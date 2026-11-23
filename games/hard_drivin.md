# Hard Drivin' (Domark / Binary Design, 1989; 128K tape)

## Next session
Stage: 3 (prove + deliver)    State: selftest --game hard_drivin --verify --stamp PASSED 2026-11-23 (stamped verified); hardware next
Techniques: `patch.inbetween-views`, `detect.pacing-structure`, `patch.pace-limiter`, `patch.restore-speed`, `patch.whole-altrom-image`, `verify.update-locked-pace`
Inputs: C:\1NEXT\harddrivin_work: hard_drivin.z80 (MD5 18809405, snapshot 0 of hard_drivin.rzx), hard_drivin.rzx (MD5 c649e04c, 22,116 frames), in\hd.tap (MD5 02e1f96c), in\hd.tzx (61f7d04c), in\hd.dsk ([a], 43a6bc4c). Game data: never in this repo; not yet in specnext/reference (a maintainer push: ask first).
Branch: add-hard-drivin (worktree C:\1NEXT\nexclash-hd), main merged 2026-11-23 (83cd68b)    Commit: see git log
Engine: nexclash/hard_drivin.py (HDPatch from the profile, Next host model, verify, unit_tests, negative_patches,
  auto, boot_problems), asm/hard_drivin_hooks.asm + asm/hard_drivin_wset.inc, docs/profiles/hard_drivin.json.
  Builds: hard_drivin.nex (plain, tail 0x6C00) d74f75e6, hard_drivin_smooth.nex (default) 9fb23f8e: the prototype's
  hd2 build (9fc24d7c) byte for byte + the automap_off entry auto adds to every build (docs/NXC_PATCHES.md).
Checks: `python nexclash.py auto hard_drivin.z80 --rzx hard_drivin.rzx --quick 2000`: boot PASS (both builds, with
  and without NEXLOAD), 146 checks, 168 in-between views, unit tests and 4 / 4 negative controls PASS, rom_paths
  COMPLETE. Prototype evidence (C:\1NEXT\harddrivin_work): whole-RZX verify PASS (3,112 checks), 18 / 18 mutants,
  JNext pace +3 frames / 178 updates.
Pending user answers: none
Start with: the hardware build hard_drivin_smooth.nex (9fb23f8e) + checklist for the user: walk and turn smooth, no
  tearing, the original's speed (lap clock vs the plain build over a lap); K and the copy time are measured at run time
  (JNext's ratio 6.2 vs TECHNIQUES' hardware 6.6-7.0). The inputs are in C:\1NEXT\hd_reference (not in specnext: ask before any push)
Open: the first calibration interrupt's extra ~574 T (not subtracted, 0.06 %); sub-unit angle interpolation;
  the CALL at 0xA402 (time-out path, not in the recording); R not preserved (patch.preserve-r: the verify excludes
  R; no consumer of R found, not proven)

## Facts
- Tape (.tap = .tzx data): BASIC `HD 128K`, code 100 bytes at 30000, 5,000 at 32960, 200 at 43616, BASIC `-`, then one 41,400-byte block at 24000. Single load, no multiload.
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
- Pacing (card detect.pacing-structure, observed): no frame wait; DI for most of play. Main loop 0x9E34
  (body to 0x9E88, JR back at 0x9E32): one update = logic + render 0x9EA9 (from 0x9E54) + clock 0xA38A (from
  0x9E5E) + view copy 0xDC37 (from 0x9E6B). Update time 7-21 frames (median 13, mean 13.6): busy scenes run
  slower in game time, as in the original.
- Clocks: lap clock 0xA38A counts 5 updates per clock second (38155 to 5, BCD seconds 38156, minutes 38157);
  no real-time clock. ISR 0xC261 (IM 2, CALL from 0xC0C0) is sound only (vars 0xC2CA-0xC2CF, CALLs
  0xCE1B / 0xCEA3; bank 3 at C000 for the music, bank 0 = main code). So a faster update = a faster game:
  the update's original time must be kept.
- Cost per update (loopprof.py, 229 updates): 0x9EA9 87.3 % (845k T), view copy 0xDC37 6.4 % (62k T), the rest
  ~6 % (0xF910 3.3 %, 0xA423 1.3 %, 0xF476 0.9 %). Inside 0x9EA9 (treeprof.py): 0xD50B/0xD548 31 %, 0xD862 15 %,
  0xD9B4 11 %, 0xD584 8 %, 0xDBBE 4 %, maths 0xC7C0 / 0xDA4C: transform, clip, fill. Object list walked with
  SP from (38539); objects clipped against the camera 43400/43402/43404.
- Camera (camlog.py at each 0x9EA9): x, y, z = 16-bit at 43400, 43402, 43404; orientation 3 bytes at
  43407-43409 (copied to 43339-43341 by 0x9EA9); per-update matrix / view block 43362-43399 (0x9EA9 copies
  43362-43370 to 43371-43379). Which routine builds the matrix: open (stage 2).
### Dependency investigation
- Render consumers (consumers.py, 2,500 frames; window 0x9EA9 .. 0x9E57, screen and back buffer excluded):
  23 addresses read later by logic: 43373-43379 (camera copy, read by 0xA6FF-0xA8AB), 0x918E (read 0xA47E /
  0xA4FB, written 0xEA48), 0x91CC-0x91CD, 0x951E (0xA353, 0xF4A9, 0xA71B), list 0xF02C-0xF03B (0xA48D-0xA496,
  written 0xEA46). In-between renders must leave these as the real render leaves them: the real render runs
  last, and these bytes are saved / restored around the extra ones; the differential test proves game RAM.
- Back buffer 0x8000-0x8FFF (4K, write-first) -> screen 0x4000-0x4FFF by 0xDC45 (SP copy). DMA candidate:
  the view copy only (docs/DDMA.md: zxnDMA / DDMA, core gated, plain fallback) - to measure in stage 2.
- Open: sound in play (engine / crash sound: OUT sites, AY from the ISR only?); interrupt windows in the loop
  (EI points) must stay at the original's times so the music tempo holds.

## Design (proposed, stage 2)
- Hooks: the render + copy block 0x9E54 .. 0x9E6E runs at 28 MHz inside a pace window (hlib_pace, as Castle
  Master M3a); window target = the original's time for this update (K x 28 MHz time, measured).
- In-between views: camera linear from the last shown view to the new one (positions; orientation by angle,
  matrix rebuilt by the game's own routine), drawn while they fit before the target; the real view last, shown
  at the original's time. Consumer bytes above saved / restored around each extra render.
- Display: views double-buffered (Layer 2 or a second ULA bank, to decide; the original look kept: green
  monochrome view, dashboard unchanged).
- Verify: RZX replay, game RAM + registers (R excepted per patch.preserve-r decision) = original at every
  update; pace per update vs the original (verify.update-locked-pace); mutants for the save / restore.

## Build (stage 2, hd2 as built)
- Sites (original bytes checked): 0x9E54 CALL render -> t_render, 0x9E6B CALL copy -> t_copy, 0xD6FE CALL 0xD77D
  (unconditional, ~100 a render, gaps under 340k T) -> t_tick (the line clock's tick inside the 28 MHz render).
- Hook code: page 36 (bank 18) in MMU slot 1 during hooks; trampolines at 0x3870 in an alt ROM (bank 12, Sinclair's
  ROM 1 + trampolines; 0xFF there); exit by NEXTREG 0x51,0xFF + RET from the ROM side. Own stacks 0x3FFE / 0x3D80.
- Render facts: the matrix builder is 0xD1A5 (called by the render at 0x9EC2; orientation 43339-41, sin/cos
  0x95AB). The render is a pure function of camera + world (a re-render with the previous camera gives the previous
  view; time repeats within 0.015 %). It POPs ROM bytes as data (SP pages 0x00-0x16) and never executes the ROM.
  No DI / EI / HALT / IM in it. Two update paths never return (JP 0x9E12): 28 MHz only inside the hooks.
- Sound in play: per-update AY writes 0xEA60-0xEB20 (bank 3, called from 0x9E7E), outside the hooks; no
  interrupts in play, so no tempo to hold inside the window. Other render callers (0x6A32, 0xF652, 0xF752) stay plain.
- Per update: the real render first (genuine pages, original SP, planted return), slots 4-7 DMA-copied to scratch
  pages 38-41, in-between views rendered there with the camera interpolated (fraction = display time / window),
  each copied by the game's own copy when the beam is in lines 128-262 (no tear). Window target L = K x the real
  render's 28 MHz lines; debt carries (signed wait goal, cap 1,200 lines). Copy target = K x the copy's lines.
- K calibration at run time (updates 1, 3, 5, then every 16): slots 2-7 copied to scratch pages (43-44 for 2-3),
  a RAM copy of the ROM (page 42) in slot 0, tick site restored there; the render runs again at 3.5 MHz with IM 2
  through its own table (handler on its own stack counts frames, repairs the 2 pushed bytes from genuine memory,
  resumes by EI + JP). K = cal lines (minus 400 T a frame for the handler) / 28 MHz lines; samples outside 4-10
  dropped. K = the latest sample: an average of samples lagged the scene's own K changes.
- JNext measurements (1.3.0): K 6.17-6.28 depending on the scene (contention share); hardware ratios in
  TECHNIQUES are 6.6-7.0, hence run-time calibration. Pace vs plain, 178 updates: average of samples every 64:
  -18 frames; every 16: -13; latest sample every 64: -9; latest sample every 16: -4 (0.16 %), 182 in-between views
  (2-4 a moving update). No in-between views while the camera is still (e.g. stopped after a crash): by design.

## Stage log
- 2026-11-22: stage 0 (intake) + stage 1 (route choice, feasibility), ~50 tool calls, 1 user round.
- 2026-11-23: stage 2 build: hd1 (fixed K) then hd2 (run-time K); unit tests pass; JNext pace within 0.16 %.
- 2026-11-23 (2): hd_verify.py (whole RZX, every loop render, normal + calibration paths: game RAM, registers, each
  in-between view = the original render at an exactly computed camera, calibration time = the original's) and
  hd_mutants.py (16 mutants, 16 caught over 9,000 frames). Fixed: setcam read angles from cam0+6 (every in-between
  view's angles wrong); calibration push repair wrong in the render's write set (tables 0x9C00-0x9DFB: sample dropped,
  bitmap hd_wset.inc, retry in 2 updates; 20 % dropped); missed first interrupt at line 240-255 (wait); calibration
  from the post-render carry (block 0x912E-0x91CD + 43337 saved / restored); copy target = its measured 3.5 MHz time
  (cpy35) less 3 lines of hook overhead (the render's K was 8 % short for the copy). ISR_T 1104. JNext pace: +2
  frames over 178 updates (0.08 %), 190 in-between views. Full verify: 3,112 checks, 3 FAIL, all calibration path:
  u605 runaway (push 7 of that render; all pushes kept = PASS; address not yet read: scratchpad push605.py), u963 /
  u964 short renders (2-3 frames) +0.53 / +0.69 % (plan: drop samples under ~1,000 lines).
- 2026-11-23 (3): the three open calibration fails fixed. u605: a push in the write set (0x9C39) was flagged but
  still repaired with a stale byte; the render followed it and ran away. Now the handler abandons a hit render at
  once (SP from cal_sp, JP cal_r1; all scratch). u963-964: renders under 1,000 lines (CAL_MIN) give no sample.
  ISR_T 1136 (whole-RZX mean 1138). Verify rules added: a hit push must be the render's last; no sample from a short
  render. Mutants Q (no abandon) and R (no CAL_MIN) caught. Full verify PASS; kept samples -0.14 .. +0.43 % of the
  original render's time (median +0.06 %), 196 of 1,556 dropped.
- 2026-11-23 (4): moved into the repo as an engine (nexclash/hard_drivin.py from hd_build / hd_next / hd_unit /
  hd_verify; hooks asm and the write-set bitmap in asm/; profile via asm2profile, IDENTICAL). The repo's smooth build
  equals the prototype's (MD5 9fc24d7c). Negative controls as page-byte patches at labels (sco_map, sc_angix, isr_fix,
  isr_taint); the push-repair control was missed on 6 states at their own start line and caught once the start line
  sweeps the frame (every 13 lines). Boot check credits the tail 0x6C00 and NEXLOAD's printer buffer (rom_paths:
  never read before written). Main merged (shared lessons as data, docs/kb); kb entry docs/kb/games/hard_drivin.json.

- 2026-11-23 (5): selftest --game hard_drivin --verify --stamp (inputs in a local reference folder,
  C:\1NEXT\hd_reference, not pushed): verify PASS on the whole RZX (3,112 checks, 3,281 views, unit tests on 11 states,
  4 / 4 negatives); two FAILs fixed: auto failed a rebuild with no recording (Unit: no states), so main's automap_off
  step never ran and the rebuild's MD5s differed from the verify's; the record held pre-automap_off MD5s.
## Technique use
- detect.pacing-structure: helped: no frame wait, 7-21 frame updates, the lap clock counts updates (not time)
- patch.inbetween-views: helped: the route itself; corrected: K is measured at run time by a calibration render (the card's fixed K from JNext would be 6-10 % off on hardware), and in-between views run on scratch copies of the game's pages instead of Layer 2 banks
- patch.pace-limiter: used: ORIGINAL target per update (window = K x the render's 28 MHz lines, signed debt)
- patch.restore-speed: used: hlib_speed in every hook
- patch.whole-altrom-image: used: Sinclair's ROM 1 + trampolines at 0x3870 (bank 12)
- verify.update-locked-pace: used: JNext pace log vs the plain build, 178 updates
- patch.preserve-r: no help: not applied; the verify excludes R (no consumer found, not proven)

## Lessons
- [kb lesson.jnext-28mhz-ratio-varies: K 6.17-6.28 by scene in JNext] observed: the render's 3.5 MHz : 28 MHz ratio moves with the scene's contention share; a fixed K lagged, the latest calibration sample tracks it.
- [kb lesson.runtime-k-calibration: a 3.5 MHz re-render on scratch pages measures K] demonstrated: calibration render with IM 2 through the hook page, kept samples within -0.14 .. +0.43 % of the original render's time over the whole RZX.
- [kb lesson.sp-as-data-pointer: an interrupt push lands in the render's SP-walked data] demonstrated: the render POPs object lists and ROM bytes, so the calibration handler must put the 2 pushed bytes back from genuine memory.
- [kb lesson.interrupt-push-in-write-set-abandon: a hit push cannot be repaired] demonstrated: a push into bytes the render writes (tables 0x9C00-0x9DFB) was repaired with a stale byte and the render ran away (u605); abandon the render and drop the sample.
- [kb lesson.negative-control-phase-sweep: sweep the start line for interrupt-timed faults] demonstrated: the no-repair control passed on 6 states at their own start line and was caught once the start line swept the frame.
- [kb lesson.skoolkit-write-guards-below-4000: the reference re-render ran away] observed: stock SkoolKit dropped the hook page's writes below 0x4000; dizzy6._rw_simulator keeps them.
- [kb lesson.nexload-printer-buffer: 256 bytes differ when booted as NEXLOAD] observed: both builds differ only in 0x5B00-0x5BFF and the tail; rom_paths shows neither is read before written.
- [kb lesson.rebuild-without-recording-must-pass: a FAILED auto skips the CLI's later steps] observed: the rebuild recipe gives no recording; auto returned FAILED, so the automap_off entry was not added and the rebuild's MD5s differed from the verify's.
- [kb lesson.asm2profile-key-prefix: profile keys from SAVEBIN names] observed: asm2profile takes the key from the SAVEBIN name up to the first underscore, so hard_drivin_page.bin gave "drivin_page"; named hdrivin_page.bin / hdrivin_rom.bin.

## Friction
- reuse: [kb lesson.negative-control-phase-sweep] the start-line sweep in unit_tests is generic for any interrupt-timed control
- retries: [kb lesson.skoolkit-write-guards-below-4000] the verify reference ran away three times before the low writes were kept
- environment: [none: git, harness and network had no workaround this stage]
- hand-rolled: [local: the host Next model (MMU, line clock, zxnDMA, IM 2) is per engine; hooklib.NextModel has no MMU or interrupts]
- scratch: [local: push605.py, hd_repo_quick.py dropped: one-off reproductions, the engine's verify covers them]
