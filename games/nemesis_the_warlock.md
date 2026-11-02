# Nemesis the Warlock (Martech 1987, 48K) - https://spectrumcomputing.co.uk/entry/3387/ZX-Spectrum/Nemesis_the_Warlock

## Next session
Stage: 1 (design)           State: stage 0 intake done 2026-11-02 (survey GATE OK)
Inputs: specnext/reference/nemesis_the_warlock/ (snapshot from the RZX, rzx, survey)    Branch: claude/festive-einstein-sx8txv
Start with: read nemesis_the_warlock_survey/survey.md + preview.png      Read: PLAYBOOK stage 1 (2, 3, 3c, 4)
Open: back buffer source of the 0x7D9A blit (`scan --range BUF --writers`); figure plotter(s) inside 0x7D28 callers; screens below: confirm with user at stage 1

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

## Screens without play / over play (found in code 2026-11-02; user unsure)
- No pause and no window drawn over the play area found. Every non-play screen is FULL SCREEN
  (0x93E9 = clear + draw), so Layer 2 / sprites must be off or cleared while it shows:
  - Title + options menu: 0x921E draws it, JP 0x8F11 polls keys 1-5 (row 0xF7FE): 1/2/3 pick a
    control set (key table at 51960), 4 = define keys, 5 = start. Reached in the recording.
  - Define keys 0x8FE0-0x9080: full screen, prompts STAB / JUMP / DUCK / LEFT / RIGHT / MASSACRE
    (strings at 36993-37066). NOT reached in the recording (survey "untouched" 0x8FA7-0x90CA).
  - Message screen (call 0x93E9 at 0x702F, start of a game/level): green text on brown
    ("YOU MAY RUN BUT YOU CANNOT HIDE DEVIANT..."), seen in preview.png.
- In play: CAPS+SPACE (ROM BREAK-KEY 0x1F54 at 0x72C4) then SPACE -> 0x7300: if (byte) = 122
  draws via 0x7D31 and sets 4 attribute cells of the top panel row (22532/3, 22554/5) to 127.
  An in-play action on the ULA panel, not a pause; reached 21 times.
- Ask the user for a recording that uses "define keys" (option 4) if that screen must be proven.

## Decisions
(none yet - stage 1 question)

## Lessons
- [local: one-off extraction; a later game with only an RZX should add an `rzx extract` command] SPIN RZX snapshot blocks are zlib-compressed Z80 (flag 2); extracted with a 10-line block parse; no CLI command extracts the first snapshot to a file.

## Technique use
- detect.buffer-layout-producer: used: not yet (stage 1 will need it for the 0x7D9A back buffer)

## Stage log
- 2026-11-02 stage 0: ~2 h wall (survey ~1.8 h for 135K frames), ~25 tool calls, 4 user rounds; menus found in code.
