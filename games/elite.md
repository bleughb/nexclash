# Elite (Braben / Bell, Firebird 1985; Russian 128K hack) - engine: elite (in progress, stage 2)

## Next session
Stage: 2 (build)   State: M3 + M3b (ships, planet, stars every frame) run in CSpect 2026-11-23 (## M2 progress); M4 next
Inputs: specnext/reference/elite/ (tape, 5 RZX, 5 extracted .z80)    Branch: add-elite    Commit: see git log
Checks: full surveys of all five RZX (7.5k-68.6k frames); tape not run in an emulator
Pending user answers: none (design closed 2026-11-23: C coloured ships, details 1-5, pacing (i) interpolate)
Start with: `python -m nexclash.elite C:\1NEXT\elite_work\Witch.z80 m2.nex` in CSpect (m3b build), then M4: HUD clash cells, Layer 2 off on pages
Read: PLAYBOOK stage 1, 3d (unknown engine: feasibility first); ## Findings below
Open: see Findings

Inputs from SARD (eliteRZX.txt): Elite.tap + 5 Fuse RZX (Docking, PoliceAnarchy, Havoc, Witch, Reidquat),
"Russian 128k Hack" with a "Mamba MkII" and a new "PuffAdder" ship. No .z80 was sent; each RZX's first
snapshot is the start state (`rzx extract`). Files live in specnext/reference/elite/ only.

## Recordings (checked 2026-11-22 against the full-length survey previews)
Order of play (cash): Docking ends docked at Lave (7186.3 Cr); Havoc, PoliceAnarchy and Reidquat start from that status
page (Lave). Havoc ends docked at Tionisla (7252.3 Cr); PoliceAnarchy ends at Riedquat (7342.8 Cr, rating Competent);
Reidquat ends at Riedquat (7483.2 Cr); Witch ends on the inventory screen ("Alien Items 6t", fuel 3.4 LY, 7215.4 Cr).
So the names match SARD's notes. Frames: Docking 7501, Havoc 54517, PoliceAnarchy 68635, Witch 53371, Reidquat 41969.
Which parts overlap each other is not compared.

## Findings (stage 0; Docking first look, then all five surveyed in full)
- Colour (CORRECTED 2026-11-22: an earlier note called the viewport coloured; the orange / cyan / purple in the survey
  preview.png are its per-plot-routine overlay tints, not the game's colours). Plain renders of Havoc, Witch and PoliceAnarchy
  show: viewport white on black, HUD bars red / white, a condition light (green / yellow / red) and a planet / sun marker
  (red / yellow), status pages cyan text. So the original has almost no colour clash: lines on one attribute colour; the
  only multi-colour areas are the HUD bars and the small icons.
- Render path (disassembly 7FBE-7FE2, PoliceAnarchy snapshot): the game draws into a back buffer at 0xC000 (bank 0, mapped
  and locked at C000 by the 128K hack) and 0xC100; 32717 copies it to the screen at 0x4020 (viewport = 128 lines x 32
  bytes) with LDIR per line (~62k T), 32702 wraps it. About 6.5k copies in 68.6k frames = one screen update per ~10 frames
  (~5 fps), the game's real frame rate.
- Gate over all five recordings: 29993 (0x7529) -> 39117 never reached; 32702 callers 37720, 38122 (and one more of 11) never
  reached; 38113 -> 30872 never reached in Docking (other four 3/4 reached). Mostly code that ran nearby; which are FIGURE
  paths is not checked.
- Pacing: interrupts accepted in about 2/3 of the frames in every recording (e.g. 46005 of 68636): the game runs with DI for
  stretches (back-buffer copy ~125k T, up to 930k T per call).
- Free memory is scarce: PoliceAnarchy leaves 5546 of 32768 bytes untouched in 0x4000-0xBFFF (largest span 456 bytes).

## Open
- Which unreached call sites are figure plotters (cost --at / disassembly); whether another recording is needed.
- Run Elite.tap in an emulator to confirm it matches the snapshots (loader is BASIC + `USR 28672`, packed 40801-byte block at 24648; the bytes differ from snapshot RAM, so it is packed).
- Stage-1 design question and feasibility (3d).

## Feasibility (stage 1, 2026-11-22; measured from the five surveys, basis in brackets)
- Pacing [observed]: one screen update (buffer copy 32702) per ~10 frames, so ~5 fps, set by the game's own CPU work
  (line drawing of ships, planet circles, scanner), not by a frame wait. Interrupts are accepted in ~2/3 of frames. Whether
  game logic or sound depends on the interrupt count is [unknown]: card detect.pacing-structure / detect.routine-removal not run.
- Colour clash [observed]: practically none to remove (mono viewport; HUD bars and icons only). The toolkit's default
  "every figure a sprite" has no figures here: ships are line drawings into a 128 x 256 buffer, hundreds of line segments.
- Tail / memory [observed]: 5.5 KB of 0x4000-0xBFFF untouched, largest span 456 bytes; bank 0 at 0xC000 is the game's buffer
  (128K paging locked). NOT a constraint (user decision 2026-11-22, ## Decisions): the engine may use the Next's whole
  memory (MMU-paged Next banks), so hook code, state and new renderers live in Next pages, not in the game's 48K.
- Not measured: T per frame in the line plotters (cost --at 32739 / 41450), the scanner and HUD writers, a safe tail place.

## Probe: erase method and ship identity (stage 1, 2026-11-22)
Scripts (local, not kept): C:\1NEXT\elite_work\probe\line_callers.py (buffer writers + CALL return addresses on the stack),
ship_regs.py (IX / IY at each ship-line write). Replays: Docking 0-2500, Havoc 9000-11000, Witch 15500-17000 and 20000-26000,
PoliceAnarchy 42000-47000.
- Erase [observed]: no XOR erase. 0x8080-0x80B3 clears the whole buffer every frame (LDDR, ~4000 bytes + the frame edge
  bytes 255 / 1 / 128), one clear per buffer copy (2,904,000 LDDR writes = 726 clears = 726 copies, Docking). Lines are then
  ORed in (0x9117 / 0x911C, 0xB1B7, 0xB233 / 0xB253). Consequence: a coloured renderer needs no pixel-owner model; each
  frame starts clean, the last colour drawn on a pixel wins.
- Who draws what [observed: return addresses at the buffer writes; main loop 0x74E4-0x74FD]:
  0x7584 (CALL Z at 0x74EE) planet / sun: lines via 0x86DE -> 0x86EE -> 0x9117 / 0x917D / 0x9215;
  0x7898 (0x74F1) stars / dust: 0xA84B;  0xD03C (0x74F4) messages: XOR text 0xD549 (via 0x5DF8);
  0x9C80 (0x74F7, a JP table) lasers and crosshair: 0xB7B4-0xB7F1 -> line 0xB044 -> 0xB1B8 / 0xB233;
  ships: 0xF8C0 switches SP to 0x4020 (a private stack in screen memory) and CALLs 0xA6DF -> 0xA878 -> 0x61DD -> 0x6FD5 -> 0xB1B8.
- Ship identity [observed]: while a ship's lines are written, IY = that model's blueprint (pointer table at ~0x61BD-0x61D1;
  0x6211, 0x6325, 0x636A, 0x6381 in Witch; 0x61E3, 0x6228, 0x626D, 0x62C9, 0x633C, 0x6353, 0x63AF in PoliceAnarchy; 11 models).
  Several models in one frame (e.g. 0x62C9 + 0x6353 + 0x633C). IX is the object slot (0x6132 - 39 n: 0x606F-0x6132 seen) or the
  model's edge list (0x6Dxx, 0x6Axx). So colour per model, and per slot, is available at line time with no extra bookkeeping.
- Not checked: the scanner / HUD writers (outside the viewport buffer), sound, whether lines from the HUD routines run in the ISR.

## Decisions
- 2026-11-22 (user): "for elite, you can totally re-write the engine to utilise all the memory of the spectrum next, free
  RAM should not be scarce". So: a full engine rewrite is allowed (not only hooks on the original), and memory is not a
  design constraint. The equivalence rule still holds (gameplay extremely close, docs: owner 2026-11-10).

## Design question (stage 1)
ANSWERED 2026-11-22: "C: coloured ships" (of A plain + 28 MHz, B A + HUD clash cells, C B + viewport on Layer 2 in
colour). Details: ## Design details.

## Pacing (stage 2 gate, 2026-11-22)
- ISR (0xFF25, own stack at 0x4020): keyboard scan 0xFD69, control integration 0xFE01 (pitch / roll from the keys,
  every interrupt), then 0x7125 -> 0x9579. [observed: disassembly]
- Movement is PER MAIN-LOOP PASS, not per time [observed: slot_motion.py, Havoc 9000-9600, slot 0x60E4]: its z (bytes 6-7)
  drops ~0x52 per screen update whether 9, 13 or 16 frames passed (e.g. 18CA -> 1877 in 13 frames, 1824 -> 17D2 in 9).
  So the original's game speed falls with load (~5.5 updates a second, slower with many ships), and running the
  original loop faster makes the GAME faster - not allowed (equivalence rule).
- Smoothness therefore means decoupling the picture from the logic. Options (asked 2026-11-22):
  (i) logic untouched at a fixed tick (the original's typical ~9 frames per pass), the renderer interpolates ships between
  the last two logic states at up to 50 fps, and applies the player's own roll / pitch every frame (no lag on your own
  turning; other ships lag one tick, ~0.18 s); recommended: the original logic runs unchanged, so the RZX verification
  still applies to it.
  (ii) extrapolate instead of interpolate: no lag, small overshoots when a ship turns suddenly.
  (iii) smaller logic steps (movement, rotation, timers, AI divided by k, k times as many passes): no lag, but every
  constant in the game changes and the RZX can no longer verify the logic.
- ANSWERED 2026-11-23: (i) interpolate. Logic unchanged at a fixed tick; renderer interpolates other ships between the
  last two logic states, own roll / pitch applied every frame.

## Design details (answered 2026-11-22: 1, 2, 3, 5 defaults; 4 changed)
1. Ships: one colour per ship model (IY blueprint, 11 seen), chosen by us now, repaintable later (colour sheet + recolour).
2. Planet / sun / stars / lasers / crosshair / messages: each its own colour (planet blue, sun yellow, stars white,
   lasers red, crosshair and messages white), same rule.
3. Viewport on Layer 2 over a blank ULA viewport; HUD, scanner and text stay on the ULA, with the clash cells fixed (B).
4. Pace: CHANGED by the user: "4 speed - should be as smooth as possible". So: the highest frame rate the Next can give,
   game speed (how fast ships move, timers) kept as the original's (equivalence rule). How depends on ## Pacing.
5. Status / chart / equipment pages (full-screen ULA): Layer 2 off while they are up.

## Build plan (stage 2, written 2026-11-23 before any build)
Engine: new, `elite` (module nexclash/elite.py, asm/elite_hooks.asm, profile); Layer 2 double buffer as wally2.
Measured inputs: "All recordings" below.
1. Machine: the game's 128K banks unchanged; 28 MHz; new code and state in Next pages mapped only while it runs
   (the game uses 0x4000-0xFFFF; ROM 1 locked). Layer 2 256x192, two buffers; rows outside the viewport transparent so the
   ULA HUD shows through. ULA viewport left blank (the 0x7FBE copy skipped).
2. Logic tick: one original main-loop pass (move, AI, collisions, HUD) at 28 MHz, then wait for the tick boundary:
   T frames per pass (the original's typical pass, from the probes). The game's ISR body (keyboard 0xFD69, controls 0xFE01,
   0x7125) runs K times per tick, in the original's pattern (~6 per 10 frames), not every frame - so turn rate, timers
   and sound per pass match the original. Consequence (told to the user 2026-11-22): the game no longer slows down when
   busy; its speed is the original's typical speed.
3. The logic pass no longer draws into the buffer (clear 0x8080, plotters, copy 0x7FBE) unless a consumer is found
   (removal experiment: who reads bank 0 0xC000-0xCFDF other than the copy). At the end of a pass, the render state
   (all object slots 0x606F-0x6158, planet / sun, star table, laser / crosshair / message state, view) is copied into a
   ring (previous, current) in a Next page.
4. Renderer, every frame (50 Hz) in the tick's wait: alpha = k / T; interpolated copies of the slots (x, y, z linear;
   orientation vectors linear), then the game's own projection and line code (ships 0xA6DF, planet 0x7584, stars 0x7898,
   lasers 0x9C80) runs on the copies with the OR writers (0x9117 / 0x911C, 0xB1B7, 0xB233 / 0xB253, 0xA84B) redirected to a
   Layer 2 plotter: colour from IY (model) or the category. Game RAM the draw path writes is saved / restored around it, so
   the logic sees exactly what the original would. If the draw path is too slow or has consumers, own projection + line
   code in the hook page (allowed by the rewrite decision).
5. Own turning: phase 2 of the renderer - the roll / pitch integrated since the tick began applied as an extra rotation
   of the interpolated scene, so your own turns show the frame you make them.
6. ULA: HUD and scanner writers unchanged; clash cells fixed from a cells sheet (B); full-screen pages (status, charts,
   equipment) switch Layer 2 off (design 5); their routines are found from the survey's screen writers.
7. Start-up: NEX with the game's banks + engine pages; the 128K tail (## Open) is solved inside this engine.
Verify (step 6):
- Logic: per pass, original vs engine from the same state and the same ISR pattern: all registers and memory except
  the viewport buffer, the ULA viewport rows and the engine pages - must match.
- Render at alpha = 1: Layer 2 lit pixels == the original buffer's set bits for that pass (exact reference), colours from
  the map. Interpolated frames: no reference; checks - no game RAM changed, each drawn line lies between its two endpoint
  states, negative control (render state of the wrong pass fails).
- Pace and freshness (PLAYBOOK 6): display updates per second, logic ticks per second, longest miss, maximum display age.
Milestones: M1 early integrated diagnostic - NEX boots (JNext headless + CSpect), logic on the fixed tick + ISR pattern,
Layer 2 shows the ships in colour once per tick (alpha = 1 only). M2 interpolation at 50 fps. M3 own turning. M4 HUD cells,
pages, colour sheet + recolour. M5 quick runs PASS, evidence record docs/records/elite.json.
All recordings [observed: pass_frames.py / pass_ints.py, whole recordings]:
frames per pass mean Docking 10.13, Havoc 9.77, PoliceAnarchy 10.47, Witch 9.73, Reidquat 10.14 (p50 9-11, p90 12-16);
interrupts per pass mean 5.85 / 6.53 / 6.99 / 6.24 / 6.57 -> 0.58-0.67 interrupts per frame (outlier passes of 65-344
interrupts are full-screen pages / hyperspace, not flight). Choice: T = 10 frames per tick (5 game updates a second,
the original's mean), the game ISR body on ~0.64 of frames (16 of every 25, spread evenly) - turn rate and timers per
second as the original's flight average. Tunable constants in the engine, revisited at the first hardware test.
Main loop map [observed: probe pass_calls.py, Havoc 9000-9100, 11 passes; credit = outermost main-loop CALL on the stack]:
one pass = 0x7505 0x84D9, 0x7509 0x7222, 0x750C 0x9A40, 0x750F 0x81A9, 0x7477 0x713C, 0x747A 0x80D3, 0x747D 0x72A3,
0x748C 0xD042, 0x74B0 0x717B, 0x74B3 0x5DC8, 0x74B6 0x7EDE, 0x74B9 0x7853, 0x74E4 0x8042, 0x74E7 0x8080 (buffer clear),
0x74EE 0x7584 (planet / sun), 0x74F1 0x7898 (stars), 0x74F4 0xD03C (messages), 0x74F7 0x9C80, 0x74FA 0x9296,
0x7502 0xED60 (-> 0x7FBE buffer copy).
- ALL object-slot writes come from 0x9C80 (3453 of 3480; the rest from the ship-draw path 0xF8C0, its stack in screen memory):
  0x9C80 is the per-ship loop - move each ship and draw it, interleaved (as the BBC original's main flight loop), plus
  lasers, crosshair and the scanner (screen writes 0xA0FD, 0xAB0B, 0xAB34). Stars move and draw together too (0x7898
  writes its table via 0x7A71); the planet routine writes its state (0x7591 / 0x75B6).
- Consequence for the build: there is no separate "draw" pass to rerun. The logic pass runs whole (drawing included,
  into the unused bank-0 buffer at 28 MHz - also the exact reference at alpha = 1); the renderer reruns only the
  per-object draw calls inside 0x9C80 / 0x7898 / 0x7584 on interpolated copies, with everything they write saved and
  restored (draw-time state such as an explosion cloud's counter must not advance per render).
- Per-ship draw site [observed: disassembly, Docking.z80]: in 0x9C80's per-ship body (IX = slot) 0x9E29 CALL 0x9F82,
  0x9E2C CALL 0xAE69, 3x CALL 0x9F41 on IX+9.., 0x9E41 CALL 0xB4D8, then 0x9E44 JP 0xF8B4 - the hack's draw wrapper: DI,
  ISR entry 0xFEFE set to RET (0xC9), SP saved and set to 0x4020, CALL 0xA6DF (draw this ship), SP = 0x411A, 0xFEFE back
  to JR (0x18), EI, JP 0x9E47. After the draw 0x9E47 RES 3,(IX+32) and tests bits 4 / 5 of (IX+32) (set by the draw?),
  then 0x9E5D CALL 0xA8EC and 0x9E63 JP 0xF8E4 (next slot). So the renderer's ship call is 0xA6DF with IX = an
  interpolated slot copy; slot byte 32 is draw-time state the logic reads (save / restore it around renders).
First tasks: removal experiment for the buffer;
find the planet / star / laser state the renderer needs; cost of one full draw at 28 MHz (drawcost / cost --at).

## M1 progress (2026-11-23)
M1 part 1 (colour mirror) RUNS in CSpect from the Docking and Witch snapshots: planet blue, crosshair / lasers red,
text and stars white, ships per model (station light grey-blue), stable over ~600 frames of flying.
M1 part 2 (pacing) RUNS too (Docking ~900 frames, Witch ~260 frames with pitch / climb keys): 28 MHz (setup NR $07 = 3);
h_flip waits until TICK = 10 frames have passed since the last tick (HALT loop, frame count from h_isr), so a pass at
28 MHz (~1 frame) idles ~9; measured tick-to-tick 10 frames exactly. h_isr (IM 2 vector 0x3A3A, I = 0x39 table of
0x3A) counts frames in state page 26 (mapped at slot 0 under DI) and runs the game's ISR body 0xFF25 on 16 of every
25 frames (pattab), honouring the hack's own 0xFEFE = RET switch. Keys answer at the original rate. Build: `python -m nexclash.elite IN.z80 OUT.nex`
(`--control` = IM 2 fix only; `--control=rst+cat+...` / `wXXXX` = hook subsets, the bisect used below).
Code: asm/elite_hooks.asm, nexclash/elite.py, docs/profiles/elite.json (not yet in nexclash/engines.py or the CLI).
- Writers: every buffer write is LD (HL),A / LD (HL),B / LD (HL),0xFF (probe buf_writers.py, Docking whole: 22 sites
  + the clear's LDDRs); each becomes RST 18h / 10h / 20h + NOP; the handler does the write, then mirrors the changed
  bits onto the Layer 2 back buffer (buffer line k = screen-layout decode of HL, shown at y = k + 8, k < 120).
- Colour: NR $7F = current colour (category hooks at 0x74EE / 0x74F1 / 0x74F4 / 0x74F7), 0 = ship mode: colour =
  shipcol[IY low byte]. Blueprints are 23-byte records 0x61E3 + 23 n (n = 0-22, distinct low bytes) - all 23 coloured.
- Layer 2: banks 16 / 19, cleared by DMA with the game's clear (0x8080), flipped with its copy (0x7FBE). ULA copy kept.
- Start-up: tail at 0x4800 (viewport rows: the copy writes them first; scan_low.log). IM 2 vector table moved to the
  alt ROM (I = 0x39, 257 x 0xFE) - see the bugs below.
Bugs found on the way (each a CSpect round): CSpect's IM 2 bus byte is not 0xFF (vector table moved to the alt ROM,
I = 0x39); the ship wrapper's stack floor 0x400E (h_plot at most 10 bytes, no CALL); 0x8080 keeps A (h_clear
pushes it); CSpect -mmc traps RST 08h as esxDOS and skips a byte (RST 18h used; found by hook-subset bisect).
Stars plot into columns 0 / 31 outside the frame (the game's copy leaves them out; h_plot skips them since M3b).
Not yet checked: the differential verify (step 6); hardware.

## M2 progress (2026-11-23)
M2 RUNS in CSpect (Docking and Witch, 700 frames each of rolling / pitching / speed-up; chart page entered and left).
Code: asm/elite_render.inc (h_flip, render, interp), asm/elite_hooks.asm (h_ship, frame counting), probes
draw_deps.py / draw_io.py in C:NEXT\elite_work\probe.
- Ship draw facts [observed: draw_deps.py, all five recordings whole, 1.1k-11.5k calls each]: 0xA6DF reads the slot's
  bytes 0-8 (x, y, z: lo, hi, sign), 10-20 even (orientation high bytes), 32, 33, 38; slots are 39 bytes at
  0x6048 + 39 n, n = 0-7 (8 slots; IY = slot bytes 35-36). Varying inputs outside the slot: 0x6F42, 0x70E3,
  0xA8FA-0xA905, 0xA9C8, 0xAA0F, 0xB452-0xB4A3, 0xB7AA/B (scratch the previous draw left, vertex tables); every
  other byte it reads (2.5k addresses) never changes. It writes ~400 bytes of scratch / self-modified operands and
  0x9C97, a flag the flight loop reads (so every render must restore what it wrote).
- Slot formats [observed: snapshots]: position 3 x (lo, hi, sign | bits 16-22); orientation 9 x (fraction,
  sign | magnitude), unit ~0x7F00 (rows norm 127).
- Design as built: h_ship (0x9E44) records each ship as the original draws it (slot, blueprint, 0xA79D, the inputs)
  into list S_W and lets the original draw go to the mono buffer only (NR $7F = 1: no mirror). Everything else the
  pass draws goes to a base Layer 2 (banks 14-15). h_flip: last list = cur, the one before = prev; until the tick,
  render once per frame: base copied (DMA) to the back buffer, game's clear (0x8084, keeps the frame), outputs
  saved, per cur record: slot + inputs written back, x / y / z and the 9 components interpolated from prev's record
  of the same slot and blueprint (weight frames-since-tick / 10; a jump of 0x8000+ keeps cur), 0xA6DF called as the
  wrapper does (0xFEFE = RET, SP 0x4020), outputs restored, flip. Only after a flight pass (h_combat sets
  S_FLIGHT): status / chart pages keep the original copy.
- Interpolation checked in CSpect (station, Docking): z 0x4D1F -> 0x4D1D shows 0x4D1E; components move in steps
  (0xE438, 0xE568, 0xE6A0 towards 0xE800 at weights 0.6-0.8).
- Frame counting (3 rounds; lesson in ## Lessons): h_isr counts each interrupt, raster polls in DI stretches add
  lost ones; 506 counted over ~505 frames. The game ISR body runs from an owed count (16 per 25 frames).
- M3 (ships): ownrot, after interp, turns each ship by one pass of the current roll / pitch (0xFF09 / 0xFF0B) with
  the game's own code - 0xA173 position (speed byte 0xFF: no z move, never its overflow exit 0x5FD5), 0xA0AB x 3
  orientation (as 0x9FA8). Cancels the tick of lag for own turning. Checked: pitch forced to 0x0FFF moved the
  station's y 0x0418 -> 0x088A in the next render (one pass of y += pitch * z). Docking / Witch 600-700 frames.
  Player rates: 0xFF08 roll, 0xFF0A pitch (16-bit sign | magnitude, controls 0xFE01 in the ISR, steps 255 / 102,
  max 0x0FFF), 0xFF0C speed; 0x713C copies the high bytes to 0x70E4-0x70E6 once per pass.
Not yet checked / open: one render sample (Docking, after ~600 frames) showed a station z of 0xB2E1 negative (not
reproduced in 8 later samples; to watch with a render assert); Havoc.z80 crashes ~150 frames in even in the
--control build (no hooks; status page snapshot - the start-up tail at 0x4800 sits in its text rows); Layer 2 not yet
hidden on pages (M4); hardware.
- M3b (planet, sun, stars): the pass draws them to the mono buffer only; render's scenery, after the ships, scales
  the control bytes 0xFF09 / 0xFF0B (magnitude) and 0xFF0D ((speed + 1) * w - 1: 0xA173 moves z by (speed + 1) * 2)
  by the weight, then the game's own 0x713C, 0x7853 (move), 0x7584 (draw, if 0x7103 = 0), 0x7898 (stars move + draw)
  - their place now (cur + w of a pass). Outputs [observed: draw_deps.py on 0x7853 / 0x7584 / 0x7898, Docking]
  added to outtab. Checked: Docking / Witch 600-1200 frames, count = time; renders land ~every 2nd frame (d 1, 3).

## Hardware checklist
None yet (no build).

## Stage log
2026-11-22  stage 0 (intake, all five recordings)  ~2 h  ~60 calls  0 user rounds

## Lessons
- [deferred Open: reconsider when a second engine counts frames on the Next with long DI stretches] Counting frames with DI code: interrupts alone lose frames, raster polls alone lose them when polls fall a frame apart at the same line, and a HALT wait polls only at the interrupt line (never sees the raster go round). Count each interrupt and let polls inside DI stretches add only the frames whose interrupt was lost (phase from the interrupt's own line, a flag so neither counts the same frame twice).
- [tool nexclash.survey] survey preview.png tints each plot routine's output in its own colour; read the game's colours from a plain `preview` (no --plot), not from the survey sheet (Elite: a mono viewport was reported as coloured). survey.md's Preview heading now says so.
- [deferred Open: reconsider when stage 1 feasibility shows whether a tail can be placed (--tail + scan --range)] A 128K snapshot with the 48K ROM locked in: `convert` found no place for the start-up tail and nextboot.check models 48K start-up only. (2026-11-23: --tail 0x4800, viewport rows the copy writes first, works in CSpect.)
- [deferred Open: reconsider when the first hardware test shows which is CSpect's alone] CSpect differs from the toolkit's assumptions twice: its IM 2 bus byte is not 0xFF (a table valid only at I*256+0xFF fails), and with -mmc it traps RST 08h as esxDOS (skips the next byte). Candidates for BRIEFING A1 / the kb once hardware confirms which is the emulator's alone.
- [deferred Open: reconsider when a second engine patches writers that run on a private stack] An RST handler that runs on a game's private stack must fit its depth: measure SP at every patched site (site_ctx.py) before choosing pushes; and a hook that replaces a routine's first instruction must keep every register the original keeps (callers rely on it: 0x8080 kept A).

## Technique use
- detect.routine-removal: no help: not run; the probe read call paths from the stack instead (2026-11-22)
- detect.pacing-structure: used: survey flagged pacing (1726 interrupts in 3001 frames); not analysed further yet (2026-11-22)
