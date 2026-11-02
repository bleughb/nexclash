# Nemesis the Warlock (Martech 1987, 48K) - https://spectrumcomputing.co.uk/entry/3387/ZX-Spectrum/Nemesis_the_Warlock

## Next session
Stage: 1 (design)           State: stage 0 intake done 2026-11-02 (survey GATE OK)
Inputs: specnext/reference/nemesis_the_warlock/ (snapshot from the RZX, rzx, survey)    Branch: claude/festive-einstein-sx8txv
Start with: read nemesis_the_warlock_survey/survey.md + preview.png      Read: PLAYBOOK stage 1 (2, 3, 3c, 4)
Open: back buffer source of the 0x7D9A blit (`scan --range BUF --writers`); figure plotter(s) inside 0x7D28 callers; menus/windows (ask user)

## Facts
- Inputs: only a SPIN 0.6 RZX (1 segment, 134,980 frames, no autosaves). Its embedded Z80 snapshot
  is the .z80 (LEARNINGS 2.4); no separate snapshot from the user.
- Snapshot: 48K, PC 0x6FDD (RAM, in game code after load), IM 1, DI, I=0x3F, SP 0x6FA0, RAMTOP 28599,
  entry USR 28600. Interrupts never accepted in the whole recording (game runs DI).
- Survey: engine unknown; GATE OK. Play area 0x7D9A = block copy of a back buffer (68,314 T/call,
  27,656 calls) -> back-buffer game; 0x7D28 = 8-byte cell plotter (224K calls, 11 callers);
  0x80D6 attrs; 0x93E9 full-screen draw (title/message screens); 0x954D status panel.
- Plain conversion: simulated boot OK; tail location not proven safe (survey WARNING) - prove with
  `scan --range` at stage 1.
- Screens seen (preview.png): play area with yellow-on-olive platforms, status panel "THE DEATH OF
  TORQUEMADA", a message screen (green text on brown).

## Decisions
(none yet - stage 1 question)

## Lessons
- [local: one-off extraction; a later game with only an RZX should add an `rzx extract` command] SPIN RZX snapshot blocks are zlib-compressed Z80 (flag 2); extracted with a 10-line block parse; no CLI command extracts the first snapshot to a file.

## Technique use
- detect.buffer-layout-producer: used: not yet (stage 1 will need it for the 0x7D9A back buffer)

## Stage log
- 2026-11-02 stage 0: ~2 h wall (survey ~1.8 h for 135K frames), ~25 tool calls, 3 user rounds.
