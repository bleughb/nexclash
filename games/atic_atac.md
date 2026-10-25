# Atic Atac (Ultimate Play The Game, 1983; 48K) - engine: not yet (stage 0 done)

## Next session
Stage: 1 (design)           State: intake done 2026-10-26, coverage gate passed (Intake below)
Inputs: specnext/reference/atic_atac/ (snapshot, AticAtac.rzx)    Branch: claude/atic_atac
Start with: `python nexclash.py auto <z80> --rzx AticAtac.rzx --no-record` (engine unknown -> the generic path)
Then: loader.prerun(rzx, test=PC reached 24576) -> in-engine snapshot (no CLI: call it from Python, as nexclash.py's Dizzy V path does)
Read: PLAYBOOK stage 1, this file, the survey (re-run it, ~15 min: 18,278 frames)
Open: menus / windows over the play area (user); test cheat (offered); game-over path not recorded

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

## Decisions
(none yet - stage 1 asks the design question)

## Open
- Menus / message windows over the play area: asked 2026-10-26 (pause? the inventory?).
- Test cheat (immortality / no chicken drain): offered 2026-10-26.
- Game-over path (35893) not in the recording.

## Lesson candidates
(none yet; the survey's run time for a long recording went straight into PLAYBOOK stage 0)

## Stage log
- 2026-10-26 stage 0 (intake): ~20 min wall, ~30 tool calls, 0 user rounds.
