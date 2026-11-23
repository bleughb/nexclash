# Jack the Nipper (Gremlin Graphics, 1986) - stage 0 done; engine not yet written

## Next session
Stage: 1 (design)            State: intake done 2026-11-22 (survey below); no design yet
Inputs: TOSEC `Jack the Nipper (1986)(Gremlin Graphics Software).z80` (md5 adcdb8f9bb5e72218392aab8fd44e78e) and its
`[a]` (4c5398b8bcfd88ebd83656f01c3aca21); rzxarchive `j/jacknipper.rzx` (108,043 frames, 36 min; its own start
snapshot md5 903c092495784d308cf03899b80d7110)    Branch: add-jack-the-nipper
Checks: survey (GATE OK), inspect    Pending user answers: none yet (the stage-1 question comes with the preview)
Start with: the object record's position bytes and 0x87BB, the erase / restore at 0x8760, objects per room
(`cost --at 0x8009`)    Read: PLAYBOOK 2-3, 3d (an unknown engine: feasibility first)
Open: the figure plotter(s) behind the copier; where the figures' colours come from; a short recording (3-5 min) for
the design runs (the 36-minute one stays for the full verification)

## Snapshot (0b)
48K, in game (PC 0x908B in RAM; the recording's start 0x90AD), IM 1 with interrupts OFF (DI), I = 0x3F, SP 0x7FF7,
RAMTOP 0x7C60, border 0. No loader to run.

## Survey (2026-11-22, the whole recording)
- Engine: unknown (no detector, no TID / Dizzy 1 signature): a new engine, feasibility first (PLAYBOOK 3d).
- Rendering: 0x86F9 writes 92 % of the pixel bytes (507 bytes per call, 28,962 calls), the play area 256 x 128 from
  0xAC75, reading 0x7D00-0x7EFF and 0x6800-0x6FFF: a copier from a composed buffer or cell map. 0xAD99 (block copies,
  269 calls) and 0x7F84 (attributes, 9 calls) are screen set-up; 0xFFCD (8 bytes a call, x 48-215) is small and runs
  from 0xFF93 / 0xFFB1 / 0xFFC8 (top of RAM).
- Pacing: no interrupt accepted in 108,043 frames: nothing syncs the game to the frame, so hook time is game time
  (PLAYBOOK 4 "no frame sync"; card detect.pacing-structure).
- Coverage: GATE OK (every CALL site to the top plot routines in code that ran was reached).
- Plain conversion: boots in the simulator; no proven-safe tail yet (prove with `scan --range`).

## Stage 1 analysis (2026-11-22, first 15,000 frames)
- 0x86F9 is a dirty-cell copier, not a plotter: 512 cell counters at 0x7D00-0x7EFF (32 x 16 cells = the 256 x 128
  play area); for each marked cell it copies eight pixel rows from a shadow screen at 0x6000-0x6FFF to the display.
- The shadow is written by read-modify-write code at 0x80E5 / 0x80FD, 0x8199 / 0x81D4, 0x8299 / 0x82B7, 0x838B,
  0x865D (it reads each byte back first: masked sprite drawing, several variants), which marks cells at 0x812C,
  0x8209, 0x82F6, 0x845F; 0x8760-0x877C writes eight rows a call (x202,775: most likely the background restore).
- The sprite routine is 0x8009 (called from 0x92A9, 0xA71A, 0xA729 and the main loop at 0xAA44, which then runs the
  copier 0x86F9 and 0x8735), one object per call through IX: (IX+6) flags (bit 4: skip), (IX+2) type (bit 0: 16 or
  24 rows), (IX+5) animation frame (a 32 / 48 / 96 / 144-byte step into the graphics), (IX+7) / (IX+9) graphics and
  mask pointers; 0x87BB turns the position into a shadow address, then a 16-pixel-wide masked draw bottom-up (0x8781
  steps up a character row). Shared helpers: 0x8781 and 0x87A0 (8 callers each), 0x87BB (16).
- Model so far: shadow screen + dirty cells + masked sprites; figures take the room's attributes (0x7F84 sets them
  per room). Next: the plotters' entry points and inputs (x, y, frame), the restore's source, figures per room.

## Stage log
- 2026-11-22: stage 0, ~1.5 h wall (both games' surveys in parallel), ~20 tool calls, no user rounds.

## Lessons
- [none: stage 0 only: the survey answered every intake question it asks]

## Technique use
- detect.pacing-structure: used: the survey's no-interrupt finding names the no-frame-sync case for the design

## Friction
- reuse: [none: no code written at intake]
- retries: [none: the first survey run started outside the toolkit folder (module not found); rerun from it]
- environment: [none: no workaround]
- hand-rolled: [none: survey and inspect covered intake]
- scratch: [none: no scratch scripts]
