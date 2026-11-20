# Castle Master (Incentive Software, 1990; 48K, Freescape) - stage 0 intake done, stage 1 design approved

## Next session
Stage: 2 (build)             State: M3b (overlays) PASS in simulator + JNext; rest of M3 open
Inputs: C:\1NEXT\castle_master_work\castle_master.z80 (extracted from the RZX), C:\dev\castlemaster\castle.rzx,
C:\dev\castlemaster\Castlemaster1.tap    Branch: add-castle-master    Commit: (this file's commit)
Checks: survey --stop 15000 (castle_master_survey/), survey full run (survey_full/), scan of the view buffer (3,000 frames)
Decision (user 2026-11-19): route B (Next-native renderer) + option (i) (Layer 2 on top, dither kept, cursor =
sprite, cycle = palette); colour switchable off by the player (original look). Later: palette 1-16, flat mode.
Start with: M3b on hardware (castle_master_m3b.nex, local); then the colour cycle as palette + the
switch, the M3b block's "Open" list
Read: PLAYBOOK stage 1 + 3d; cards detect.pacing-structure, detect.routine-removal, patch.hybrid-display-replacement
Open: unreached CALL sites (Coverage); K on hardware (6.75 = JNext); heaviest outdoor view ~10 views a second: DMA

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
- Consequence (confirmed by M3a): one move or turn step per update; a faster render alone = faster walking
  in real time, so the update's original time is kept and the freed time draws in-between views.
- Sound: OUT 254 at 0xC821 (20,932, in 39 updates), 0xC117 (195), 0xB374 (16) - check which run inside render
  code before any speed-up (patch.timed-side-effect-replay).
- Colour source: (29501) = the face's colour index 1-16 per span; table 53825 = 16 four-line dither patterns (1
  empty, 2 and 11 solid); the filler ANDs / ORs the pattern into the buffer. Layer 2 takes the index per span.
- Pipeline costs (15k frames): 0x8D4F sectors 2k T, 0x9776 12k, 0x9D8A sort median 42k (max 662k), raster
  (clear 82k + fill ~41k) 17.5 % of all T, copy 52k; walking ~2.4M T a step, maths ~20 %, no wait anywhere.
- Camera (observed, cm_profile at each 0x9776): x, y, z = 16-bit at 27309, 27311, 27313 (start 928, 96, 8032;
  y = eye height); pitch 27318, yaw 27319, both mod 72 (5 deg); a turn = 2 units (10 deg); a walk step ~238 units
  ((+206, -120) at yaw 24). 27315 / 27317 = 0xF0 (unknown, constant so far).
- DMA / DDMA evaluation (docs/DDMA.md; estimates): clear -> DDMA 2D fill (fallback zxnDMA fill; CPU); spans
  -> DDMA above a crossover width (M1: PUSH fill); copy 452k T -> DMA / DDMA; gating per DDMA.md 3 (core >=
  3.03.00 for DDMA, zxnDMA otherwise, CPU-only option HLIB_NO_BLITTER / HLIB_CPU_ONLY). Not built yet.
- Render consumers (probe cm_consumers, 3,000 frames; window 0x9776 .. 0x859F, ISR excluded): game code
  outside reads the projected polygons / display list 0x6754-0x68xx (0xB708-0xB7BE, 0xBA42-0xBA60: inferred the
  crosshair pick = gameplay; 0x9495-0x952B / 0x9EDA-0x9EEC: the second draw path 0xB62C from 0xB40B / 0xB41B /
  0xB447), flags 0x733E, 0x7353, 0x7377, the screen (printer, 0xCF39). So the game's own update incl.
  projection stays, in game RAM; in-between views never feed the pick.
- Raster stage alone (skip_*.log, taint_8599_full.json; all frames, 5,281 calls): the only raster-written
  bytes read outside it are the view buffer, by display code (copier 0xA3A6, copies 0xB6C2 / 0xD1B1, printer,
  masked overlay 0xD134, XOR marker 0xCF53) and the filler itself: display-only (observed). routine_skip:
  0x9F19 is not a pure copy (game variables differ): keep it. Filler overruns to 0x6752. Format reference:
  ScummVM's Freescape engine (GPL: reference only).
- Design history (2026-11-19): span hook; original at 28 MHz + E1; route A (sandbox in-between cameras); route
  B (Next-native renderer) CHOSEN. Buffer readers draw INTO it (user's correction) -> option (i) each to Layer
  2 (chosen); (ii) ULA over Layer 2 (unsolved for white paper).
  R (static): ISR LD A,R 49291 / 49342 = blink delays (cosmetic); 0x9F6E: 27391 = (R AND 63) + 10, an event
  countdown (gameplay; patch.preserve-r); 0xA569: R mod 20 -> 41970 (display).
- E1 PASS (e1_maths.asm, e1_check_full.log): Z80N 0xA1FD (A*HL), 0xA253 (HL*DE), 0xA348 (H*L) with MUL D,E;
  0xA2C1 (AHL/DE) = restoring division unrolled. All 682,956 unique inputs of 1,827,355 recorded calls +
  100,000 random each, edges: registers, flags, memory equal. T per call 554 -> 273, 489 -> 228, 2,078 -> 904,
  238 -> 110: maths 9.7 % -> 4.5 % of the recording's T. 4 mutants FAIL (Lessons).
- E2 (route A sandbox, not chosen), E3 (time model), E5 (ISR redirect): PASS, superseded by M2 / M3a.
- E4 (e4_overlays.py, e4_full.log; all frames, writers by PC): view on screen = pixel lines 32-143, columns
  4-27, attribute rows 4-17. Straight onto the screen view: cursor / crosshair 0xCEAF / 0xCF39 (1,829 frames),
  menu pointer 0xCB00 / 0xCB3B / 0xCB63, a second buffer -> screen copier 0xB6C3 (244), masked sprite
  0xD0F9-0xD146 + restore 0xD1B1 (the opening portcullis). Into the buffer: XOR centre marker 0xCF54-0xCF68
  (175), printer 0xCA97-0xCC16 (151), transition 0xCA42 (12), boxes 0xBC9F-0xBD34 (6). Attributes: area colours
  0xB368 (some WHITE paper), ISR 0xC069 colour cycle (4,977 frames: one value to all 336 cells, table 49168).
  Option (i) trial (opt1_trial.py; user: KEEP the dither): Layer 2 pixel = buffer bit set ? the face's colour :
  the area's paper; cursor = sprite, ISR cycle = palette; overlays / unknown writers keep the original ink.
- View buffer: 0x5CBC-0x673B, 112 x 24 bytes, row table 28975 (0x9DC9-0x9DF8 also puts scratch 24369-24382 in it).

## Build design (stage 2, route B + option (i); written before the first quick run)
- Game side: original code runs (update, projection = the pick's list, ISR, panel on the ULA) + E1 maths.
  Planned: a CTC pacer + renderer thread, world snapshot by DMA; built synchronous (M3a), the game's raster kept.
- Palette: index 1-16 + area paper; colour off (player option) = all indices -> the area's ink / paper (original
  look); ISR cycle = same switch with the ISR's attribute. Placeholder until the user's palette.
- Overlays: hardware sprites over Layer 2 (M3b); non-view screens -> Layer 2 and sprites off.
- Milestones: M0 host port, M1 Z80N renderer bit-exact (>= 12.5 fps outdoors), M2 integrated NEX (no
  tweens), M3 tweens, overlays, switch, sound; differential test at every site (PLAYBOOK 6).
- M0 PASS 2026-11-19 (castle_master_work, local): Python port m0_pipeline.py (m0_geom / m0_cube / m0_objects /
  m0_sort, each with failing mutants) gives the raster's input from the block-start RAM alone = the game's at
  all 5,233 redraws (44,594 polygons). Data: m0_states.bin (RAM per redraw).
- M1 PASS 2026-11-19: cmr.asm (Z80N, 8.5 KB; code 0x0000-0x3FFF, work from 0x4000, world = the game's
  0xC000-0xFFFF in place; templates 27486, sin-cos 29337, panorama 30660, bolt 31085 copied at init). Geometry =
  the game's sorted list at all redraws (m1_gate.py), sweeps (m1_unit / m1_unit2). Raster spec m1_raster.py
  (0x9EA3 = clear 0xA3F4 + filler 0x9484 + span 0x9696) = the game's view buffer at all redraws; cmr.asm ->
  Layer 2 (lines 32-144, x 32-223, MMU slot 4; byte = 2 x code + the original bit; code 0-15 face colour, 16 +
  c sky / ground, 32 band, 33 bolt: the palette decides colour / original / flat) = the model per pixel at all
  5,233 (m1_raster_gate.py), lightning forced, 4,000 sweeps, 17 / 17 mutants; bolt clipped (Lessons). T per view:
  median 810k, cleared views 90 % 1.52M, max 2.82M. PUSH fill (spans >= 16 pixels, clear rows; SP in Layer 2,
  interrupts on: an entry may write only its return address at SP), filler in registers, sort cache.
- M2 PASS in the simulator + JNext 2026-11-19, on hardware (user): runs well, about the original's pace
  (castle_master_work: cm2_glue.asm in cmr.asm, m2_lib / m2_sim / m2_build / m2_jnext / m2_mutants). The game's
  raster and copy STAY (ULA = the original); Layer 2 over the view (clip window). Sites: 0x855E h_geom, 0x8599 /
  0xB635 h_rast, 0x859C h_show ((0x7349) = 0: palette from (27353), flip NR 0x12; else Layer 2 off), 0xB638
  h_flip, 0xFDFD JP isr_e. Hooks = alt ROM 0x386E, the same bytes in the renderer's page; pages 32-33 code
  (slots 0-1, never written: stock simulator), 34-35 work, Layer 2 banks from 18. State switch under DI (~140 T
  at 28 MHz). Interrupt in the renderer: isr_e = JP isr_full there (alt ROM: JP to the handler): game stack,
  pages 10 / 11 / 4 / 5 back, CALL 0xC01F (cur54 / cur55 written before each NEXTREG). No clear and no
  full-screen record -> the last view copied first (LDIR, 452k T). m2_sim: all 5,233 redraws with interrupts =
  the model per pixel; without (every 10th) registers but R and ALL game RAM = the original's; 9 / 9 mutants
  FAIL. JNext: renderer per redraw 1.3 / 4.2 frames median / max.
- M3a PASS in the simulator + JNext 2026-11-19 (cm3_glue.asm, m3_sim / m3_jnext / m2_build --prefix cm3;
  castle_master_m3.nex): original pace + in-between views, synchronous. The game's block 0x855E .. 0x859C (its
  geometry, raster, copy: buffer and ULA stay whole) runs at 28 MHz in a pace window (hlib_pace's clock; state
  = 40 bytes of the IM 2 table at 0xFE40, never read by the CPU, zeroed in the image); original time = K x its
  28 MHz time (K 6.75 in JNext) + the handler's lines a call (measured in the block) over the original's frames;
  views and waits count real lines (handler incl.). Main-line speed in a variable written before each NR 7: the
  plain wrapper restores it (an interrupt in r_enter came before the window). h_show then draws in-between views (camera linear from the last view; yaw /
  pitch in 1/8 units: sin / cos between table entries, horizon 11 rows a unit, panorama by bytes) while they
  fit before the final view, draws that from the inputs saved at 0x855E / 0x8599, waits for the target, flips
  outside lines 30-143. Three Layer 2 banks (shown, drawn, last final = the copy's source). Handler and sound
  0xC683 (sites 0xC68B, 0xC7F2) at 3.5 MHz, their time out of the window, as the 14 waits on the handler
  (LD A,(0x7377 / 0x734A) / OR A / JR cc: 6-byte sites); printer ticks at entry and exit (sites 0xCA4E,
  0xCBFF: its DI spans a whole string); main-line readings commit with interrupts off and read again if an
  interrupt came during them; the window opens with interrupts off; non-view screen:
  wait, 3.5 MHz, Layer 2 off, 0x9F19. No in-between view: area change, a step >= 1024, a turn > 8 units, a
  redraw without 0x855E.
  m3_sim (interrupts, line counter, planted previous camera): all 5,233 redraws = the model per pixel; pace on
  the same game path (5,218) median +0.24 frames, -0.49 .. +2.08; 15 on another path (-2.2 .. -0.9); without
  interrupts (every 5th): registers but R + game RAM = the original's. JNext: 7 updates end within 0.2 frame of
  the plain conversion; 8,000 frames clean; views a second in a moving update: median 11.5-29 (two runs), 10 %
  10, 90 % 31-36; an indoor turn = a view every frame. 14 / 14 mutants FAIL (m3_mutants.py; K-N at given
  states / phases).
- M3b PASS in the simulator + JNext 2026-11-20 (castle_master_m3b.nex): 84 sprites over Layer 2 (12 x 7 of
  16 x 16, 4-bit; palette 1 = the area's paper, 2 = ink), opaque where the screen differs from the raster's
  output (ov_s: the buffer at the copy, marker out), ink where its bit is set. Hardware run 1 (photos): whole
  bytes made the marker a dither block; the printer (0xC0F9, handler) writes the buffer between views, never
  copied: cursor blocks. Built around the copy at the show sites and after the cursor's draw / restore
  (0xCDD2 / 0xCECD; rows in 8 bits). Sprites go with Layer 2; the dissolve
  0xB66E (9 calls under Layer 2: 0xBCE5, 0xCA44) now turns both off. Hooks from 0x3600 (m3b_rom.py). m3_sim:
  all 5,233 redraws incl. the overlay per pixel, stale sprites planted, the cursor at 40 positions (recorded
  domain) after every 10th view; m3b_seq.py (the build's overlay code along the recording: 5,357 views, 3,670
  cursor moves); m3b_diss.py; m3b_race.py (MMU reads under DI); 10 / 10 mutants (O-X). Pace (same path)
  median +0.59 frames, max +2.41 (M3a +0.24: the overlay work). Open: overlay time, colour cycle, switch, DMA,
  R, K on hardware, the first ~4 frames of an update stay still, the IM 2 bus value on hardware (0xFF assumed).
- M0 side checks (m0_misc.py): raster callers 0x8599 (5,281), 0xB62C (108, the same list again); ROM unused.
## Coverage (survey GATE, 15,000 frames)
Unreached CALL sites: 0xD028 (2/3), 0xCA4E (17/18), 0xB66E (2/6; 48357 not reached). All text / panel / area
pictures, no figure plotter.
Full run (survey_full/, all 167,135 frames, no desync): GATE OK; 0xCA4E 18/18, 0xB66E 4/6, 0xD028 2/3, 0xB347
4/6 reached; 5,356 view copies. No further recording needed for stage 1.

## Stage log
- 2026-11-19, stages 0-1 (intake, survey, pacing census, DMA / DDMA, experiments E1-E5, option (i) trial, a
  separate removal + taint session), ~11 h, ~300 tool calls, ~22 user rounds: design approved (route B).
- 2026-11-19, stage 2 M0 (host port), ~3 h, ~90 tool calls, 4 user rounds: gate PASS at all 5,233 redraws.
- 2026-11-19, stage 2 M1 (Z80N geometry + raster, then "Speed up M1 first"), ~5.5 h, ~115 tool calls, 2 user
  rounds: = the game at all redraws; sweeps, 17 mutants; PUSH fill, sort cache: -19 % median.
- 2026-11-19, stage 2 M2 (early integrated NEX), ~3 h, ~60 tool calls, 0 user rounds: hooks + interrupt stub,
  host integration test at all redraws, 9 mutants, NEX, JNext 8,000 frames. Whole-module read: z80tonex.py
  (stub, tail, alt ROM fill: the build's memory plan depends on all three).
- 2026-11-19, stage 2 M3a (pace + in-between views), ~7 h, ~200 tool calls, 6 user rounds (hardware: M2 runs,
  original pace; "Start M3"): block probe (sound, printer, waits), cm3_glue.asm, host test, NEX, JNext.
  Whole-module read: asm/lib/hlib_pace.asm (the clock's rules decide where ticks must come from).
- 2026-11-20, stage 2 M3b (overlays), ~6 h, ~170 tool calls, 2 user rounds (photos): sprite grid, cursor /
  dissolve sites, host test, cursor sweep, sequence test, 10 mutants, NEX, JNext.

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
- [doc docs/TECHNIQUES.md §1.0 Measured costs on a board (tools/hwtests/nextbench, core 3.02.00, 2026-10-22)] Simulator T is not 28 MHz time: JNext ran the renderer at 1.34-1.42x
  (wait states), which moved the worst outdoor view from "in budget" to ~10 fps. Budget from T x 1.4.
- [local: one engine's thread switch; a card candidate if a second engine runs code in its own pages] An
  interrupt-safe state switch the stock simulator can check: write nothing in slots 0-1; the vector jumps to
  one address whose code differs between the alt ROM (JP handler) and the renderer's page (restore pages,
  stack, speed, CALL handler); every NEXTREG that changes a page is preceded by its variable's write.
- [local: one harness] A control that saves, clobbers, then restores is no control (HL'), and one on a rare
  path (stale-pixel copy: 30 of 5,233 views) needs its own direct check, or it passes.
- [local: one build's start-up; a z80tonex note candidate] setup_call runs with the stub in slots 6-7: a write
  to the game's 0xC000-0xFFFF there lands in the stub's bank. The host harness poked the same bytes, so only
  JNext showed it (the clock ran on table bytes). Put start-up state in the image (patch.apply): the boot check
  then covers it.
- [local: one engine's clock; an hlib_pace candidate if a second engine paces windows over 13 frames] Two
  line readings one frame apart (handler to handler) differ by 0 or 311 by jitter: a tick taken only in the
  interrupt wrapper lost half the frames. Rule: after a reading at an interrupt, a difference under half a
  frame is a frame more. hlib_pace_wait's target is 16-bit sixteenths (13 frames): longer windows need their
  own wait in lines. A long interrupts-off span (sound, 0.5 s) must be ticked before and re-read after, not
  held (hold / resume are modulo a frame). The game's waits on its handler inside the window are real time:
  14 loops found by their byte pattern after redraws showed +28 frames late. An interrupt that skips its
  reading (a main-line one under way, the window half open) loses a frame: let it read; commit main-line
  readings with interrupts off, reading again if one came (-6 frames in 3 of 5,233).
- [local: one engine's pace gate; a hooklib / probes candidate] A pace check against the original from the same
  state can fail for the right build: the game reads real-time state (message printer: 15,000 instructions in
  the original's block, under 200 in M3's). Count the game's own main-line instructions (sites, handler, the
  vector's JP and the renderer's work-RAM code apart) and gate pace only where both runs took the same path.
- [local: a harness trap; a probes candidate] SkoolKit's Simulator applies the LD A,I / R quirk (P/V 0) on its
  own 48K frame, not the harness's interrupts: HLIB_IFF_DI then left interrupts off at random (a hang once a
  clock call ran ~100 times a frame). Set int_active 0; clear P/V where the harness accepts an interrupt.
- [local: one harness; a probes candidate] Per-state runs start from clean hardware: "rebuild stale sprites" /
  "sprites off" mutants passed until a previous view's sprites were planted. For edge cases the states rarely
  reach, drive the game's own routine at swept inputs (found an 8-bit wrap at the cursor's bottom edge). A
  per-redraw gate missed what hardware showed at once: also run the build's code along the recording.

## Technique use
- detect.pacing-structure: helped: pacing_census on the main loop 0x8542 showed event-driven renders of 2-52
  frames and no frame wait, which set the speed question.
- patch.preserve-r: used: found the gameplay R read (0x9F6E -> 27391) that every sandbox render must restore;
  the ISR's R reads are cosmetic (E5: 229 blink-delay bytes).
- detect.routine-removal: helped: the consumer probe (cm_consumers) found gameplay reads of the projected
  polygons, which ruled out replacing the game's own redraw with a tween.
- patch.hybrid-display-replacement: used (M2): original logic and producers run, the view goes to Layer 2.
- patch.iff-safe-read: used: HLIB_IFF_DI / _EI around both state switches. patch.restore-speed: adapted: the
  latch is in paged work RAM, so the speed is read before the switch and stored after it (own code, same rule).
- patch.isr-deferral: no help: the handler runs at once, on the game's stack with the game's pages.
- patch.pace-limiter: used: hlib_pace's clock (open, tick, hold / resume) in a K window around the game's
  own redraw; own wait in lines and an interrupt-side tick (Lessons). patch.timed-side-effect-replay: used:
  the probe of the block found sound 0xC683 and interrupt waits inside it before the speed-up.

## Friction
- reuse: [tool tools/probes/pacing_census.py] used as it is; `nexclash.py cost` too
- retries: [local: a helper named dis.py shadows the stdlib `dis` (twice); heredoc-written Python loses its
  backslash escapes (use a file); a C-simulator run without interrupts never returns from a wait loop;
  JNext screenshot names count from the start line, log F from power-on (500 apart here)]
- environment: [none: local Windows checkout, no workarounds needed]
- hand-rolled: [local: byte searches for CALL / LD (nn) sites with skoolkit's snapshot reader]
- scratch: [local: cmdis / callers helpers stay in the session scratchpad; cm_profile / cm_consumers,
  e1-e5 and m0 / m1 scripts are local (castle_master_work): the engine's own verifier at stage 3]
