# Elite (Braben / Bell, Firebird 1985; Russian 128K hack) - engine: none yet

## Next session
Stage: 0 done (Docking only), 1 next (design)   State: intake 2026-11-22, no design asked yet
Inputs: specnext/reference/elite/ (tape, 5 RZX, 5 extracted .z80)    Branch: add-elite    Commit: see git log
Checks: survey of DockingElite (3000 frames); other four recordings not surveyed
Pending user answers: stage-1 design question (nothing asked yet)
Start with: `python -m nexclash.survey ../specnext/reference/elite/PoliceAnarchyElite.z80 --rzx ../specnext/reference/elite/PoliceAnarchyElite.rzx --stop 15000`
Read: PLAYBOOK stage 1, 3d (unknown engine: feasibility first)
Open: see Findings

Inputs from SARD (eliteRZX.txt): Elite.tap + 5 Fuse RZX (Docking, PoliceAnarchy, Havoc, Witch, Reidquat),
"Russian 128k Hack" with a "Mamba MkII" and a new "PuffAdder" ship. No .z80 was sent; each RZX's first
snapshot is the start state (`rzx extract`). Files live in specnext/reference/elite/ only.

## Findings (stage 0, DockingElite.rzx, `--stop 3000`)
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
- Longer survey of the other four recordings (coverage GATE: 29993, 39074 never reached).
- Stage-1 design question and feasibility (3d).

## Hardware checklist
None yet (no build).

## Stage log
2026-11-22  stage 0 (intake, Docking only)  ~30 min  ~25 calls  0 user rounds

## Lessons
- [deferred Open: reconsider when stage 1 feasibility shows whether a tail can be placed (--tail + scan --range)] A 128K snapshot with the 48K ROM locked in: `convert` found no place for the start-up tail and nextboot.check models 48K start-up only.

## Technique use
- detect.pacing-structure: used: survey flagged pacing (1726 interrupts in 3001 frames); not analysed further yet (2026-11-22)
