# R-Type (128K) - intake

## Next session
Stage: 1 (design/feasibility). State: visual design approved; architecture under independent review.
Inputs: ../specnext/reference/r_type/Rtype.z80, Rtype.rzx, Rtype.tap (hashes below).
Branch: add-r-type. Base: 931458b9d65a76cf1f8bfebacbe57e7f33807397.
Checks: bounded survey, full-recording caller census, canary and doccheck PASS;
tools check has one pre-existing Inferno audit failure (Checks below).
User answer 2026-11-10: defaults 1-5; every effect a sprite; see-through bodies; no outlines.
Start with: PLAYBOOK stage 1 and the feasibility findings below.
Open: credits classification, protected-pattern capacity, whole-hook timing and full ISR memory proof.
JNext 1.2.0 runs; SD card absent. Owner agreed to allow www.specnext.com; policy application pending.

## Inputs
The attached TAP is a tape, not a snapshot. The build start state was extracted from the
attached RZX with `nexclash.py rzx extract`, as MAINTAIN specifies. Originals and derived
game files stay in specnext, never this repository.

| File | Bytes | MD5 |
|---|---|---|
| Rtype.tap | 132823 | 2d1e17efa08a303dc4bb783278f8cfd9 |
| Rtype.rzx | 320136 | fb4a142aa9fee684dfbfd7650d6b22bf |
| Rtype.z80 | 111966 | 5a2179b4006d7888a1f7f821a4316bf5 |

## Facts and evidence
- Observed: 128K snapshot, PC BE24, SP FFF6, IM 2, I=84, interrupts disabled;
  7FFD=10 (ROM 1, bank 0), technical-specification screen. No existing engine recognises it.
- Observed: one RZX segment, no autosave snapshots, 90,102 frames (30:02.04 at 50 Hz).
  Full C-simulator screen/caller replay completed without desync. Contact sheet samples
  frames 1, 500, 2000, 5000, 10000, 20000, 30000, 40000, 50000, 60000, 75000, 90000;
  later levels and a return to the level-1 loading sequence are visible.
- Observed in the first 2,001 frames: screen refresh 8842 copies/clears dirty cells from
  a buffer at screen address +2000 and shifts selected screen spans. 8979 calls it at entry.
  BE97 draws the stars; C084 prints text. FDEF clears memory, not a figure plotter.
- Observed in original frames 2000-2500: buffer scan flags 8D2F..8D4B and 8E06/8E0F;
  disassembly identifies four cell plotters, 8CFD / 8D65 / 8DD3 / 8E29, with flip variants.
  The shared 8EC2 path also performs collision-related cell checks; 8EA2 changes cell maps.
  Removing original plotter effects has NOT been proven safe.
- Observed: full caller census reaches 8979 18,202 times and 8842 18,576 times;
  C290 (the level-transition caller) eight times. The initial survey falsely marked the
  CALL at 8979 unreached: its tracker skipped CALLs at routine entry. The tracker is fixed.
- Plain: Rtype.nex, MD5 657362a108b54e5080cb88ccf2dcfdc6, 147,968 bytes; tail 5B00..5B4E.
  `intake/plain.py` restores printer data in the stub before copying the tail. Rainbow's 128K
  checker and nextboot pass with/without NEXLOAD, including a separate R check. Removing restoration
  from the built stub catches 176 RAM differences (5B4F onward). Hardware untested; no sprites yet.
- Full access scan: 90,102 frames; ROM 1F00..3FFF never accessed; printer spans 5B00..5B63 and
  5C4C..5CAF never accessed. Tail 5B00..5B4E fits. No full ISR-specific access proof yet.

## Coverage
Full C-simulator census: 90,102 frames, no desync, all 17 static CALL candidates to the
four figure plotters reached. Initial-only gaps A540, 9183 and 9A11 are covered by later play.
This establishes observed caller coverage, not an assertion that every game branch was visited.
Banked high-address PC counts do not distinguish code images; hook-site byte validation remains required.

| Plotter | Calls | Static caller candidates (all reached) |
|---|---|---|
| 8CFD | 328871 | 917A, 959A, 9A01, 9A9D, A540, C3A9, C443, F591, F6D9, FF52 |
| 8D65 | 17323 | 9183, 9A11 |
| 8DD3 | 30591 | 918C, 959F, 9A09 |
| 8E29 | 9147 | 9191, 9A19 |

The corrected bounded survey covers the first 2,501 frames; the buffer scan covers 500
original frames from 2000. The full survey started with the old tracker was cancelled when
its defect was found; a separate full-recording access scan subsequently completed (Facts above).
921E / 9227 / 9230 call the memory clearer, not a figure plotter; none runs in the full RZX.
The corresponding clear sequence needs a later unit test; it is not missing figure coverage.

## Design approval (2026-11-10)
Approved together: every figure (ship, Force, enemies, bosses); scenery/HUD/text on ULA;
original depth and pace; original inks until painted; added graphics off for menus/pause.
Explicit answer: all effects as sprites, see-through figures, no outlines.
The original-recording contact sheet is the intake preview, not a simulation of a sprite build.

## Feasibility
Visual design approved; no architecture selected. Required next: caller/text classification,
whole-hook timing budget and DMA/DDMA ownership/fallback evaluation (docs/DDMA.md).
The shared routine_skip probe supports only 48K, so it cannot establish removal safety here.
Preliminary pacing census on frames 2000-2500: 150 updates; 113 take 3 frames, 26 take 4,
11 take 5; median 205,413 T, maximum 360,652 T (uncontended). Wait at 868C polls 7A8A
until >=3; main loop 8649 resets it. Measured slack on 47 waits: min 333 T, median 26,797 T.
The probe reports beeper writes at FAA2 and FB52. These are NOT a whole-game hook budget.
Removal (`intake/removal.py`): 35 live copier states sampled every 2,500 frames through 87,444.
Clear selected source pixels/paper, run original 8842, restore temporary sources: all registers
including R, non-ULA RAM and the predicted clean ULA agree exactly. This proves the sampled algorithm
without interrupts, not an assembled hook. Nonlinear pixels occupy 6000..6FFF plus the low 128 bytes
of each page 7000..7700; never restore 6000..77FF wholesale (gaps hold variables such as 71D0).

First screen-aligned 16x16 proposal: 126 sprites, so a 64-pattern split buffer fails; protected
old+new patterns peak at 221 (canonical review: 219), above 128. PLAYBOOK 3d review requested;
owner explicitly authorized one reviewer. The worst frame is THANK-YOU text plus flying figures.
Text belongs on ULA: owner 1..DB alone misclassifies it. Owner88 is text here but normal enemies
elsewhere: never exclude that owner globally. Text plot: 8CFD from917A, HL=CAFF, D=21,E=24,
frame32 resolved by8E85, C4BA=D99C. Reviewer is checking this graphic identity before remeasuring.
Owner-aligned packing without classification can require144 sprites and is not an approved substitute.

DMA/DDMA remains an evaluation, not a selected route: the four plotters copy 8-pixel cell
graphics and update collision maps; DDMA cannot generate those maps or unpack ZX bits.
Evaluate cached sprite uploads with ordinary DMA and eligible rectangle work with gated DDMA,
using the shared policies (including no-blitter and CPU fallback), after the dependency probe.

## Checks
- `selftest.py --canary`: PASS, both Chuckie Egg rebuild checksums unchanged.
- `selftest.py --tools`: new entry-CALL regression PASS; existing Chuckie survey golden PASS;
  overall FAIL on the unchanged Inferno IFF audit (asm/inferno_hooks.asm lines 5722, 5726, 7563).
  Neither that source nor hooklib.py differs from the session base. No other game was modified.
- `tools/doccheck.py`: PASS (146 docs; existing warning about a split module name in another game's notes).
- Full recordings replayed by both caller censuses: 90,102 frames each, no desync.

## Hardware checklist
Plain above: try CSpect first, then controls, sound, level loading and restart on the Next.
Boot and tail checks pass; real NEXLOAD/hardware untested. Sprite pace, music, controls,
level transitions, death/restart and display
checks belong to the eventual sprite build; no hardware result is claimed.

## Technique use
- detect.pacing-structure: used: preliminary census locates the three-interrupt wait and beeper writers.
- detect.routine-removal: helped: identifies the required dependency experiment; existing probe is 48K only.
- detect.buffer-layout-producer: helped: separated final copier, nonlinear source cells and non-pixel holes.

## Lessons
- [tool nexclash.survey] Observed: a CALL as a routine's first instruction was never tracked;
  R-Type 8979 -> 8842 exposed the false coverage gap. Removed the early return and added a golden check.
- [local: tile plotters] Observed: screen-writer ranking identifies the refresh, not the figure
  plotters; scanning its source buffer locates the four tile drawers. No removal-safety claim yet.
- [local: credits share an enemy slot] Independent review: peak owner-grid scene includes THANK-YOU
  text. Match graphic identity, not a globally excluded owner; revised budget pending.

## Friction
- reuse: [none: existing survey, scan, preview and census tools provided the investigation paths]
- retries: [tool nexclash.survey] Fixed missing entry CALL tracking before trusting caller coverage.
- environment: [local: session dependency selection] SkoolKit 10.2 changed the C trace callback
  to five arguments; this session uses 10.1 in ../venv101, within the project's declared range.
- hand-rolled: [none: disassembly used sna2skool; screen images used the existing preview renderer]
- scratch: [local: per-game feasibility evidence] Game-specific experiments kept beside the inputs
  in specnext/reference/r_type/intake; none added as an untested shared toolkit probe.

## Stage log
- 2026-11-10 Stage 0: ~13 min wall, ~65 tool calls, one design round pending. Source refreshed
  at 931458b; original attachments preserved, snapshot extracted, full screen replay and
  caller censuses, bounded surveys, tracker fixed and regression checked. No sprite build yet.
- 2026-11-10 Stage 1 in progress: owner approved all effects, see-through, no outlines; authorized
  one capacity reviewer. Full access scan and plain NEXLOAD boot/negative proof pass.
