# Jack the Nipper (Gremlin Graphics, 1986) - stage 0 done; engine not yet written

## Next session
Stage: 1 (design)            State: intake done 2026-11-22 (survey below); no design yet
Inputs: TOSEC `Jack the Nipper (1986)(Gremlin Graphics Software).z80` (md5 adcdb8f9bb5e72218392aab8fd44e78e) and its
`[a]` (4c5398b8bcfd88ebd83656f01c3aca21); rzxarchive `j/jacknipper.rzx` (108,043 frames, 36 min; its own start
snapshot md5 903c092495784d308cf03899b80d7110)    Branch: add-jack-the-nipper
Checks: survey (GATE OK), inspect    Pending user answers: none yet (the stage-1 question comes with the preview)
Start with: `python nexclash.py scan jtn1_start.z80 --rzx jacknipper.rzx --stop 15000 --range 0x7D00-0x7EFF --writers`
(who composes what 0x86F9 copies)    Read: PLAYBOOK 2-3, 3d (an unknown engine: feasibility first)
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
