# Heartland (Odin, 1986; 48K)

## Next session
Stage: 0 (intake)           State: first survey done 2026-11-17; the recordings reach two rooms only
Inputs (private, pilot runs/heartland/2026-11-17): TOSEC "Heartland (1986)(Odin Computer Graphics).z80", md5
07bfa8f74d60a53ab64e5b092ffd6cca; heart_1..4.rzx (11,197 frames, scripted, from that snapshot); heartland_survey/.
Branch: add-heartland    Commit: this one    Checks: survey, doccheck    Pending user answers: none
Start with: a recording that goes through more rooms and meets every enemy kind (the owner's play, or the search
with a room test), then `python -m nexclash.survey` again; only then the stage 1 question
Read: PLAYBOOK stage 0-1, the survey's survey.md
Open: the snapshot is a BASIC program stopped at PAUSE 0 (below); room coverage; which routines compose the buffer.

## Facts (snapshot check, survey)
- 48K. The snapshot is the tape's BASIC loader stopped at line 9998 `PAUSE 1: PAUSE 0` with the loading screen up:
  PC 0x0038 in the ROM, IM 0, SP 0x61A0, RAMTOP 24999; line 9999 is `RANDOMIZE USR 25000`. A key starts the game.
  On the Next the ROM under a .nex is not Sinclair's, so the start needs the snapshot's own BASIC start handled
  (as Bomb Jack, Cobra and Sabre Wulf did), or the build must enter at 25000 itself.
- Start: any key, then 1 (keyboard). The whole play window is composed in a back buffer at 0xC000-0xCDFF and copied
  to the screen as one block by 0xA56F (called from 0xA4CA, 2,193 times in the recordings, 97% of all pixel bytes);
  0xA615 copies the attributes the same way. So the figures' own plotters write the buffer, not the screen, and the
  survey's screen-writer table does not show them: next is `scan --range 0xC000-0xCDFF --writers`.
- Other screen writers: 0xA179 (the hourglass, x 8-23 and 232-247), 0xBDE3 (attributes), 0x5E5E (whole screens),
  0x5EF6 (text and pictures on the front screens).
- Survey gate OK (every CALL site to the top plot routines reached), but the gate only knows the routines that write
  the screen; with the figures composed in the buffer it says little here.
- Plain conversion: boots in the simulated start; no proven-safe tail place yet.

## How the recordings were made
- Scripted (no human player): a coverage-guided search with random keys from the snapshot, the four routes that
  together run the most code. They show the first room and one more, the player, a few objects and the wizard.

## Open
- Room coverage: a recording through more of the game.
- A scripted player that tells rooms apart (the search here counted new code only).

## Decisions
- none yet.

## Lessons
- [deferred Open: reconsider when the engine is designed] The coverage gate passes on a game that composes its
  figures in a back buffer, because none of their plotters is a screen writer. Reason: it only follows screen writes.

## Friction
- reuse: [local: private run folder] the Arc of Yesod search and RZX scripts, with the toolkit's 48K machine.
- retries: [none: one pass]
- hand-rolled: [none: nothing new written for this game]
- environment: [none: nothing new about the environment]
- scratch: [local: private run folder] explore.py, mkrzx.py, play48.py kept with the inputs.

## Technique use
- detect.pacing-structure: no help: stage 0 stopped before pacing was looked at.

## Stage log
- 2026-11-17: stage 0 (first pass), about 30 min, about 10 tool calls, 1 user round.
