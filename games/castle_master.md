# Castle Master (Incentive Software, 1990; 48K, Freescape) - stage 0 intake done, stage 1 design approved

## Next session
Stage: 1 (design)            State: design approved 2026-11-19 (Decision below); route B build plan next
Inputs: C:\1NEXT\castle_master_work\castle_master.z80 (extracted from the RZX), C:\dev\castlemaster\castle.rzx,
C:\dev\castlemaster\Castlemaster1.tap    Branch: add-castle-master    Commit: (this file's commit)
Checks: survey --stop 15000 (castle_master_survey/), survey full run (survey_full/), scan of the view buffer (3,000 frames)
Decision (user 2026-11-19): route B (Next-native renderer) + option (i) (Layer 2 on top, dither kept, cursor =
sprite, cycle = palette); colour switchable off by the player (original look). Later: palette 1-16, flat mode.
Start with: the route B build plan (stage 2) from Design + E4; replaces route A's sandbox
Read: PLAYBOOK stage 1 + 3d; cards detect.pacing-structure, detect.routine-removal, patch.hybrid-display-replacement
Open: who maps a face's colour to its dither pattern (the colour source for a colour route); unreached CALL sites (Coverage)

## Inputs
- Snapshot: the RZX's embedded .z80 (`nexclash.py rzx extract`), in game: 48K, PC 0xFDFD (RAM), IM 2 I=0xFE, vector
  0xFEFF -> 0xFDFD -> 0xC01F; handler DI / PUSH HL,BC,AF / SET 7,(29518). SP 0xFFEC. RAMTOP 32767. Border 0.
- Recording: castle.rzx, 1 segment, 167,134 frames (3,342.7 s), no autosave snapshots.
- Tape: Castlemaster1.tap = BASIC "CASTLE" (LINE 10), "CMT" CODE 32768,260 (loader), then three headerless blocks
  (6,914 / 36,098 / 6,914 bytes with flag 0, i.e. the turbo/custom loader's data); one 6,914-byte block may be the
  loading screen (not yet checked). Single load: no multiload files.

## Rendering model (survey, scan of the view buffer, first 3,000 / 15,000 frames)
| Stage | Code | Buffer |
|---|---|---|
| clear the view | 0xA502 (x158,996 writes in 3,000 frames) | 0x5CBC-0x673F (24 bytes x 112 lines, linear) |
| fill polygon spans (dither patterns, read-modify-write) | 0x9DC9-0x9DF8, 0x96F2-0x9731, ~105 routine spans 0x8637-0x8F0F | same |
| buffer to screen (LDI/unrolled block copy) | 0xA38D, called from 0x9F19 and 0xB62C | view x 32-223, y 32-143 |
| panel text / messages | 0xCA4E (17 call sites), 0xD028 | panel and message strip |
| area pictures / panel blocks | 0xB66E, attributes 0xB347 | |
The view's attributes are one ink/paper for the whole window per area (cyan, yellow, ... in the preview);
faces differ only by dither pattern. ISR at 0xC01F writes 65,856 attribute bytes (the flashing border towers /
panel) and uses LD A,R (49291, 49342); slots 1, 4, 5 never touched by it.

## Clash: kind D (one colour per area), none
No figures: everything in the view is the Freescape renderer's polygons. There is no colour clash to remove; a
Next version's gain would be colour (faces in their own colours), as with Quazatron.

## Decisions (user, 2026-11-19)
- Goal: colour the 3D view (faces in their own colours; Layer 2 presumably, panel on the ULA - design detail open).
- Speed: "utilise the Next's new hardware to dramatically speed up the rendering, without affecting the gameplay"
  = an owner-named faster pace for the renderer (patch.pace-limiter: not ORIGINAL). Constraint to settle in
  feasibility: what the game's movement / timers count (rendered frames or interrupts, 29518 bit 7 set by the ISR);
  if movement is per rendered frame, a faster renderer changes gameplay unless steps are scaled or the frame rate
  is capped - that answer goes back to the user before the design is approved.
- Speed, answered 2026-11-19: "Original pace, smooth view". Game updates keep the original's real-time rate
  (pace target ORIGINAL for game state); the time the faster renderer frees renders in-between camera positions
  (display only, never writes game state) so the view moves smoothly. Rejected by the user: faster updates
  (walk/turn faster in real time) and smaller steps (changes game logic).
  Feasibility must establish: (1) the camera state (position, yaw, pitch) and the step per update, so a tween can
  interpolate between the previous and the new camera; (2) that the renderer can run on a copy of that state
  without writing game memory (removal / isolation experiment); (3) the original's per-update real time to pace
  to (renders 2-52 frames: pace each update to its own original duration, card patch.pace-limiter); (4) the
  render cost at 28 MHz + Layer 2 + DMA, i.e. how many tween frames fit per update.

## Feasibility (PLAYBOOK 3d; first 15,000 frames)
- Pacing (card detect.pacing-structure, observed): no frame wait. Main loop body 0x8542 (callers 0x6A8C, 0x6A96,
  0x8519, 0xBD49) polls ~30x per frame (588 T) while nothing changes; on a change (move, turn, action) it runs the
  whole update + render: 0x8542 -> 0xBE03 (48643), 0x9EA3 (40611), 0x9F19 (40729 = buffer copy 0xA38D, 51,503 T).
  pacing_census --update 0x8542: renders take 2-52 frames (median ~16 = ~0.3 s, ~3 fps), one 151; 62.1 % of all
  frame time is inside 0x8542 (cost). Updates are event-driven, not frame-locked.
- Clocks (observed, ISR 0xC01F): 29559 counts down per interrupt; 49182 /120 -> 27408++; 27407 /10 -> 27411++;
  29518 bit 7 = "inside the ISR" (the printer 0xCC17 checks it before EI). Timers are real time, independent of
  render speed. The ISR also rewrites the view attributes 0x5884 (24 x 14 cells) from 27353 / table 49168
  (view flashes) - a colour design must follow those writes.
- Consequence for "faster without affecting gameplay" (inferred, to confirm by a removal experiment): one move or
  turn step per update. A faster render = more updates per second = faster walking and turning in real time,
  while the real-time clocks stay the same. Per-update game logic stays identical either way (same inputs per
  update -> same game); only the real-time feel changes. Options for the user (below, Pending).
- Sound: OUT 254 at 0xC821 (20,932, in 39 updates), 0xC117 (195), 0xB374 (16) - check which run inside render
  code before any speed-up (patch.timed-side-effect-replay).
- Colour source (observed, static code): span setup 0x9660-0x9686 sets (29662) = view line address
  (23740 + 24*line) and (29664) = 53825 + 4*((29501)-1): (29501) = the face's colour index 1-16, table 53825 = 16
  four-line dither patterns (1 empty, 2 and 11 solid, 3-10 / 12-16 dithers). Span filler ~0x969E-0x9731 reads
  (29664)+(line&3) (29658 = y), masked fill: CPL / AND (HL) / AND pattern / OR / LD (HL),A at 38633-38642, then
  whole bytes. 0x9682 is the only writer of 29664. A colour hook can take the index from (29501) per span and
  write it into a byte-per-pixel Layer 2 view: no reverse mapping from patterns needed. Which colour each index
  shows: the 16-bit versions' palettes or the user's choice (stage-1 colour question, later).
- Pipeline (observed, static + cost, 15,000 frames): 0x8542 -> [(29503) bit 2] 0x8D4F (2k T, angle sectors) ->
  0x9776 (matrix, 12k T) -> objects 0x85C9 -> 0x9D8A (clip/project, median 42k, max 662k) -> 0xBE03 (panel) ->
  0x9EA3 (raster: 0xA3F4 clear 82k, then the sorted list 26452, 4-byte entries, (29502) of them; per polygon
  header byte: hi nibble -> 29501 colour, lo nibble -> 29544; 0x9484 -> 0x9448 fill, median 41k, ~6 a redraw)
  -> 0x9F19 copy 52k. Maths: 0xA1FD / 0xA253 multiplies (18 / 20+ callers in 0x86xx-0x8Bxx transform), 0xA2C1
  24-bit divide (perspective). Shares of all T: 0x8542 62.1 %, raster 17.5 %, fill 12.6 %, spans 10.1 %, copy 5.9 %.
- Walking profile (probe cm_profile, frames 780-920, 4 steps): the CPU is busy all the time, ~2.4M T a step
  (~34 frames): maths A1C0-A3BF ~20 %, clip/project 9D80-9EBF ~16 %, spans 9540-977F ~17 %, panel/attrs B2C0-B3BF
  ~7 %, clear 2.6 %, copy ~2 %, keyboard 0xC18D 2.3 %. No wait: the original's pace IS its render time.
- Camera (observed, cm_profile at each 0x9776): x, y, z = 16-bit at 27309, 27311, 27313 (start 928, 96, 8032;
  y = eye height); pitch 27318, yaw 27319, both mod 72 (5 deg); a turn = 2 units (10 deg); a walk step ~238 units
  ((+206, -120) at yaw 24). 27315 / 27317 = 0xF0 (unknown, constant so far).
- DMA / DDMA evaluation (docs/DDMA.md; estimates, not measured):
  | Stage | Original | Next route | DMA fit |
  |---|---|---|---|
  | clear view | 82k T (0xA3F4) | Layer 2 sky / ground fill | DDMA 2D fill (no read phase); fallback zxnDMA fixed-source fill; CPU |
  | spans | ~731 T each, ~300 a redraw | 8bpp Layer 2: a span = a run of one byte | DDMA fill per span pays only above a crossover width (setup ~15 port writes); short spans CPU (LD (HL),A / INC L unrolled); measure the crossover on hardware |
  | copy | 52k T | none: render into the hidden Layer 2 bank, flip NR 0x12 | removed |
  | maths | ~20 % | Z80N MUL D,E for 16x16 / 24-bit products, 28 MHz | n/a (CPU) |
  | sandbox refresh (below) | - | 40K RAM copy per game update | zxnDMA memory-to-memory, ~6-8 ms |
  DMA helps the raster part (~25 %); the bulk (maths + clip ~36 %) needs 28 MHz + MUL. Gating per DDMA.md 3:
  core >= 3.03.00 for DDMA, ordinary zxnDMA otherwise, CPU-only build option (HLIB_NO_BLITTER / HLIB_CPU_ONLY).
  Rough budget (inferred): 2.4M T at 3.5 MHz ~ 690 ms -> ~115 ms at 28 MHz (x6, LEARNINGS 2.1f) before MUL /
  DMA / no copy; with them perhaps 40-60 ms -> 6-12 in-between views per outdoor step (12-25 fps) instead of ~1.5.
- Tween sandbox (route A; ISR redirect proven by E5 below): RAM DMA-copied to a sandbox after each update, the
  original renderer run there on an interpolated camera (position lerp of 27309-27313; finer yaw / pitch via the
  matrix builder 0x9776 and an own sine table: 72 steps give one in-between angle per 10-deg turn). Pace: each
  update lands when the original's would (its render T, E3; patch.pace-limiter). Open: OUT 254 at 0xC821 (39
  updates), the panel 0xB3xx.
- Render consumers (probe cm_consumers, 3,000 frames, 65 redraws; window 0x9776 .. 0x859F, ISR excluded): game
  code outside the window reads render-written bytes: the projected polygons / display list 0x6754-0x68xx by
  0xB708-0xB7BE and 0xBA42-0xBA60 (inferred: the crosshair pick, i.e. gameplay) and by 0x9495-0x952B / 0x9EDA-0x9EEC
  (a second draw path, 0xB62C copy callers 0xB40B / 0xB41B / 0xB447); flags 0x733E, 0x7353, 0x7377; 0xBE00-0xBE02
  (the panel 0xBE03's own variables, inside my coarse window); screen reads by the printer 0xCAA2 / 0xCAF1 /
  0xCB53, 0x7FD6-0x7FE1 by 0xCF39. Decision consequence: the game's own redraw at each update's camera must stay,
  in game RAM, unchanged in what it writes (it may draw to Layer 2 instead of the buffer); in-between views may run
  only in an isolated copy (sandbox) and must never be what the pick reads.
- Raster stage alone (separate session 2026-11-19; castle_master_work/skip_*.log, taint_8599_full.json; narrower
  than cm_consumers: only the dynamic extent of CALL 0x9EA3 at 0x8599, ISR excluded):
  taint over all 167,135 frames (5,281 calls): the only raster-written bytes read by code outside it are the view
  buffer, by display code: copier 0xA3A6-0xA3D4, copies 0xB6C2 / 0xD1B1, printer 0xCAA2 / 0xCAFC, masked overlay
  0xD134-0xD142, XOR marker 0xCF53-0xCF67 (fixed buffer addresses 0x61BF-0x624F), and the filler itself
  (0x96EA / 0x9710, reached from the other 0x9EA3 call sites 0xA0A0 / 0xB635 / 0xC539). Its 8.7M writes to page
  0x73 and 15.7M stack-page writes are never read outside it. So 0x9EA3 is display-only in the recording (observed);
  the pick's inputs (display list 0x6754-0x68xx, above) come from the stages before it, which must stay.
  routine_skip, 15,000 frames: 0x8599 skipped, buffer excluded: 62 / 462 updates identical (differences = the
  unread page-0x73 scratch); 0x859C (0x9F19) skipped: 437 / 462, 25 differ in game variables (first 0x6AD9, 0x7339,
  0xC677): 0x9F19 is not a pure copy, keep it and remove only the 0xA38D copy inside; 0x855E / 0x8561 / 0x857E
  skipped: heavy differences incl. code pages (0x8561 worst): not removable singly; 0x8596 (0xBE03): 456 / 462 (no
  use as a negative control). Not checked: branches the recording never takes; what the raster's writes to page
  0xA3 (the copier's code) patch (instruction-fetch reads are not counted by the probe). Filler overrun
  (observed): spans write up to 0x6752, 23 bytes past the buffer end 0x673B and 2 bytes short of the display list
  at 0x6754; a hook must not assume the buffer bounds.
  Engine-replacement option (asked by the user, not decided): because the raster is display-only, in-between
  views could come from a new Next-native renderer (own camera, own pages, reads the world data) instead of the
  sandboxed original, while the game's own update incl. projection runs unchanged for the pick and the pace.
  Format reference: ScummVM's Freescape engine loads the ZX Castle Master data as one 36,096-byte file = the
  tape's 36,098-byte block less flag and checksum (its ZX support is marked unstable; GPL, check before copying).
- Design (for approval, not built; consolidated 2026-11-19): (a) colour: span hook in the filler (0x9696 path:
  covers all four 0x9EA3 callers 0x8599 / 0xA0A0 / 0xB635 / 0xC539; bounds = the filler's real extent to
  0x6752) writes (29501) indices to Layer 2 (hidden bank, flip), palette per index (user's choice), clear by
  DDMA 2D fill; 0x9F19 stays (changes game variables), only the 0xA38D copy's screen writes go; panel stays ULA.
  (b) speed: updates run the original at 28 MHz with the E1 maths. (c) smooth view, route A (user 2026-11-19:
  first, provided E5 early): after each update a DMA copy of RAM = sandbox renders in-between cameras into
  Layer 2 while the update waits out the original's duration (pace ORIGINAL). Route B (Next-native renderer,
  CHOSEN): no jump if it draws every view incl. each update's final one; what remains is a pixel-level
  gap between what is shown and what the crosshair pick hits. (d) DMA: DDMA on core >= 3.03.00, zxnDMA
  otherwise, CPU-only option; span-fill crossover measured on hardware.
  Scope (user): "display-only" holds on recorded paths; unrecorded branches and the raster's writes into the
  copier's code page 0xA3 are unchecked. Buffer readers (printer 0xCAA2 / 0xCAFC, overlay 0xD134-0xD142, XOR
  marker 0xCF53-0xCF67, copies 0xB6C2 / 0xD1B1) draw INTO the buffer, so the buffer alone does not show them
  once its copy goes (user's correction). Options: (i) each to Layer 2 (more hooks); (ii) user's idea,
  untested: faces out of the buffer, keep its copy to the ULA, ULA over Layer 2 with the view paper see-through
  - to work out: per-area paper colours (NR 0x14 vs a ULA palette entry shared with the panel), the ISR's
  view-attribute flashes (0x5884, 24 x 14). E4 checks which readers are active in play.
  R (static): ISR LD A,R 49291 / 49342 = blink delays 49173 / 49175 (cosmetic); 0x9F6E: 27391 = (R AND 63) +
  10, an event countdown (gameplay) -> sandbox renders and hooks restore R (patch.preserve-r); 0xA569: R mod
  20 -> 41970 (display). Interrupts land elsewhere at 28 MHz: "extremely close", not 1:1.
- E5 PASS (castle_master_work/e5_isr_redirect.py, e5_full.log): ISR redirect while the sandbox is mapped. MMU
  model, real pages 10, 11, 4, 5, 0, 1 / sandbox 32-37 (camera and all 18 ISR variables altered, 0xFDFD JP ->
  stub). Stub at 0x2000 (slot 1, never touched by the renderer): LD (0x82C0),SP / LD SP,0x8400 / NEXTREG
  0x52, 0x53, 0x56, 0x57 -> real / CALL 0xC01F / DI / NEXTREG back / LD SP,(0x82C0) / EI / RET; 0x82C0-0x8400
  never used by the game. 79,705 / 79,705 interrupts in redraw windows (all frames): real RAM = the
  recording's handler result, sandbox unchanged, registers and MMU back; 245 T (3.5 MHz T) each. 229 cosmetic
  blink-delay bytes differ (R; accepted pending the user). Controls: no remap, slot 3, 6 unmapped, SP not
  restored FAIL 20 / 20; slot 2 2 / 20; slot 7 passes all (stack + vector only; remap kept, 40 T). Not covered:
  hardware MMU / timing, the renderer's DI periods, unrecorded branches.
- E1 PASS (e1_maths.asm, e1_capture.py / e1_check.py, e1_check_full.log): Z80N 0xA1FD (A*HL), 0xA253 (HL*DE),
  0xA348 (H*L) with MUL D,E; 0xA2C1 (AHL/DE, DE = remainder) = restoring division unrolled, leading quotient
  zeros skipped, DE = 0 -> the original's code. All 682,956 unique inputs of 1,827,355 recorded calls, original
  vs new: all 16 registers, SP / IX / IY, memory, flags equal; + 100,000 random each, edges, 0xA348 exhaustive.
  T per call 554 -> 273, 489 -> 228, 2,078 -> 904, 238 -> 110: maths 9.7 % -> 4.5 % of the recording's T.
  4 mutants FAIL (Lessons); a dead 16x16 carry removed.
- E2 PASS, route A (e2_sandbox.py --timer --prevbuf, e2_full_final.log): every full redraw (block 34142 ->
  0x859F in 0x8542, (29503) bit 2; 18 more never reach the copier: non-view screens via (29513)), sandbox = RAM
  at 0x859F, registers as at 34142, no interrupts: buffer at the copier 0xA38D = the game's, 5,214 / 5,214.
  Two inputs must be live (first runs 5,202 / 5,214): 27391 (ISR-decremented countdown, read by the clear at
  42076: sky / ground split 41966; 3 frames, 1-43 bytes) -> tweens read the real 27391; the buffer is not fully
  rebuilt (filler 0x96F2 / 0x9716 read-modify-writes, the clear misses bytes; 9 frames, 1-126 bytes) -> tweens
  draw over the last shown frame. Not causes: R at 0xA569, ISR -> render data flow (none). Controls: yaw +10
  deg 61 / 62 FAIL, raster skipped 62 / 62 FAIL, display list junked still PASS (rebuilt). Block T median 883k,
  max 4.59M. The re-run writes the ULA panel and 0xBE / 0xCA / 0xCC variables: keep 0xBE03's and 0x9F19's
  screen writes off the real screen. Design rule (hardware, untested): the RAM -> sandbox DMA copy finishes
  before a tween starts (no DMA in flight when the E5 stub runs).
- E3 (e3_probe.py / e3_frames.py / e3_fit.py --realtime, logs e3_*.log): wall time per update (main-loop
  iteration 0x8542 -> 0x8542 that ran the raster; 5,379, fit on frames <= 15,000, tested on 4,908 later ones).
  Physics: frames = (T main + T ISR + 1.23 T x accesses to 0x4000-0x7FFF) / 69,888: test 99.9 % within 2 %,
  median 0.14 %, max 2.5 %, total +0.10 %. Reference fix: 168 RZX frames of ~20 T (Fuse closes one when an
  interrupt held off by DI lands) count by their T; before that 146 updates were one frame "short". Runtime
  model for the pacer: a cycle timer on the Next measures main + ISR (same instructions; add back the E1 saving
  per maths call; 28 MHz wait-state factor to calibrate on hardware), contention from hook counters (span
  bytes, spans, polygons, objects, prints, copy, clear, display list): test 96.0 % within 2 %, median 0.36 %,
  max 8.1 % (text-only updates: no spans, contention from printing), every 10-update run within 2 % (max
  1.81 %), total +0.37 %; the pacer carries the remainder so it does not accumulate. Counters alone (no timer):
  median 7 % - not enough. Not covered: real Next timing (wait states, DMA), the CTC's availability per core.
- E4 (e4_overlays.py, e4_full.log; all frames, writers by PC; renderer paths via 0xA0A0 / 0xB635 / 0xC539
  left out): view on screen = pixel lines 32-143, columns 4-27, attributes rows 4-17. Straight onto the screen
  view: cursor / crosshair 0xCEAF / 0xCF39 (anywhere in the view, 1,829 frames), the menu's pointer arrow
  0xCB00 / 0xCB3B / 0xCB63 (lines 60-87, cols 4-6; its 1,364 frames are mostly the panel's room name), a second buffer -> screen copier 0xB6C3 (244
  frames; must be hooked like 0xA38D), masked sprite 0xD0F9-0xD146 + restore 0xD1B1 (frames 559-673 only: the opening portcullis).
  Examples: e4_shots.py -> e4_examples.png. Option (i) trial (opt1_trial.py --shaded, placeholder palette):
  user 2026-11-19: KEEP the original's dither shading. Layer 2 pixel = buffer bit set ? colour of the face
  whose span covered it (0x969E: H / D ends, (29662) row, (29501) index) : the area's paper. Shading kept, and
  buffer overlays come back. --fix: cursor = sprite (non-copier screen writes), ISR cycle = palette
  (attrs != 0xB368's); overlays / unknown writers (mountains) keep the original ink.
  Into the buffer: XOR centre marker 0xCF54-0xCF68 (175 frames), printer 0xCA97 / 0xCAA4 / 0xCAF5 / 0xCB00-0xCC16
  (151), full-view transition effect 0xCA42 (12), boxes 0xBC9F-0xBD34 (6). Attributes: area colours 0xB368 (218: values
  6, 68, 124, 62, 5 - some WHITE paper), ISR 0xC069 colour cycle (4,977 frames: one value to all 336 cells from
  table 49168, 70 / 67 / 66 / 6, paper black, ink cycles). Consequence: option (i) needs every one of these
  re-routed to Layer 2 (cursor could be a hardware sprite); option (ii) keeps all of them as they are, but the
  view's paper must be see-through while the panel, sharing the same paper palette entries, stays opaque
  (white-paper areas) - unsolved; for the user's design decision.
- Not the filler: 0x9DC9-0x9DF8 writes variables 24369-24382 that lie inside the view buffer's address range
  (geometry / clipping scratch, run when (29502) > 1); the scan range 0x5C80-0x673F mixed both.
- View buffer (observed): 0x5CBC-0x673B, 112 lines x 24 bytes, row table 28975; copied by 0xA38D (LDI x24 per
  line); 0xA502 clears it.

## Coverage (survey GATE, 15,000 frames)
Unreached CALL sites: 0xD028 (2/3), 0xCA4E (17/18), 0xB66E (2/6; 48357 not reached). All text / panel / area
pictures, no figure plotter.
Full run (survey_full/, all 167,135 frames, no desync): GATE OK; 0xCA4E 18/18, 0xB66E 4/6, 0xD028 2/3, 0xB347
4/6 reached; 5,356 view copies. No further recording needed for stage 1.

## Stage log
- 2026-11-19, stage 0 + 1 (feasibility started), ~70 min, ~45 tool calls, 2 user rounds: intake, survey 15k,
  goal + speed answered, pacing census, colour source found.
- 2026-11-19, stage 1 feasibility (DMA / DDMA), ~60 min, ~30 tool calls, 1 user round: stage costs, walking
  profile, camera, consumer probe, proposed design.
- 2026-11-19, E5 / E1 / E2 / E3 / E4 + option (i) trial, ~6 h incl. many ~10-min full runs, ~150 tool calls,
  ~10 user rounds: all experiments PASS / recorded (Feasibility); results above.
- 2026-11-19, separate session (removal + taint of the raster stage), ~60 min, ~25 tool calls, 3 user rounds: six
  routine_skip runs, a taint probe over the full recording (castle_master_work/taint_call.py).

## Lessons
- [doc docs/RECORDING_CHECKLIST.md §Making a recording (Fuse)] An RZX alone (no separate .z80) is a complete intake: `nexclash.py rzx extract R -o
  GAME.z80` gives the snapshot it was recorded from (here a .tap came with it, not needed for a single load).
- [local: one game's misread; the survey reports what the copier reads] The survey's buffer range (0x5C80-0x673F, rounded) mixed the view buffer with renderer variables, so
  `scan --writers` on it listed geometry code first; the copier's own pointer (LD HL,23740 at 0xA39A) gave the
  exact buffer.
- [local: one game's maths; a candidate for a shared bit-exact checker if a second game replaces maths] A
  bit-exact replacement checked only on recorded inputs can hide wrong rare paths: two of four mutants passed
  every recorded call and failed only random / edge inputs, so add sweeps and mutants.
- [local: one harness; tools/probes candidate if a second game sandboxes a renderer] Junk-filling a buffer
  before a re-render is a strong test only if the renderer fully rebuilds it; when it reads-modify-writes, use
  the buffer as it was before the game's own render, and bisect differing inputs from the block's START state
  (a bisect that already fails on the start state names a random byte).
- [local: one game's pacing check; tools/probes candidate] RZX frames are not real time: Fuse writes a ~20 T
  frame when an interrupt delayed by DI lands, so a frame count runs ahead; weigh short frames by their T.

## Technique use
- detect.pacing-structure: helped: pacing_census on the main loop 0x8542 showed event-driven renders of 2-52
  frames and no frame wait, which set the speed question.
- patch.preserve-r: used: found the gameplay R read (0x9F6E -> 27391) that every sandbox render must restore;
  the ISR's R reads are cosmetic (E5: 229 blink-delay bytes).
- detect.routine-removal: helped: the consumer probe (cm_consumers) found gameplay reads of the projected
  polygons, which ruled out replacing the game's own redraw with a tween.

## Friction
- reuse: [tool tools/probes/pacing_census.py] used as it is; `nexclash.py cost` too
- retries: [local: the skoolkit helper first named dis.py shadowed the stdlib module `dis`; renamed]
- environment: [none: local Windows checkout, no workarounds needed]
- hand-rolled: [local: byte searches for CALL / LD (nn) sites with skoolkit's snapshot reader]
- scratch: [local: cmdis / callers helpers stay in the session scratchpad; cm_profile and cm_consumers are
  Castle Master probes, to move to tools/probes/ if E1-E3 reuse them; e5_isr_redirect.py, e1_*.py / e1_maths.asm, e2_*.py, e3_*.py, e4_overlays.py (local, castle_master_work)
  becomes part of the engine's own verifier at stage 2 (verification harnesses stay per engine)]
