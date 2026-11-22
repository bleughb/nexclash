# Elite (Braben / Bell, Firebird 1985; Russian 128K hack) - engine: none yet

## Next session
Stage: 0 done (all five recordings surveyed in full), 1 next (design)   State: stage 1 probe done 2026-11-22 (## Probe); design question open, user allowed a full rewrite
Inputs: specnext/reference/elite/ (tape, 5 RZX, 5 extracted .z80)    Branch: add-elite    Commit: see git log
Checks: full surveys of all five RZX (7.5k-68.6k frames); tape not run in an emulator
Pending user answers: ## Design details 1-5 (option C chosen)
Start with: the user's answers to ## Design details, then stage 2 (build)
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

## Findings (stage 0, DockingElite.rzx, `--stop 3000` first look)
- Snapshot: 128K machine, 7FFD = 0x30 (ROM 1 = 48K BASIC, bank 0 at C000, paging LOCKED): runs like a
  48K game. IM 2, I = 0xFD, vector 0xFDFF -> 0xFEFE, DI at the snapshot. Border 0. WitchElite starts at
  PC 0xAB64, the other four at 0xFEFE (ISR). All five snapshots show the same IM 2 setup.
- Engine: unknown (no detector, no TID / Dizzy signature) -> stage 1, feasibility first (PLAYBOOK 3d).
- Rendering: vector (wireframe) game with a BACK BUFFER: 32702 (0x7FBE) / 32717 (0x7FCD) block-copy the
  frame to the screen (~125k T per call, 286 calls in 3000 frames, i.e. a full-frame copy every ~10
  frames). Line plotter 32739 (0x7FE3) does most calls (68642). Text/scanner-like plotters at
  44033 (0xAC01) and 39117 (0x98CD), 30872 (0x7898).
- Plain conversion FAILED: no place for the start-up tail (128K snapshot; `--tail ADDR` needed, prove
  with `scan --range`; nextboot.check models 48K start-up only).
- GATE: CHECK - 2 CALL sites to 39117 (29993, 39074) never reached in this short run; repeat with
  the longer recordings before design.
- Pacing: 1726 interrupts accepted in 3001 frames (the game runs with DI for stretches).
- Mostly lines on black with few colour attributes: expected colour clash is limited (HUD / scanner
  colours); what a "sprite" conversion means here is a stage-1 question, not decided.

## Open
- Tail placement for a 128K snapshot with ROM 1 locked (see Lessons).
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
  (128K paging locked). NOT a constraint (user decision 2026-11-22, ## Probe: erase method and ship identity (stage 1, 2026-11-22)
Scripts (local, not kept): C:NEXT\elite_work\probe\line_callers.py (buffer writers + CALL return addresses on the stack),
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

## Decisions): the engine may use the Next's whole
  memory (MMU-paged Next banks), so hook code, state and new renderers live in Next pages, not in the game's 48K.
- Not measured: T per frame in the line plotters (cost --at 32739 / 41450), the scanner and HUD writers, a safe tail place.

## Probe: erase method and ship identity (stage 1, 2026-11-22)
Scripts (local, not kept): C:NEXT\elite_work\probe\line_callers.py (buffer writers + CALL return addresses on the stack),
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
ANSWERED 2026-11-22 (user): "C: coloured ships" -> option C (includes B). Details still open: the numbered list in
## Design details (asked 2026-11-22).
Options put to the user: (A) plain, ULA unchanged, + Next speed (28 MHz) if pacing allows; (B) A + fix the few clash
cells (HUD bars, condition light, planet / sun icon); (C) B + redraw the viewport on Layer 2 so ships / lines get colour
(a new line-renderer engine; changes what the user sees). After the rewrite decision, C is no longer limited by memory;
both unknowns for C are answered (## Probe): the buffer is cleared every frame (no owner model needed) and the ship
model is in IY while its lines are drawn. Colouring per model / per draw category (planet, sun, stars, lasers, text) is cheap.

## Design details (asked 2026-11-22, answers pending; defaults proposed)
1. Ships: one colour per ship model (IY blueprint, 11 seen), chosen by us now, repaintable later (colour sheet + recolour).
2. Planet / sun / stars / lasers / crosshair / messages: each its own colour (planet blue, sun yellow, stars white,
   lasers red, crosshair and messages white), same rule.
3. Viewport on Layer 2 over a blank ULA viewport; HUD, scanner and text stay on the ULA, with the clash cells fixed (B).
4. Pace: the original's (~5 updates a second, its slowdowns kept); a faster mode only if asked.
5. Status / chart / equipment pages (full-screen ULA): Layer 2 off while they are up.

## Hardware checklist
None yet (no build).

## Stage log
2026-11-22  stage 0 (intake, all five recordings)  ~2 h  ~60 calls  0 user rounds

## Lessons
- [tool nexclash.survey] survey preview.png tints each plot routine's output in its own colour; read the game's colours from a plain `preview` (no --plot), not from the survey sheet (Elite: a mono viewport was reported as coloured). survey.md's Preview heading now says so.
- [deferred Open: reconsider when stage 1 feasibility shows whether a tail can be placed (--tail + scan --range)] A 128K snapshot with the 48K ROM locked in: `convert` found no place for the start-up tail and nextboot.check models 48K start-up only.

## Technique use
- detect.routine-removal: no help: not run; the probe read call paths from the stack instead (2026-11-22)
- detect.pacing-structure: used: survey flagged pacing (1726 interrupts in 3001 frames); not analysed further yet (2026-11-22)
