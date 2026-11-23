# Elite (Braben / Bell, Firebird 1985; Russian 128K hack) - engine: elite (in progress, stage 2)

Techniques: `patch.hybrid-display-replacement`, `patch.inbetween-views`, `patch.iff-safe-read`

## Next session
Stage: 2 (build)   State: M5 done 2026-11-23 (record docs/records/elite.json; CSpect / hardware check owed)
Inputs: specnext/reference/elite/ (tape, 5 RZX, 5 extracted .z80)    Branch: add-elite    Commit: see git log
Checks: full surveys of all five RZX (7.5k-68.6k frames); tape not run in an emulator
Pending user answers: none (design closed 2026-11-23: C coloured ships, details 1-5, pacing (i) interpolate)
Start with: `python -m nexclash.elite C:\1NEXT\elite_work\Witch.z80 m2.nex` in CSpect (m4 build), then CSpect / hardware check
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
Probes: C:\1NEXT\elite_work\probe (line_callers.py, ship_regs.py; partial replays of four recordings).
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
  11 models seen then; 21 of 23 over the five whole recordings, M4 sheet probe).
  Several models in one frame (e.g. 0x62C9 + 0x6353 + 0x633C). IX is the object slot (0x6132 - 39 n: 0x606F-0x6132 seen) or the
  model's edge list (0x6Dxx, 0x6Axx). So colour per model, and per slot, is available at line time with no extra bookkeeping.
- HUD clash [observed: probe hud_cells.py, Docking + Havoc whole]: bars switch whole cell rows (7/0, 7/2); only clash:
  scanner sticks (direct 9809 / 982D / 9856, buffer copy 991F at c09-21 r18-23) in the light's r17-18 c09 and the S cell
  r22 c21 (9B07: 0/0 hides). Fixed for the light (sprite, ## M2 progress); the S cell left as the original.

## Decisions
- 2026-11-22 (user): "for elite, you can totally re-write the engine to utilise all the memory of the spectrum next, free
  RAM should not be scarce". So: a full engine rewrite is allowed (not only hooks on the original), and memory is not a
  design constraint. The equivalence rule still holds (gameplay extremely close, docs: owner 2026-11-10).
- 2026-11-22 (user): design "C: coloured ships" (B HUD clash cells + viewport on Layer 2 in colour); ## Design details.

## Pacing (stage 2 gate, 2026-11-22)
- ISR (0xFF25, own stack at 0x4020): keyboard scan 0xFD69, control integration 0xFE01 (pitch / roll from the keys,
  every interrupt), then 0x7125 -> 0x9579. [observed: disassembly]
- Movement is PER MAIN-LOOP PASS, not per time [observed: slot_motion.py, Havoc 9000-9600, slot 0x60E4]: its z (bytes 6-7)
  drops ~0x52 per screen update whether 9, 13 or 16 frames passed (e.g. 18CA -> 1877 in 13 frames, 1824 -> 17D2 in 9).
  So the original's game speed falls with load (~5.5 updates a second, slower with many ships), and running the
  original loop faster makes the GAME faster - not allowed (equivalence rule).
- Smoothness therefore means decoupling the picture from the logic. Options (asked 2026-11-22):
  (i) logic untouched at a fixed tick, renderer interpolates ships between the last two states at 50 fps, own roll /
  pitch every frame (other ships lag one tick, ~0.18 s; the RZX still verifies the logic).
  (ii) extrapolate (overshoots); (iii) smaller logic steps (every constant changes, RZX no longer verifies).
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

## Build plan (stage 2, written 2026-11-23; condensed at M5)
Engine `elite` (nexclash/elite.py, asm/elite_hooks.asm, profile); Layer 2 double buffer as wally2. 28 MHz; new code and
state in Next pages mapped only while it runs; Layer 2 rows outside the viewport transparent so the ULA HUD shows.
- Logic tick: one original main-loop pass at 28 MHz, then wait for the tick: T = 10 frames (mean 9.7-10.5 per pass in
  all five recordings), the game ISR body on 16 of 25 frames (0.58-0.67 interrupts per frame measured): turn rate,
  timers and sound per second as the original's flight average; the game no longer slows when busy.
- The pass draws to the mono buffer only (the exact reference at weight 1); a renderer per frame reruns the game's own
  draw (ships 0xA6DF, planet 0x7584, stars 0x7898) on interpolated copies, game RAM saved and restored around it.
  Own turning: roll / pitch since the tick applied to the interpolated scene. Full-screen pages: Layer 2 off.
- Main loop [probe pass_calls.py]: 0x7477 0x713C .. 0x7853, 0x8080 clear, 0x7584 planet, 0x7898 stars, 0xD03C messages,
  0x9C80 ship loop (move + draw interleaved, lasers, scanner), 0xED60 -> 0x7FBE copy. Ship draw site 0x9E44 JP 0xF8B4.
- Verify: per pass original vs patched (registers, memory outside the exclusions, port writes); the render at full
  weight against the buffer; interpolated frames have no reference (negative control: the wrong pass fails).
Milestones: M1 colour mirror + pacing, M2 interpolation, M3 own turning, M4 HUD / pages / colour sheet, M5 quick runs + record.

## M1 progress (2026-11-23)
M1 RUNS in CSpect (Docking, Witch): colour mirror + pacing. 28 MHz; h_flip waits TICK = 10 frames since the last tick;
h_isr (IM 2 vector 0x3A3A, I = 0x39) counts frames in state page 26 and runs the game's ISR body 0xFF25 on 16 of 25
frames (pattab), honouring the hack's 0xFEFE = RET. Build: `python -m nexclash.elite IN.z80 OUT.nex` (`--control` =
IM 2 fix only; `--control=rst+cat+light+...` / `wXXXX` = hook subsets). Code: asm/elite_hooks.asm, asm/elite_render.inc,
nexclash/elite.py, nexclash/elite_colours.py, docs/profiles/elite.json (not yet in nexclash/engines.py or the CLI).
- Writers: every buffer write (LD (HL),A / B / 0xFF, probe buf_writers.py + buf_pcs.py, all recordings; LDDR fills,
  PUSH AF stack blits) becomes an RST / JP into the alt ROM that writes and mirrors the changed bits to Layer 2
  (buffer line k at y = k + 8). Left: 0x818C (page save); 0xFB01 (hidden in an operand) found at M5.
- Colour: NR $7F = current colour, 0 = ship mode (shipcol[IY low byte]; blueprints 0x61E3 + 23 n, n = 0-22).
- Layer 2 banks 16 / 19, cleared by DMA with 0x8080, flipped with 0x7FBE. Start-up tail at 0x4800.
- Bugs (each a CSpect round): CSpect's IM 2 bus byte is not 0xFF; 0x8080 keeps A; CSpect -mmc traps RST 08h; stars
  plot into columns 0 / 31 (skipped); the game's 32-byte stack 0x4100 overflows into ULA row 56 (rowfix, own stacks).
Not yet checked: the differential verify (step 6); hardware.

## M2 progress (2026-11-23)
M2 RUNS in CSpect (Docking, Witch: 700 frames each, flying; chart page and back). Code: asm/elite_render.inc,
asm/elite_hooks.asm; probes draw_deps.py / draw_io.py.
- Ship draw facts [observed: draw_deps.py, all five recordings whole, 1.1k-11.5k calls each]: 0xA6DF reads the slot's
  bytes 0-8 (x, y, z: lo, hi, sign), 10-20 even (orientation high bytes), 32, 33, 38; slots are 39 bytes at
  0x6048 + 39 n, n = 0-7 (8 slots; IY = slot bytes 35-36). Varying inputs outside the slot: 0x6F42, 0x70E3,
  0xA8FA-0xA905, 0xA9C8, 0xAA0F, 0xB452-0xB4A3, 0xB7AA/B (scratch the previous draw left, vertex tables); every
  other byte it reads (2.5k addresses) never changes. It writes ~400 bytes of scratch / self-modified operands and
  0x9C97, a flag the flight loop reads (so every render must restore what it wrote).
- Slot formats [observed: snapshots]: position 3 x (lo, hi, sign | bits 16-22); orientation 9 x (fraction,
  sign | magnitude), unit ~0x7F00 (rows norm 127).
- Design as built: h_ship (0x9E44) records each ship as drawn (slot, blueprint, inputs) into list S_W; the pass draws
  ships to the mono buffer only, the rest to a base Layer 2. h_flip renders once per frame until the tick: base copied
  (DMA), outputs saved, each record's slot / inputs written back, x / y / z and orientation interpolated from the
  previous list's record (weight frames-since-tick / 10; a jump of 0x8000+ keeps cur), 0xA6DF called as the wrapper
  does, outputs restored, flip. Only after a flight pass (S_FLIGHT): pages keep the original copy.
- Frame counting (lesson in ## Lessons): interrupts + raster polls in DI stretches; 506 counted over ~505 frames. The game ISR body runs from an owed count (16 per 25 frames).
- M3 (ships): ownrot, after interp, turns each ship by one pass of the current roll / pitch (0xFF09 / 0xFF0B) with
  the game's own code - 0xA173 position (speed byte 0xFF: no z move, never its overflow exit 0x5FD5), 0xA0AB x 3
  orientation (as 0x9FA8). Cancels the tick of lag for own turning. Checked (forced pitch moved the station
  one pass in the next render); Docking / Witch 600-700 frames.
  Player rates: 0xFF08 roll, 0xFF0A pitch (16-bit sign | magnitude, controls 0xFE01 in the ISR, steps 255 / 102,
  max 0x0FFF), 0xFF0C speed; 0x713C copies the high bytes to 0x70E4-0x70E6 once per pass.
Not yet checked / open: one render sample (Docking, after ~600 frames) showed a station z of 0xB2E1 negative (not
reproduced in 8 later samples; to watch with a render assert); Havoc.z80 crashes ~150 frames in even in the
--control build (no hooks; status page snapshot - the start-up tail at 0x4800 sits in its text rows); hardware.
- M3b (planet, sun, stars): the pass draws them to the mono buffer only; render's scenery, before the ships (they are drawn over it), scales
  the control bytes 0xFF09 / 0xFF0B (magnitude) and 0xFF0D ((speed + 1) * w - 1: 0xA173 moves z by (speed + 1) * 2)
  by the weight, then the game's own 0x713C, 0x7853 (move), 0x7584 (draw, if 0x7103 = 0), stars_x
  - their place now (cur + w of a pass). Outputs [observed: draw_deps.py on 0x7853 / 0x7584 / 0x7898, Docking]
  added to outtab. Checked: Docking / Witch 600-1200 frames, count = time.
- M4 part 1: Layer 2 off (blank bank 22) on pages (h_isr: 0x7104 = 0 or 0x70E3 >= 4). Hooks use stacks in the
  state page (the game's 32-byte one overflowed into ULA row 56: dashes). h_plot is DI while write-over is on (an
  interrupt there wrote h_isr's stack to Layer 2: Docking hang). Checked: Docking 1800, Witch sun, pages.
  stars_x: stars moved on by w along their last move (0x7898 on scaled speed wobbled).
- M4 part 2: ulaclr clears the snapshot's ULA viewport inside its frame once (first h_flip). h_light (0x99D7):
  condition light = sprite 0 (the game's shape; palette 0x11/0x21/0x31 = ULA red/green/yellow), c09 cells white (scanner
  sticks white); sprites off on pages and docked. Checked: yellow/green/forced red, page and back.
  Colour: nexclash/elite_colours.py, one key per figure (S<IY lo> = shipcol; C<cat> = `nextreg 0x7F,n` sites cs_*),
  15-colour PAL8, nibble 0 = asm default; recolour() rewrites bank 12 only (empty map = build, tested). Figures: 21
  models from the recordings (61E3 6211 62F7 6325 picked by eye: tunnel rings come under a stale IY) in
  docs/profiles/elite_shapes.json.gz. The CLI finds it once the M5 record exists.

## M5 progress (2026-11-23)
Verifier nexclash/elite_verify.py (docstring = method): per main-loop pass the patched build on a Next model against the
original (registers without I / R, banks 0-7 minus exclusions, port writes; ISR bodies placed by main-line count; the
first render of a pass at full weight against that pass's buffer; XOR overlaps classified exactly, no tolerance).
Result: Docking whole 1434 passes, Witch / Havoc / PoliceAnarchy / Reidquat to frame 20000 213 / 8988 / 11613 / 17505,
all exact; full-weight renders = buffer except 7-113 XOR overlaps per recording; unit tests (recolour, negative h_clear,
R, ISR pattern, render) caught; 8CCD / 8DC3 fills never reached in any recording. Record docs/records/elite.json.
Bugs the verifier found: waitpt (ISR bodies lost in DI renders); render changed IX / IY / alternates (S_REGS); NIN 100 vs
103-byte intab (ships drawn from shifted slots); 0xFB01 writer; XOR line pairs holes (h_plot restores the base pixel);
streak stars (S_HYP); h_isr unmapped the state page of a render it interrupted (the ship wrapper's EI) - now reads NR $50
and puts it back, no body then (waitpt runs it); the model's NR read-back of the MMU slots was missing.
Not done: CSpect check of the M5 build (CSpect not running at the scheduled run); hardware.

## Hardware checklist
None yet (no build).

## Stage log
2026-11-22  stage 0 (intake, all five recordings)  ~2 h  ~60 calls  0 user rounds
2026-11-23  stage 2 M4 (pages, stars, HUD light sprite, colour sheet + recolour)  2 user rounds
2026-11-23  stage 2 M5 (verifier, 5 recordings exact, record)  0 user rounds

## Lessons
- [deferred Open: reconsider when a second engine counts frames on the Next with long DI stretches] Counting frames with DI code: interrupts alone lose frames, raster polls alone lose them when polls fall a frame apart at the same line, and a HALT wait polls only at the interrupt line (never sees the raster go round). Count each interrupt and let polls inside DI stretches add only the frames whose interrupt was lost (phase from the interrupt's own line, a flag so neither counts the same frame twice).
- [tool nexclash.survey] survey preview.png tints each plot routine's output in its own colour; read the game's colours from a plain `preview` (no --plot), not from the survey sheet (Elite: a mono viewport was reported as coloured). survey.md's Preview heading now says so.
- [deferred Open: reconsider when stage 1 feasibility shows whether a tail can be placed (--tail + scan --range)] A 128K snapshot with the 48K ROM locked in: `convert` found no place for the start-up tail and nextboot.check models 48K start-up only. (2026-11-23: --tail 0x4800, viewport rows the copy writes first, works in CSpect.)
- [deferred Open: reconsider when the first hardware test shows which is CSpect's alone] CSpect differs from the toolkit's assumptions twice: its IM 2 bus byte is not 0xFF (a table valid only at I*256+0xFF fails), and with -mmc it traps RST 08h as esxDOS (skips the next byte). Candidates for BRIEFING A1 / the kb once hardware confirms which is the emulator's alone.
- [deferred Open: reconsider when a second engine patches writers that run on a private stack] An RST handler that runs on a game's private stack must fit its depth: measure SP at every patched site (site_ctx.py) before choosing pushes; and a hook that replaces a routine's first instruction must keep every register the original keeps (callers rely on it: 0x8080 kept A).
- [kb lesson.clash-by-layer-and-no-clash: Elite's mono HUD measured] HUD cell census (Docking, Havoc whole): only three
  cells clash - scanner sticks reach the condition light's cells and the S cell; the bars switch whole cell rows.
- [kb lesson.ink-rectangle-sprites-car-colour: a HUD indicator] the condition light, coloured by four attribute writes,
  is drawn as a sprite of the game's own light pixels; its scanner-side cells go white, so scanner sticks there show white.
- [kb lesson.coloursheet-one-key-per-figure: new] one colour per ship model: each figure is one colour-map key at bit 0 on
  a whole-figure sheet, so one painted pixel colours the whole figure on rebuild and on the redrawn sheet.
- [local: Elite's ship draw path] the launch tunnel rings are drawn while IY still holds the last ship's blueprint, so
  they take that ship's colour, and a capture of figures per IY must leave them out.
- [local: CSpect latches INT] verify interrupt windows against a 32 T pulse: at 28 MHz renders with long DI left almost no interrupt in the EI window and the game ISR rarely ran; CSpect hid it.
- [local: Elite verifier] assert a table's size from the table, not a copied expression (NIN 100 against a 103-byte intab drew every ship from a shifted slot); and an ISR must keep the interrupted code's MMU mapping, not assume ROM.

## Technique use
- detect.routine-removal: no help: not run; the probe read call paths from the stack instead (2026-11-22)
- detect.pacing-structure: used: survey flagged pacing (1726 interrupts in 3001 frames); not analysed further yet (2026-11-22)
- tools/probes/sprite_leftovers.py: helped: 127 sprites left visible once h_light enabled sprites; setup hides all (2026-11-23)
- tools/probes/attr_census.py: no help: per-window sets; the question was which writers meet in a cell (2026-11-23)
- patch.hybrid-display-replacement: helped: buffer writers mirrored to Layer 2, verified exact on five recordings (2026-11-23)
- patch.inbetween-views: helped: renders between passes, full-weight render = buffer (2026-11-23)
- patch.iff-safe-read: corrected: 5 single LD A,I reads -> HLIB_IFF_DI; phase to im2tab gap (2026-11-23)

## Friction
- reuse: [probe tools/probes/cell_writers.py] the per-cell writer census (HUD clash question) was written from scratch; kept.
- retries: [local: M5 crash hunt] a whole-run agent (330k tokens) was too costly; the crash was found by tracing slot-0 mapping, not by bisecting. ulaclr first cleared the frame lines too; the light sprite first left out the light's own edge pixels.
- environment: [local: cause not found] games/elite.md and nexclash/elite.py had CR CR LF line ends from an earlier session; fixed to CRLF.
- hand-rolled: [local: Elite's view flag] a page in CSpect: break at 0x747A, write 0xFC08 = 1 (press_keys did not open one).
- scratch: [local: Elite's draw path and recordings] ship_shapes6.py / pick_ships.py / show_cands.py stay in the local elite_work/probe folder.
