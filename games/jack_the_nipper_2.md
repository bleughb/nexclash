# Jack the Nipper II - In Coconut Capers (Gremlin Graphics, 1987) - stage 0 done; engine not yet written

## Next session
Stage: 1 (design)            State: intake done 2026-11-22 (survey below); no design yet
Inputs: TOSEC `Jack the Nipper II - In Coconut Capers (1987)(Gremlin Graphics Software)[a].z80` (md5
6f5d708c439f3356a930ea4f176a0c8f: 48K, in game); rzxarchive `j/jacknipper2.rzx` (158,593 frames, 52 min; its own
start snapshot md5 f89e14ab3939e70ecbe94cc1f42b38fe)    Branch: add-jack-the-nipper
Checks: survey (GATE CHECK, below), inspect    Pending user answers: none yet (the stage-1 question comes with the preview)
Start with: `python nexclash.py scan jtn2_start.z80 --rzx jacknipper2.rzx --stop 15000 --range 0xFB00-0xFD7F --writers`
(who composes what 0xB25F copies)    Read: PLAYBOOK 2-3, 3d (an unknown engine: feasibility first)
Open: the three unreached CALL sites; the figure plotter(s); a short recording (3-5 min) from the 48K snapshot

## Snapshot (0b)
- The plain TOSEC `.z80` (812f365c792c8af30edafcf227843a96) is a BASIC loader (`LOAD ""SCREEN$`, "IBM copy by
  Cysio", PC in ROM PAUSE): not a build input. The `[a]` snapshot is in game: 48K, PC 0xBC79, IM 1 with interrupts
  OFF, I = 0x3F, SP 0xFFFA.
- The recording was made on a 128K machine running the 48K game: 0x7FFD = 0x10 (the 48K ROM, bank 0 at the top,
  paging as a 48K machine), banks 1, 3, 4 and 6 empty, and RAM 97 % equal to `[a]` (the rest is game state). So the
  build targets the 48K game and this recording can verify it.

## Survey (2026-11-22, the whole recording, from the TOSEC loader snapshot's survey: the replay uses the RZX's own start)
- Engine: unknown (no detector, no TID / Dizzy 1 signature): a new engine, feasibility first (PLAYBOOK 3d).
- Rendering: 0xB25F writes 62 % of the pixel bytes (164 bytes a call, 55,675 calls) reading 0xFB00-0xFD7F,
  0xBDC0-0xBDFF and 0xF940-0xFA3F: a copier from a composed buffer. 0x935E / 0x939F draw the status panel's
  numbers; 0x967F (482,000 T a call, 498 calls) redraws whole screens; 0x9B1A (21 callers) prints text.
- Pacing: no interrupt accepted in 158,593 frames: no frame sync (as Jack the Nipper).
- Coverage: GATE CHECK: 0x967F's call from 0xA958 and 0x9B1A's calls from 0x9B62 / 0x9B9C never ran (code near them
  did). 0x967F is a screen redraw and 0x9B1A a text printer, not figure plotters: likely a message or screen the
  recording did not bring up; confirm in stage 1.
- Plain conversion: built from the loader snapshot, so not meaningful; rebuild from `[a]`.

## Stage log
- 2026-11-22: stage 0, ~1.5 h wall (with Jack the Nipper), ~20 tool calls, no user rounds.

## Lessons
- [none: PLAYBOOK 0b already covers loader snapshots; the TOSEC `[a]` copy was the in-game one]

## Technique use
- detect.pacing-structure: used: the survey's no-interrupt finding names the no-frame-sync case for the design

## Friction
- reuse: [none: no code written at intake]
- retries: [none: the first survey run started outside the toolkit folder (module not found); rerun from it]
- environment: [none: no workaround]
- hand-rolled: [local: this game's recording machine] comparing the 128K recording's start with the 48K snapshot
  (paging byte, empty banks, RAM equal) was a hand-written check
- scratch: [none: one inline check, recorded above]
