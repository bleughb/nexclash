# Castle Master (Incentive Software, 1990; 48K, Freescape) - stage 0 intake done, stage 1 question open

## Next session
Stage: 1 (design)            State: intake 2026-11-19; the design question is with the user (Pending below)
Inputs: C:\1NEXT\castle_master_work\castle_master.z80 (extracted from the RZX), C:\dev\castlemaster\castle.rzx,
C:\dev\castlemaster\Castlemaster1.tap    Branch: add-castle-master    Commit: (this file's commit)
Checks: survey --stop 15000 (castle_master_survey/), survey full run (survey_full/), scan of the view buffer (3,000 frames)
Pending user answers: final design approval (route A first, agreed 2026-11-19, if E5 passes); buffer-reader
option (i) / (ii); the colour palette for indices 1-16
Start with: E1-E4 (E5 passed 2026-11-19, Feasibility); E2 adds: no DMA in flight when the stub runs
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
- Tween isolation idea (inferred, to prove): after each game update, DMA-copy the 48K RAM to a sandbox bank set;
  tween views run the original renderer there (MMU-mapped, the game's ISR held off or redirected) with an
  interpolated camera: game RAM cannot be written by construction. Position: linear between the old and new
  27309-27313; turning: the matrix builder 0x9776 in the sandbox fed a finer angle (own sine table) since 72
  steps give only one in-between angle per 10-deg turn. Pace: the game update + final view must land when the
  original's would: the original's duration is its render T, so measure it by running the original path and
  scaling (or a T model per polygon / span); card patch.pace-limiter. Open: renderer side effects (OUT 254 at
  0xC821 in 39 updates, ISR attribute writes, the panel 0xB3xx), the removal / isolation experiment.
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
- Proposed design (for approval, not built): (a) colour: span hook writes (29501) indices to Layer 2 (hidden bank,
  flip), palette per index (the user's choice); clear by DDMA 2D fill; the buffer copy and the ULA view removed;
  panel stays ULA (Layer 2 window over the view only, the ISR's view-attribute flashes mapped to a Layer 2 palette
  effect). (b) speed: game updates run the original code at 28 MHz with MUL-based multiply / divide where they
  match bit-exactly; each update's final view is the game's own render. (c) smooth view: between updates, the
  sandbox (DMA copy of RAM after each update) renders in-between cameras (position lerp, finer yaw / pitch) into
  Layer 2 while the update waits out the original's duration (pace ORIGINAL per update). (d) DMA policy:
  DDMA on core >= 3.03.00, zxnDMA fill / copy otherwise, CPU-only option; crossover for span fills measured on
  hardware. Experiments before build: E1 MUL routines bit-exact vs 0xA1FD / 0xA253 / 0xA2C1 over all recorded
  operands; E2 sandbox render of an unchanged camera = the game's own frame, byte for byte; E3 a T model of the
  original per update (needed for pacing) within 2 % of the recording's frames per update.
  Revised after the raster removal + taint results above (2026-11-19, still for approval):
  (a') the span hook goes in the filler (0x9696 path), so all four 0x9EA3 callers (0x8599, 0xA0A0, 0xB635,
  0xC539) are covered; its bounds follow the filler's real extent (to 0x6752), not the buffer's. 0x9F19 stays
  (it changes game variables: skip_859C 25 / 462 differ); only the 0xA38D copy's screen writes are replaced.
  Scope (user, 2026-11-19): "display-only" holds for the paths the recording takes; branches it never takes and
  what the raster writes into the copier's code page 0xA3 are unchecked (taint notes above) - not "measured" in
  general.
  Buffer readers (printer 0xCAA2 / 0xCAFC, masked overlay 0xD134-0xD142, XOR marker 0xCF53-0xCF67, copies 0xB6C2 /
  0xD1B1): the text, marker and overlay are drawn INTO the buffer, so keeping the buffer alone does not show them
  once its copy to the screen is replaced (correction by the user; the earlier "dual write" option was wrong).
  Options: (i) move each to Layer 2 (more hooks); (ii) user's idea, untested: leave the faces out of the buffer,
  keep the buffer's copy to the ULA, ULA over Layer 2 with the view's paper see-through - overlays stay visible
  through every view, no extra hooks. To work out for (ii): the per-area paper colours (one transparent colour,
  NR 0x14, vs a ULA palette entry shared with the panel), the ISR's view-attribute flash writes (0x5884, 24 x 14),
  ink pixels the faces used to supply (none left in the buffer: the view is paper + overlays). E4 checks which
  readers are active in play.
  (c') tween source, two routes (the user asked about B; not decided): A = the sandboxed original renderer
  (exact look, original speed per view x 28 MHz); B = a Next-native renderer (own camera, pages, reads the world
  data; the raster is display-only, so the game's own update + projection still runs for the pick and the
  pace). B can use finer angles, MUL, DDMA spans freely and leaves the original untouched, but a second renderer
  must match the original's look (faces, clipping, sort order) closely enough that the switch from tween to the
  game's own view does not jump. E2 becomes: A - sandbox at an unchanged camera = the game's frame byte for byte;
  B - native view at an update's camera vs the game's own frame, polygon colour per pixel, with a mismatch bound.
  Corrections (user, 2026-11-19): route A's untested risk: while the original renderer runs in the sandbox for
  100 ms or more, the game's ISR must still run on the REAL memory every interrupt, or the real-time clocks
  (29559, 27407 / 27408 / 27411) slow and gameplay changes; holding it off is not an option, redirecting needs its
  own experiment (E5). Route B's jump risk is avoidable: since the raster is display-only (recorded paths), the
  native renderer can draw every view including each update's final one - no switch, no jump; what remains is a
  pixel-level difference between what is shown and what the crosshair pick (the game's own projection) hits.
  Decision (user, 2026-11-19): route A first is reasonable on effort and risk, provided E5 is tested early -> E5
  runs first.
  E5 (new, first): ISR redirect during a sandbox render. Every interrupt taken while the sandbox is mapped must
  run the game's handler 0xC01F on the real pages (slots 2, 3, 6, 7: its reads / writes, the ULA attributes it
  flashes, OUT 254) and return to the sandbox unchanged. Questions: a stub that is mapped in both worlds (the ISR
  never touches slots 1, 4, 5; the renderer's own use of slots 0 / 1 to check); a stack for the handler outside
  the remapped pages; R (the handler reads it at 49291 / 49342: patch.preserve-r); interrupt timing at 28 MHz.
  Success: in a simulator with two memories (sandbox / real), injecting sandbox renders between updates leaves the
  real RAM at every update entry identical to the unmodified replay, and the handler runs once per frame.
  E5 groundwork (probe cm_slots, 3,000 frames; observed): render window (ISR excluded) reads slots 2-7, writes
  2-7 (most: 2 = view buffer + vars, 7 = stack + vars), never slots 0 / 1. ISR: reads slot 0 (2,820, ROM), 2, 3,
  6, 7; writes 2, 3, 6, 7; runs code in pages 0xC0-0xC1, 0xCA-0xCC (the printer 0xCA4E: it prints from the ISR)
  and 0xFD (vector JP). So a redirect stub and the handler's private stack fit in slots 0 / 1 (alt ROM / a RAM
  page in slot 1), mapped in both worlds; the ISR's slot-0 reads must still see the ROM bytes there (check which
  addresses). Sketch: sandbox copy's 0xFDFD JP -> stub: save SP, own stack, MMU slots 2, 3, 6, 7 -> real pages,
  CALL the real handler (its RETI returns to the stub), MMU back, SP back, EI, RET.
  R (observed, static): ISR LD A,R at 49291 / 49342 = random blink delays 49173 / 49175 (512 + 2R frames) for
  screen bytes 0x4CA2 / 0x47BD, used only in the ISR: cosmetic. Game: 0x9F6E (in 0x9F49, called from 0x6A99):
  27391 = (R AND 63) + 10, a countdown read by the redraw trigger 0x8583, 0xA45C and the ISR 0xC123 = gameplay
  event timing; 0xA569 (from 0xA4D3, clear code): R mod 20 -> 41970 (display, inferred). So every sandbox render
  and hook restores R (patch.preserve-r); the ISR's cosmetic R reads during a sandbox render differ (accepted?).
  Interrupts land at other points of the update at 28 MHz + pacing than in the original: equivalence is
  "extremely close", not 1:1 (owner 2026-11-10); E5's real-RAM check compares at update entries with that rule.
  E5 RESULT (2026-11-19, harness castle_master_work/e5_isr_redirect.py, logs e5_full.log / e5_full_noslot7.log):
  PASS. Per interrupt the RZX takes inside a redraw window (where hardware would be running the sandbox), a Next
  MMU model with real pages 10, 11, 4, 5, 0, 1 and sandbox pages 32-37 (= RAM at that redraw's start, camera
  moved, all 18 ISR variables altered, 0xFDFD JP -> stub): IM 2 acceptance in the sandbox, stub at 0x2000 (slot
  1): LD (0x82C0),SP / LD SP,0x8400 / NEXTREG 0x52,0x53,0x56,0x57 -> real / CALL 0xC01F / DI / NEXTREG back /
  LD SP,(0x82C0) / EI / RET. All 167,135 frames: 79,705 of 79,705 cases pass C1 (real RAM = the recording's own
  handler result, dead stack below the interrupted SP excluded), C2 (sandbox unchanged but the return address
  and the stub stack 0x82C0-0x8400, never touched by the game), C3 (all registers but R / T, IFF, MMU back). Stub
  cost 245 T (3.5 MHz T; ~9 us at 28 MHz) per interrupt. R: 229 blink-delay bytes (49173-49176) differ across
  the run - cosmetic (the stub's own R increments), accepted pending the user. Negative controls (900 frames,
  20 cases each): no remap -> 20 FAIL (C1 + C2); slot 6 not remapped -> 20 FAIL; slot 3 -> 20 FAIL; slot 2 ->
  2 FAIL (only interrupts that flash the view attributes); SP not restored -> 20 FAIL (runaway). Slot 7 not
  remapped passes all 79,705 (full run): on the recorded paths the handler uses slot 7 only for its stack (now
  the stub's) and the IM 2 vector (read in the sandbox, same bytes) - kept in the stub anyway for unrecorded
  paths (40 T). Not covered: real hardware MMU / interrupt timing, an interrupt during the stub's own DI window
  (none can arrive: the handler runs far past the /INT pulse), DMA in flight during the redirect (the design
  must finish or pause sandbox DMA before the stub - check in E2), the sandbox renderer's own DI periods
  (interrupt latency), branches the recording never takes.
  E4 (new): which display readers of the buffer are active in play (overlay, marker, printer in the view), from
  the taint result's reader PCs per frame, to choose dual write or Layer 2 per reader.
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
- 2026-11-19, E5 (ISR redirect), ~90 min incl. a 75-min full run, ~25 tool calls, 2 user rounds: corrections
  recorded, slot / R groundwork, harness + 5 negative controls, full-recording PASS.
- 2026-11-19, separate session (removal + taint of the raster stage), ~60 min, ~25 tool calls, 3 user rounds: six
  routine_skip runs, a taint probe over the full recording (castle_master_work/taint_call.py).

## Lessons
- [doc docs/RECORDING_CHECKLIST.md §Making a recording (Fuse)] An RZX alone (no separate .z80) is a complete intake: `nexclash.py rzx extract R -o
  GAME.z80` gives the snapshot it was recorded from (here a .tap came with it, not needed for a single load).
- [local: one game's misread; the survey reports what the copier reads] The survey's buffer range (0x5C80-0x673F, rounded) mixed the view buffer with renderer variables, so
  `scan --writers` on it listed geometry code first; the copier's own pointer (LD HL,23740 at 0xA39A) gave the
  exact buffer.

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
  Castle Master probes, to move to tools/probes/ if E1-E3 reuse them; e5_isr_redirect.py (local, castle_master_work)
  becomes part of the engine's own verifier at stage 2 (verification harnesses stay per engine)]
