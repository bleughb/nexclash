# Castle Master (Incentive Software, 1990; 48K, Freescape) - stage 0 intake done, stage 1 design approved

## Next session
Stage: 2 (build)             State: M1 PASS (Z80N geometry + raster to Layer 2); M2 next
Inputs: C:\1NEXT\castle_master_work\castle_master.z80 (extracted from the RZX), C:\dev\castlemaster\castle.rzx,
C:\dev\castlemaster\Castlemaster1.tap    Branch: add-castle-master    Commit: (this file's commit)
Checks: survey --stop 15000 (castle_master_survey/), survey full run (survey_full/), scan of the view buffer (3,000 frames)
Decision (user 2026-11-19): route B (Next-native renderer) + option (i) (Layer 2 on top, dither kept, cursor =
sprite, cycle = palette); colour switchable off by the player (original look). Later: palette 1-16, flat mode.
Start with: M2 (Build design "Milestones"): integrated NEX, update-camera views in colour; M1's "For M2" notes
Read: PLAYBOOK stage 1 + 3d; cards detect.pacing-structure, detect.routine-removal, patch.hybrid-display-replacement
Open: unreached CALL sites (Coverage); renderer speed on hardware (wait states, DMA fills)

## Inputs
- Snapshot: the RZX's embedded .z80 (`nexclash.py rzx extract`), in game: 48K, PC 0xFDFD (RAM), IM 2 I=0xFE, vector
  0xFEFF -> 0xFDFD -> 0xC01F; handler DI / PUSH HL,BC,AF / SET 7,(29518). SP 0xFFEC. RAMTOP 32767. Border 0.
- Recording: castle.rzx, 1 segment, 167,134 frames (3,342.7 s), no autosave snapshots.
- Tape: Castlemaster1.tap = BASIC "CASTLE" (LINE 10), "CMT" CODE 32768,260 (loader), then three headerless blocks
  (6,914 / 36,098 / 6,914 bytes, flag 0: the custom loader's data). Single load: no multiload files.

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
- Speed: "Original pace, smooth view": updates keep the original's real-time rate (pace ORIGINAL, per update);
  the freed time renders in-between cameras (display only). Rejected: faster updates, smaller steps.

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
- Colour source: (29501) = the face's colour index 1-16 per span; table 53825 = 16 four-line dither patterns (1
  empty, 2 and 11 solid); the filler ANDs / ORs the pattern into the buffer. Layer 2 takes the index per span.
- Pipeline costs (15k frames): 0x8D4F sectors 2k T, 0x9776 12k, 0x9D8A sort median 42k (max 662k), raster
  (clear 82k + fill ~41k) 17.5 % of all T, copy 52k; walking ~2.4M T a step, maths ~20 %, no wait anywhere.
- Camera (observed, cm_profile at each 0x9776): x, y, z = 16-bit at 27309, 27311, 27313 (start 928, 96, 8032;
  y = eye height); pitch 27318, yaw 27319, both mod 72 (5 deg); a turn = 2 units (10 deg); a walk step ~238 units
  ((+206, -120) at yaw 24). 27315 / 27317 = 0xF0 (unknown, constant so far).
- DMA / DDMA evaluation (docs/DDMA.md; estimates, not measured):
  | Stage | Original | Next route | DMA fit |
  |---|---|---|---|
  | clear view | 82k T (0xA3F4) | Layer 2 sky / ground fill | DDMA 2D fill (no read phase); fallback zxnDMA fixed-source fill; CPU |
  | spans | ~731 T each, ~300 a redraw | 8bpp Layer 2 (M1: PUSH fill) | DDMA per span only above a crossover width (setup ~15 port writes); measure on hardware |
  | copy | 52k T | none: render into the hidden Layer 2 bank, flip NR 0x12 | removed |
  | maths | ~20 % | Z80N MUL D,E for 16x16 / 24-bit products, 28 MHz | n/a (CPU) |
  | sandbox refresh (below) | - | 40K RAM copy per game update | zxnDMA memory-to-memory, ~6-8 ms |
  DMA helps the raster part (~25 %); the bulk (maths + clip ~36 %) needs 28 MHz + MUL. Gating per DDMA.md 3:
  core >= 3.03.00 for DDMA, ordinary zxnDMA otherwise, CPU-only build option (HLIB_NO_BLITTER / HLIB_CPU_ONLY).
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
  routine_skip (15k): 0x8599 skip changes only page-0x73 scratch; 0x9F19 is not a pure copy (25 / 462 differ in
  game variables): keep it, drop only 0xA38D; 0x855E / 0x8561 / 0x857E not removable. Filler overruns to 0x6752.
  Engine-replacement option (asked by the user, not decided): because the raster is display-only, in-between
  views could come from a new Next-native renderer (own camera, own pages, reads the world data) instead of the
  sandboxed original, while the game's own update incl. projection runs unchanged for the pick and the pace.
  Format reference: ScummVM's Freescape engine loads the ZX Castle Master data as one 36,096-byte file = the
  tape's 36,098-byte block less flag and checksum (its ZX support is marked unstable; GPL, check before copying).
- Design history (2026-11-19): (a) colour by a span hook in the filler, (b) speed = the original at 28 MHz +
  E1, (c) route A = sandbox renders in-between cameras; route B (Next-native renderer) CHOSEN: no jump if it draws
  every view incl. each update's final one; what remains is a pixel-level gap between what is shown and what
  the crosshair pick hits. (d) DDMA on core >= 3.03.00, zxnDMA otherwise, CPU-only option. Scope (user):
  "display-only" holds on recorded paths only. Buffer readers (printer, overlay 0xD134, XOR marker 0xCF53,
  copies 0xB6C2 / 0xD1B1) draw INTO the buffer (user's correction) -> option (i) each to Layer 2 (chosen);
  (ii) ULA over Layer 2 (unsolved for white-paper areas).
  R (static): ISR LD A,R 49291 / 49342 = blink delays 49173 / 49175 (cosmetic); 0x9F6E: 27391 = (R AND 63) +
  10, an event countdown (gameplay) -> sandbox renders and hooks restore R (patch.preserve-r); 0xA569: R mod
  20 -> 41970 (display). Interrupts land elsewhere at 28 MHz: "extremely close", not 1:1.
- E5 PASS (castle_master_work/e5_isr_redirect.py, e5_full.log): ISR redirect while the sandbox is mapped. MMU
  model; stub at 0x2000 (slot 1): own SP 0x8400 (0x82C0-0x8400 unused by the game), NEXTREG slots 2-3 / 6-7
  real, CALL 0xC01F, back. 79,705 / 79,705 interrupts: real RAM = recording, other pages unchanged, 245 T each;
  229 cosmetic blink bytes differ (R). Controls FAIL (no remap, slot 3, 6, SP). Not covered: hardware, DI periods.
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
  rebuilt (filler read-modify-writes, the clear misses bytes; 9 frames) -> the game's own render reads the last
  shown frame. Controls FAIL (yaw +10 deg, raster skipped). Block T median 883k, max 4.59M.
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
  table 49168, 70 / 67 / 66 / 6, paper black, ink cycles). Option (i) re-routes each to Layer 2 (chosen);
  option (ii) (ULA over Layer 2) was unsolved for white-paper areas.
- Not the filler: 0x9DC9-0x9DF8 writes scratch 24369-24382 inside the buffer's address range ((29502) > 1).
- View buffer (observed): 0x5CBC-0x673B, 112 lines x 24 bytes, row table 28975; copied by 0xA38D (LDI x24 per
  line); 0xA502 clears it.

## Build design (stage 2, route B + option (i); written before the first quick run)
- Game side: original code runs (update, projection = the pick's list, ISR, panel on the ULA) + E1 maths.
  Sites: CALL 0x9EA3 at 0x8599 -> clear the buffer only (it becomes the overlay buffer); 0xA38D in 0x9F19 ->
  publish (camera 27309-27319, world snapshot by DMA, overlay bytes), no ULA write. 0x9F19 itself stays.
- Pacer: each update lands at its original real time (E3 hybrid: CTC timer of game T, renderer time excluded,
  + contention counters; remainder carried).
- Renderer (new, Z80N): a second thread entered from the frame interrupt after the game's ISR (E5 stub keeps the
  ISR on real pages); draws the newest snapshot's area with the camera interpolated by wall time; each update's
  own camera drawn too. Painter's order, spans in the 16 dither patterns (set bit = index colour, clear = area
  paper), sky / ground split by 27391, DDMA fills; hidden Layer 2 bank, flip. World format: own reader from live
  RAM (ScummVM as reference only, GPL: no code copied).
- Palette: index 1-16 + area paper; colour off (player option) = all indices -> the area's ink / paper (original
  look); ISR cycle = same switch with the ISR's attribute. Placeholder until the user's palette.
- Overlays: cursor 0xCEAF / 0xCF39 and XOR marker -> hardware sprites; printer, menu arrow, boxes, transition,
  portcullis -> written bytes opaque in Layer 2 (buffer bits, original ink / paper); non-view screens -> Layer 2
  and sprites off. Anything unknown keeps the original ink.
- Memory: game RAM only at sites; renderer, snapshots, tables in own Next pages at slots 0-1 while it runs; hooks
  altrom. R restored on each thread switch (patch.preserve-r); OUT 254 at 0xC821 / 0xC117 / 0xB374 at 3.5 MHz.
- Milestones: M0 host port, M1 Z80N renderer bit-exact + T per view (target >= 12.5 fps outdoors): both PASS
  (below). M2 early integrated NEX:
  update-camera views in colour, no tweens; JNext + user's hardware. M3 tweens, overlays, sprites, switch,
  sound; differential test at every site (PLAYBOOK 6), pacer vs E3, 20,000-frame quick run.
- M0 PASS 2026-11-19 (castle_master_work, local): Python port m0_pipeline.py (m0_geom / m0_cube / m0_objects /
  m0_sort, each with failing mutants) gives the raster's input from the block-start RAM alone = the game's at
  all 5,233 redraws (44,594 polygons). Data: m0_states.bin (RAM per redraw).
- M1 PASS 2026-11-19: cmr.asm (Z80N, 8.5 KB; code 0x0000-0x3FFF, work 0x4000-0x69FF, world = the game's
  0xC000-0xFFFF in place; templates 27486, sin-cos 29337, panorama 30660, bolt 31085 copied at init). Geometry =
  the game's sorted list + full count at all redraws (m1_gate.py), sweeps in camera reach (m1_unit / m1_unit2),
  6 / 6 mutants. Raster spec m1_raster.py (0x9EA3 = clear 0xA3F4 + filler 0x9484 + span 0x9696) = the game's
  view buffer at all redraws (3,766 without a clear, 30 of them with stale pixels; lightning forced: 1,047 /
  1,047). cmr.asm -> Layer 2 (rows 0-112 = lines 32-144, x 32-223, MMU slot 4; byte = 2 x code + the original
  bit; code 0-15 face colour, 16 + c sky / ground, 32 band, 33 bolt: the palette decides colour / original /
  flat) = the model per pixel at all 5,233 (m1_raster_gate.py), lightning forced, 4,000 sweeps
  (m1_raster_unit.py), 17 / 17 mutants (geometry 8 / 8). Deliberate difference: the bolt is clipped to the view (at pitch 4 the
  original's 255-row bolt overwrites its RAM 20343-30056).
  T per view (Z80 timing; no 28 MHz wait states): median 810k; cleared views median 855k (1.53 frames at 28
  MHz), 90 % 1.52M, max 2.05M (12.5 fps = 2.24M); any view max 2.82M; first version 994k / 1.09M / 1.84M /
  2.53M. Speed: PUSH fill (spans >= 16 pixels, clear rows; 5.5 T a pixel, SP in Layer 2, interrupts on: safe
  only if an interrupt entry writes just its return address at SP - M2 stub switches stacks first; --irq sweep
  66,832 injected); filler in registers; sort results cached per pair (the order cycles; s_mat needs zeroed
  RAM at init). Left (m1_prof / m1_worst): span setup ~530 T x 357, projection, sort loop; DMA on hardware.
  For M2: views without a clear keep the last picture -> copy the shown bank's view into the hidden one first;
  bolt column = the game's R mod 20 (cosmetic input).
- M0 side checks (m0_misc.py, all frames): raster callers 0x8599 (5,281) and 0xB62C (108: re-raster of the same
  list + copy, from 0xB40B / 0xB41B / 0xB447); 0xA0A0 / 0xC539 unreached. ROM: never executed, no real reads (only
  simulator artefact reads of 0x0000): slots 0-1 are free for the renderer, the ISR stub needs no ROM.
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
- 2026-11-19, stage 1 close + stage 2 start, ~90 min, ~40 tool calls, 6 user rounds: option (i) trial fixed
  (cursor, cycle, text), design approved (route B), build design written.
- 2026-11-19, stage 2 M0 (host port of the renderer), ~3 h, ~90 tool calls, 4 user rounds: matrix, all object
  builders, clipper, sector cull, sort ported; end-to-end gate PASS at all 5,233 redraws.
- 2026-11-19, stage 2 M1 geometry (Z80N), ~2 h, ~45 tool calls, 1 user round: cmr.asm = the game at all
  redraws first run; sweeps + 6 mutants; raster read.
- 2026-11-19, stage 2 M1 raster, ~2.5 h, ~50 tool calls, 0 user rounds: model = the game's buffer, Z80N = the
  model per pixel, at all redraws; sweeps, 11 mutants, T per view. Then speed (user: "Speed up M1 first"),
  ~1 h, ~20 tool calls: profile, PUSH fill, filler in registers, sort cache: -19 % median, worst outdoor view in budget.

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
- [local: one engine port; PLAYBOOK 3d candidate if a second renderer is ported] Port stage by stage against
  the game's own data at fixed PCs, each with a failing mutant, then gate end to end on every redraw: a missed
  stage (sector cull 0x8D4F) showed as one cube in one frame of 5,233, which a sample run would have missed.
- [local: one engine port] Random sweeps must stay in the inputs' domain (camera words <= ~16,000; pitch an
  angle 0-71): beyond it 16-bit sums wrap or the original reads 2.5 KB past a table, and failures are false (22
  of 5,000; 1 of 4,000). Size copied tables by the domain, not the recording (bolt: 688 bytes at pitch 4, 172
  recorded). A mutant can be equivalent (sign bit 46 vs 47 of a dot < 2^45): replace it, don't count it.
- [local: one engine port; PLAYBOOK 3d candidate] Forcing an input the recording never has ((27391) = 0,
  lightning) found an original bug: at pitch 4 a 255-row bolt overwrites RAM incl. the face list. A renderer
  drawing into its own pages must not copy that: make it a model option (bolt clipped) and record it.

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
- scratch: [local: cmdis / callers helpers stay in the session scratchpad; cm_profile / cm_consumers,
  e1-e5 and m0 / m1 scripts are local (castle_master_work): the engine's own verifier at stage 3]
