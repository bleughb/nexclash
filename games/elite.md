# Elite (Braben / Bell, Firebird 1985; Russian 128K hack) - engine: none yet

## Next session
Stage: 0 done (all five recordings surveyed in full), 1 next (design)   State: intake 2026-11-22, no design asked yet
Inputs: specnext/reference/elite/ (tape, 5 RZX, 5 extracted .z80)    Branch: add-elite    Commit: see git log
Checks: full surveys of all five RZX (7.5k-68.6k frames); tape not run in an emulator
Pending user answers: stage-1 design question (nothing asked yet)
Start with: feasibility (PLAYBOOK 3d): cost of 32702/32717 (back-buffer copy) and 32739 (line plot), tail place, then the design question
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

## Hardware checklist
None yet (no build).

## Stage log
2026-11-22  stage 0 (intake, all five recordings)  ~2 h  ~60 calls  0 user rounds

## Lessons
- [deferred Open: reconsider when stage 1 feasibility shows whether a tail can be placed (--tail + scan --range)] A 128K snapshot with the 48K ROM locked in: `convert` found no place for the start-up tail and nextboot.check models 48K start-up only.

## Technique use
- detect.pacing-structure: used: survey flagged pacing (1726 interrupts in 3001 frames); not analysed further yet (2026-11-22)
