# Atic Atac (Ultimate Play The Game, 1983; 48K) - engine: not yet (stage 1: design asked)

## Next session
Stage: 1 (design, waiting)  State: analysis done, design question sent 2026-10-26 (Engine, Decisions)
Inputs: specnext/reference/atic_atac/ (snapshot, AticAtac.rzx)    Branch: claude/atic_atac (both repos)
Start with: record the user's answer under Decisions; then stage 2 (build)
Start state: the .z80 run to JP 24576 (simrun.free_run(z80, 400, None, stop_pc=24576), get_state,
  write_snapshot); the RZX needs no prerun (its own snapshot is mid-game)
Read: PLAYBOOK stage 2, docs/ENGINE_CONTRACT.md, this file; Dizzy 1 (1-bit shadow screen) as template
Open: the design answer; test cheat (offered); game-over path not recorded

Reference: specnext reference/atic_atac/ (Dean, 2026-10-26).

    python -m nexclash.survey Atic_Atac_1983_Ultimate_Play_The_Game_a.z80 --rzx AticAtac.rzx

| Output | MD5 | Status |
|---|---|---|
| atic_atac.nex (plain, tail 0x5B00) | e710fa8785802f1aa51f214d95c82343 | boot sim OK; hardware untested |

## Intake (stage 0, 2026-10-26)
- Snapshot: 48K, LOADER state. PC 0x5B89 inside a descramble loop at 0x5B80 (USR 23424 from the
  one-line BASIC loader): `LD HL,24575 / LD BC,124 / XOR A / RRD / INC HL / DJNZ / DEC C / JR NZ`,
  then `JP 24576` (game entry). IM 1 (ROM ISR), I = 0x3F, SP 0x5FE7, RAMTOP 24574, border 0.
- CORRECTION (stage 1, 2026-10-26): the RZX embeds its OWN snapshot (rzxinfo: start address 41446 =
  0xA1E6, game running, code already descrambled); only the .z80 is at the loader (PC 0x5B89).
  So no prerun is needed for the recording; the nex start state is the .z80 run to JP 24576
  (simrun.free_run stop_pc=24576, 2 frames) written with get_state/write_snapshot. loader.prerun's
  test sees memory only and, on this RZX, returns frame 0 = the embedded snapshot.
- Recording: AticAtac.rzx, 18,278 frames (6 min), no autosave snapshots, no desync. Plays to the
  escape ("Congratulations, you have escaped", 5:46, score 8060, 39%). Rooms with stairs, doors,
  monsters, the chicken meter and the scroll panel all seen (preview.png).
- Engine: unknown (identify). ISR: ROM IM 1 only, reads IY (keep IY), 16 bytes below SP.
- Lowest SP 0x5DD8 (whole recording, loader phase included).

## Screen writers (survey, routine -> what it draws)
| Routine | Calls | What (preview) |
|---|---|---|
| 0x9F21 (40737) from 0x9EAC | 557,574 | figures (monsters, player, items): byte plotter, 178 T median |
| 0x9EDC (40668) from 0x9EA3 | 546,381 | figures, second plotter (pair with 0x9F21: draw / erase or the two shifts) |
| 0x9C61 (40033) from 0x9D08 / 0x9C5D / 0x9CC7 | 183,564 | room outlines: one byte per call (line drawing) |
| 0x8093 (32915) from 0x9150 / 0x973D | 126 | play-area clear (24 x 192 bytes) on every room change |
| 0x9980 (39296) from 0x920E | 38,939 | attributes only (room / figure colours) |
| 0x7EB2 (32434) from 0x7DE7 / 0x7E0E | 14,847 | attributes of the side panel (x 200-247: chicken, lives) |

Coverage GATE: one unreached CALL, 35893 (0x8C35) -> 0x8093, reached by `JP Z,35893` at 36516. It
is the GAME OVER path: clear the play area, print "GAME OVER" (string at 35929 via 41459), wait,
`JP 31785`. Not a figure plotter -> the gate passes; the game-over screen is untested by the
recording (stage 3 checks it with a test cheat off, or a second recording that loses every life).

## Engine (stage 1 analysis, 2026-10-26; start state = .z80 run to JP 24576)
- Rendering model: PURE XOR to the screen for every figure. Two row blitters, 0x9EDC (40668) and
  0x9F21 (40737), one CALL site each (0x9EA0 / 0x9EA9) inside the row loop at 0x9E9B; each call XORs
  one row of 2-3 bytes. The pixel shift is a self-modified JR at 0x9EE4 / 0x9F29 (written at 0x9F91
  = 40849: LD (40677),A), shared row-advance at 0x9F03. Figure-level entries: 0x9F40 / 0x9F45 /
  0x9F4A / 0x9F56 / 0x9F74 / 0x9F80 (draw object IX). Object records at 0xEA90.. (IX groups in cost).
- No logic reads figure pixels (figdep, whole recording): every non-plotter read of a byte holding
  figure pixels is a drawer's own read-modify-write - room-line OR (HL) 0x9C75 x1150, and the
  scenery-object drawers' run-time op (XOR/OR (HL)) at 0x99D7 x265, 0x9A78 x83, 0x9B88 x16,
  0x9ADD x14, 0x9A36 x2. No collision or decision reads the screen -> no virtual read.
- Writers that change figure bits (they break ULA = scenery ^ figures):
  0x809F play-area clear 0x8093 (room change 0x914D / escape 0x973A / game over 0x8C35);
  0xA190/0xA193 = 0xA185, zero a 2x20 cell then re-plot via 0x9F4A (IX = 0xA17D; from 0xA16E and the
  3-slot loop at 0xA2F3: the pocket icons in the panel);
  scenery-object drawers 0x99D8 / 0x9ADE / 0x9B89 / 0x9A79 / 0x9A37 (op at the NOP before each
  picked by 0x9D19: B&3 = 0 LD, 1 OR, 2-3 XOR (HL)); room-line OR 0x9C76; text printer 0xA1E6
  (8-row glyph LD (HL),A; the escape message over the play area, frame 18184).
  Counts, whole recording (writes / of them changing figure bits): 0x809F 17894/9587, 0xA190
  3834/3834, 0xA193 2200/2200, 0x9C76 1150/145, 0x99D8 712/343, 0x9ADE 475/209, 0x9B89 447/188,
  0x9A79 332/169, 0x9A37 16/7, 0xA1E6 15/3.
- Panel: only the pocket-icon record IX 0xA17D plots into the panel (cols 25-30, panelix, frames
  1-2500); every other figure record stays in cols 0-22.
- Colour = attribute painting: per figure 0x91FE -> 0x9980 (paint, table 0x9985 -> 0x9D25..0x9E55;
  0xFF entries take (24090)) and 0x9962 -> 0x7E85. That painting IS the clash (wall lines in a
  figure's cells take its ink, plain.png frames).
- Scenery on the ULA: room outlines 0x9C61 (OR, from 0x9D08 / 0x9C5D / 0x9CC7), objects above,
  panel 0x7EB2 (attrs, x 200-247: chicken), play-area clear 0x8093.
- Cost: plotters 0x9F21 / 0x9EDC median 247 / 235 T per row call, ~10 % of frame time each;
  typical frames 18 or 34 calls, busiest 85-86 -> hook per FIGURE (the 0x9F4A.. entries), not per row.
- ISR: ROM IM 1; reads IY; 16 bytes below SP; never touches slots 1, 3-7. Lowest SP 0x5DD8.
- Free RAM (survey, whole recording): 0xD2EE-0xEA8F (6050 bytes), 0xB786-0xBA57, 0xB536-0xB6F1,
  0xBB60-0xBCCD, 0x5B00-0x5BFF, 0x5CB1-0x5DD7.
- Planned pattern (decision table): 1-bit shadow screen (Dizzy 1 row): converted XORs go to the
  shadow, ULA ^ shadow = original; non-XOR writers above fold their change into shadow / ULA; play-
  area clear empties both and hides every sprite; attribute painting of figure cells skipped
  (colour moves to the sprite). Design to be confirmed by the stage-1 answer.

## Decisions
(pending: stage-1 design question sent 2026-10-26)

## Open
- Menus / message windows over the play area: asked 2026-10-26 (pause? the inventory?).
- Test cheat (immortality / no chicken drain): offered 2026-10-26.
- Game-over path (35893) not in the recording.

## Lesson candidates
- A .z80 at the loader does not mean the RZX is: an RZX carries its OWN start snapshot (rzxinfo
  "Start address"); the survey and every --rzx analysis start there. Stage 0 read the .z80's loader
  state as the recording's and planned a prerun that was not needed (loader.prerun then "finds"
  frame 0). Check `rzxinfo` in stage 0 before calling a recording loader-stage.
- A run-time screen-dependency check for an XOR engine is cheap with simrun hooks: shadow ^= each
  plotter delta, report non-plotter reads / writes where shadow != 0 (figdep, ~15 min for 18K
  frames). Candidate for a shared `scan --xor-owner ENTRY` option (BRIEFING C4).

## Stage log
- 2026-10-26 stage 0 (intake): ~20 min wall, ~30 tool calls, 0 user rounds.
- 2026-10-26 stage 1 (design): ~1 h wall, ~60 tool calls, 1 user round (the design question).
