# Cauldron (Palace Software, 1985; 48K) - no engine yet (stage 1: design question sent)

## Next session
Stage: 1 (design) waits for the user's answer; then 2 (build)    State: question sent 2026-10-26
Inputs: specnext/reference/cauldron/ (Cauldron_1985_Palace_Software_a.z80, cauldron.rzx)
Branch: claude/cauldron
Start with: record the answers under "Decisions"; settle Q0 (which start snapshot) BEFORE any build
Read: PLAYBOOK stage 2, this file, docs/techniques/patch.xor-overlay-keep-ula.md,
  then patch.display-atomic-switch.md (deferred card, see Patch plan)
Open: Q0-Q5 below; bit-level POINT check (only if a shadow design is ever reconsidered)

Reference: specnext reference/cauldron/. Status: stage 0 + stage 1 analysis done 2026-10-26
(technique-card pilot). Analysis scripts are scratch (not in the repo): a one-off screen-reader
probe (detect.gameplay-screen-readers has no shared command yet, BRIEFING C2 candidate).

## Inputs (2026-10-26)
- Cauldron_1985_Palace_Software_a.z80 (39,878 bytes, 48K), cauldron.rzx (89,595 frames, ~30 min,
  1 segment, no autosaves, no desync).
- **The RZX does not start from this .z80** (observed, 2026-10-26): its embedded Z80 snapshot has
  the same screen and entry (0x6018 `JP 0x63F8`) but 11,283 bytes of 0x6018-0xFFFF and 711 bytes
  of sysvars/BASIC differ: the compiled-BASIC body (0x6D9E-0x7Fxx at least) is laid out
  differently (e.g. `CALL 0x6275` sites at 29140/29149/29164 in the RZX's copy, 29191/29200/29215
  in the .z80). A different build or variant of the game. Everything the survey and the probes
  measured is the RZX's copy. Identical in both (checked at frame 2000): 0x6275 helper, 0x6357
  plotter, 0x61D8-0x61FF PEEK/POINT, 0xB29C-0xB380, 0xC9D8-0xC9F3, 0xCE74-0xCE90, 0xDED2-0xDF30.
  -> Q0 in the design question.

## Snapshot facts (PLAYBOOK 0b)
- 48K, IM 1, I = 0x3F, DI (an interrupt was just accepted: PC 0x0038, stacked return 0x613E is
  game code), SP 0x5FF6, border 0. RAMTOP 24599; game 0x6018-0xFFFF resident.
- `inspect` WARNING "loader snapshot" is a false positive here: the BASIC loader (tape load to
  0x6018 then `JP 0x6018`) is still in memory and PC is in ROM only because of the interrupt.
- ISR: ROM IM 1 only, 89,377 interrupts, 126 distinct handler instructions, all in ROM (observed,
  whole RZX). Reads IY (keep IY), needs >= 18 free stack bytes. MMU slots touched 0 and 2 only;
  1, 3-7 never. 0x63DB sets IM 2 (vector table 0xFEFF -> 25576) - never executed in this
  recording (unknown handler).
- Free RAM (local evidence only): 0x5B02-0x5BFF, 0x5D52-0x5FB9, 0x62DE-0x6347, 0xA306-0xA49B,
  0xBDA6-0xBDF5. Lowest SP 0x5FBA. Plain .nex: no proven-safe tail (converter default), boot OK.
- Main program is compiled BASIC (inferred from its runtime): 0x61D8 PEEK (`LD L,(HL)`), 0x61DB IN,
  0x61F1 POINT (ROM PIXEL-ADD + bit test), 0x6275 USR-style indirect call (`CALL 0x627B` ->
  `JP (HL)`), 0x627E RND, 0x6130 multiply, 25089 ATTR(y,x).

## Rendering model (PLAYBOOK 2)
Coverage gate: 2 unreached `CALL 0x6275` sites, both non-figure: 40167 (CLS + 0xC4AE: ROM
PR-STRING of a 162-char message, a text screen) and 31131 (USR (41337) = (41321)+142/166 =
57042/57066, the scrollers below, reached via other sites; (41321) = 56900 all recording). No new
recording needed for coverage.

Observations (basis / scope; scope = cauldron.rzx 89,596 frames unless stated):
| # | Routine | Observation | Basis |
|---|---|---|---|
| 1 | 0x6357 figure plotter (14 callers) | target ULA bitmap + attributes, direct (no back buffer) | observed (static + writers) |
| 2 | 0x6357 | composition XOR: all pixel writes XOR the old byte (0x63BE/0x63C2 `XOR D/E` shifted pair, 0x63CD `XOR (HL)` aligned) | observed (static) |
| 3 | 0x6357 | attributes: per cell, overwrite when the old attr equals ATTR-T (23693) or the graphic's; type 2 via ROM PO-ATTR 0x0BE4 | observed (static); exact rule inferred |
| 4 | 0x6357 | lifecycle: paired draw/erase - callers in matched pairs 38810/39537 (19,865/19,587), 27799/31236 (12,448/12,407), 35390/35210 (9,390/9,389), 39708/39824 (380/375), 28441/28585 (234/234); unpaired 31115 (276), 40860/40577/40483 (20/14/10) | inferred (counts) |
| 5 | 0x6357 | tracked unit: one call = one whole image from a descriptor at HL (graphic ptr, x, y, rows, width per row, drawn upward) | inferred (static); partial draws unknown |
| 6 | 0x6357 | object identity: descriptor pointer HL per caller | observed (static) |
| 7 | 0x6357 | cost: median 23,090 T, max 55,615 T per call (~1/3 frame); 84,629 calls in 59,155 frames | observed |
| 8 | 0x6357 | execution: main loop only (ISR is ROM, calls no game code) | observed |
| 9 | gameplay readers | POINT reads bytes holding figure bits: 114 of 530 POINT reads (0x6B87/0x6BA8 = POINT(px-1, py-18) around the position in 41297/41355; 0x9DE1, 0x9E3F) | observed at byte level; bit level inferred |
| 10 | gameplay readers | ATTR reads cells the plotter painted: 3,794 of 37,416 attr PEEKs (0x9077-0x90FC: ATTR of the 4 neighbours of (41537,41539) -> 41527...; 0x6B39/0x6B56: ATTR(21,28)/ATTR(21,4) = 65) | observed (painted-cell tracking) |
| 11 | other writers on figure bits | ROM PO-CHAR 0x0BBC 15,777; tile writer 0xB378 1,204; ROM CLS 0x0E59 6; clear 0xB2A6 1. On figure-painted attrs: 0xC9F0 47,955 (bottom-third attr restore), 0xCE7F 16,061 (6x5 attr box at 0x58E6), ROM 0x0E80 24 | observed |
| 12 | 0x6275 USR helper (17 sites) | not a plotter: routes to overwrite writers - 0xDED2/0xDEEA byte-step scroll of the bottom third (0x5000, 64 rows) + 0xDF04 its attributes; 0xB366 8x8 tiles (font at (45970)); 0xB2A0 clear 0x4800-0x57FF + attrs; 0xC9DB/0xC9E7 save/restore bottom-third attrs (51700); 0xCE74 attr box; 0xC4AE text screens. 4 caller groups draw nothing (logic) | observed |
| 13 | text | ROM printing (0x0B24 via PRINT-OUT 0x162C): HUD and messages; ROM CLS 0x0E44 | observed |
| 4b | 0x6357 figure kinds (preview --plot 0x6357, frames 1-44,800) | paired movers over the play area: 0x6C9A/0x7A07, 0x898D/0x8A41, 0x979D/0x9A74, 0x6F1C/0x6FAC; a fixed 24x24 image at x 96-119, y 107-130 (0x9B1F/0x9B93); unpaired bottom-left x 24-95, y 144-175 (0x798E); a plot into the HUD's top-right scroll x 216-247, y 0-23 (0x9E84, the collected-item icon); 0x9F9F (5 calls) | observed; which figure is which: from the sheet, not settled |
| 14 | hazards | self-modification at sites: not checked (no LD (nn) scan yet); IM 2 path at 0x63DB not reached | unknown |

## Patch plan (STANDARD 4-5; cards opened: 3)
Index read whole; cards opened: detect.gameplay-screen-readers, patch.xor-overlay-keep-ula,
patch.xor-shadow. Others judged from index.json `requires`/`rejects` only.

Figure routine 0x6357 (all 14 callers):
- detect.gameplay-screen-readers - applied: `screen.gameplay_reads_figure_pixels` = TRUE
  (obs. 9: byte level observed, bit level inferred; whole RZX), and attribute readers of
  figure-painted cells exist (obs. 10).
- **patch.xor-overlay-keep-ula - eligible pending the stage-1 answer.** `render.composition.xor`
  TRUE (obs. 2); `design.figures_in_front` UNKNOWN -> its probe is the design question (Q2). XOR
  already shows figures over the scenery, so "in front" matches the original's look.
  Its probe step 3: attribute painting has readers (obs. 10) -> painting cannot simply be removed
  (Q3). Step 4: plots last ~1/3 frame (obs. 7) -> patch.display-atomic-switch applies (deferred).
- patch.xor-shadow - REJECTED: rejects `screen.gameplay_reads_figure_pixels` (TRUE, obs. 9; the
  ULA would no longer hold the pixels POINT tests). Requires were true (XOR; slots 1, 3-7 free).
  Revisit only with a bit-level POINT check that comes out false.
- patch.scratch-redirect - REJECTED: `render.target.back_buffer` FALSE (obs. 1).
- patch.isr-deferral - REJECTED: `exec.isr_calls_routine` FALSE (obs. 8, whole RZX); unknown
  only for the unreached IM 2 handler at 25576.
- patch.display-atomic-switch - deferred to stage 2: `hook.updates_visible_image` is TRUE for an
  overlay build (sprites move at the plot); not opened (3-card limit).
- optimise.pattern-cache - deferred to stage 2: `sprite.working_set_fits` UNKNOWN, probe `cost
  --at 0x6357 --group` (no need yet: ~1.4 plots per active frame).
- detect.tracked-unit - not opened; obs. 5 from the code (whole image per call).

Scenery / tile / scroll / clear writers (0x6275 targets, obs. 12) and ROM text (obs. 13): no card
fits (no card covers overwrite scenery writers; they stay on the ULA by default 2). They matter
only as the "other writers" of obs. 11, which the overlay's sprite model must follow (ULA stays
original, so behaviour is unaffected; the residue the original leaves is what the sprites cover).

Attribute painting with readers (obs. 10): no card covers a virtual attribute read; decision
table 4 "Logic reads player pixels -> virtual read" is the nearest row. Lesson candidate below.

## Design question (sent 2026-10-26) - answers go to "Decisions"
Q0 Start snapshot (exception): build from the RZX's embedded snapshot (the copy the recording
   proves; proposed) / record again from the .z80 / build from the .z80 unverified (not offered).
Q1 Every figure a sprite (default 1): all 0x6357 callers, incl. the cauldron-spot image and the
   HUD item icon (exception: ask whether the HUD icon stays on the ULA).
Q2 Depth (default 3 = the game's rule): XOR has no depth rule; figures in front (overlay) proposed.
Q3 Figure-cell attribute painting (exception): keep it (clash halo stays, zero risk to the ATTR
   tests) / remove it + virtual attribute reads for the ATTR readers (no halo, bigger build).
Q4 Colours (default 4): the figure's cell ink until painted.
Q5 Menus / message screens (default 5): Layer 2 + sprites off on the text screens (0xC4AE family)
   and the control menu. Always-ask: no bullets/explosions seen in 0x6357's groups; solid vs
   see-through; outline.
Sheets: preview.png (survey) and preview_6357.png (per caller; scratch, regenerate with
`preview ... --plot 0x6357 --at 3000,8000,15000,22398,33597,44796 --stop 44800`).

## Decisions
(none yet)

## Open
- Q0-Q5 unanswered.
- Bit-level check of the POINT readers (obs. 9) if a shadow design is ever wanted.
- LD (nn),A / LD (nn),HL scan of 0x6357 and its call sites before choosing hook sites (stage 2).
- IM 2 path (0x63DB, handler 25576): when is it used? Not in this recording.

## Lesson candidates
- `inspect` flags "loader snapshot" when PC is in ROM because an IM 1 interrupt was just taken
  with the BASIC loader still in memory (Cauldron): check the stacked return address before
  treating it as a loader.
- An RZX's embedded snapshot can be a different build of the game than the .z80 delivered with
  it (Cauldron: 11,283 bytes differ, code shifted): the survey analyses the RZX's copy. The survey
  could compare the two start states and warn (BRIEFING C2 candidate).
- Compiled BASIC games read the screen through runtime PEEK / POINT / ATTR routines: find those
  routines first, then classify reads by their return address (Cauldron).
- Figure-cell attribute painting can have gameplay readers (Cauldron ATTR neighbour tests); a
  card for "virtual attribute read" would cover keeping clash-free colours with such readers.

## Stage log
- 2026-10-26 stage 0+1 (survey, patch plan, design question; pilot): see Pilot log.

## Pilot log
Technique-card pilot, stage 0 + 1, one session, 2026-10-26.
- Tool calls: ~85 (incl. 4 failed: survey started from the wrong cwd (module not found), an rm
  stopped by the safety check, a chained sleep blocked, a scratch script named dis.py shadowing
  the stdlib `dis`).
- Wall time to the design question: ~78 min, of which ~58 min the survey (89,596 frames; the
  PLAYBOOK rate holds: ~15 min per 18K frames). Probes: screen-reader pass 10 min, per-caller
  preview (44,800 frames) ~6 min, memory diffs < 1 min each.
- Files read more than once: LEARNINGS.md x2 (two different 10-line spans), survey.json x2
  (queries). Each doc, card and survey.md read once.
- Cards opened (3): detect.gameplay-screen-readers, patch.xor-overlay-keep-ula, patch.xor-shadow.
  Judged from index.json alone (5): scratch-redirect, isr-deferral, display-atomic-switch,
  pattern-cache, tracked-unit. Engine modules of other games read: none.
- Card choices later corrected: none. Static disassembly of the .z80 was partly stale (the RZX is
  a different build); the routines the cards rest on were checked identical in both.
- What cost the most besides the survey: finding the .z80 / RZX mismatch only at call ~60 (after
  disassembling the .z80). A start-state comparison belongs in the survey (lesson candidate).
- User rounds: 0 so far (the design question is round 1).
