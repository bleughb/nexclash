# Hard Drivin' (Domark / Binary Design, 1989; 128K tape)

## Next session
Stage: 2 (build)             State: M2 prototype (hd2) passes unit tests; pace in JNext within 0.16 % of the original
Inputs: C:\1NEXT\harddrivin_work: hard_drivin.z80 (snapshot 0 of hard_drivin.rzx), hard_drivin.rzx (MD5 c649e04c, 22,116 frames), in\hd.tap (MD5 02e1f96c), in\hd.tzx (61f7d04c), in\hd.dsk ([a], 43a6bc4c). Game data: never in this repo.
Branch: add-hard-drivin (worktree C:\1NEXT\nexclash-hd)    Commit: see git log
Prototype (local, not in the repo yet): C:\1NEXT\harddrivin_work: hd2.asm (hooks), hd_build.py (128K patch over
  nexclash.z80tonex), hd_next.py + simram.py (host Next model), hd_unit.py (differential unit test), jlog.py (JNext
  pace log vs jn\jl_plain), jrun.py (screenshots)
Checks: `py -3 hd_unit.py --prefix hd2 [--cal]` PASS 0 (11 states, both paths); jlog 4,000 frames: 178 updates,
  start-time drift -4 frames vs plain, 182 in-between views
Pending user answers: none
Start with: verify over the RZX (game RAM + registers per update), mutants for the scratch-page / camera restore,
  then move the prototype into an engine module + tests, then a hardware build for the user (K differs on hardware:
  calibrated at run time)
Open: the first calibration interrupt's extra ~574 T (not subtracted, 0.06 %); sub-unit angle interpolation; copy K
  calibrated separately (uses the render's K now); the CALL at 0xA402 (time-out path, not in the recording)

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
