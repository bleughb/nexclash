# Heartland (Odin, 1986; 48K)

## Next session
Stage: 1 (design)           State: intake done 2026-11-17 (second survey, six or seven rooms); feasibility not started
Inputs (private, pilot runs/heartland/2026-11-17): TOSEC "Heartland (1986)(Odin Computer Graphics).z80", md5
07bfa8f74d60a53ab64e5b092ffd6cca; heartR_1..6.rzx (13,461 frames, scripted, from that snapshot); heartland_survey2/ (heart_1..4 and heartland_survey/: the first pass).
Branch: add-heartland    Commit: this one    Checks: survey, doccheck    Pending user answers: none
Start with: PLAYBOOK 3d feasibility: which of the buffer's writers below plot figures, what the attribute buffer holds
(0xA615 copies it), then the stage 1 question with a preview
Read: PLAYBOOK stage 0-1, the survey's survey.md
Open: the snapshot is a BASIC program stopped at PAUSE 0 (below); a human recording; the design (a new engine, not a port).

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
- Second survey (heartR_1..6, 13,467 frames, gate OK). Writers of the buffer 0xC000-0xCDFF (`scan --writers` on two
  recordings): 0xA949 (255,864 writes) with 0xA8C7 / 0xA8E5 / 0xA903 / 0xA921 and readers 0xA8AB-0xA905 (read, then
  write: a masked plot); 0xA7FD / 0xA80A / 0xA817 / 0xA824 (readers 0xA7F2-0xA819) and 0xA860 / 0xA86D / 0xA87A
  (0xA855-0xA86F): two more plotters of the same kind; 0xA0A9 (187,744, reads 0xA0A5 first); 0x5E75 (35,830, a fill
  or copy); 0xB240, 0xE43F, 0xFCF8, 0xFD42 (small). Which are figures and which scenery is the feasibility's first job.

## How the recordings were made
- Scripted (no human player): coverage-guided searches with random keys from the snapshot. The second pass also
  rewards a new room (a play-window colour picture unlike any seen, explore2.py): six or seven rooms in each of three
  runs, the six routes that together run the most code. A human recording through the game is still owed.

## Open
- A human recording through more of the game (the scripted ones stay near the start).
- The design: figures are composed into the buffer with masks, the whole window and its attributes are copied each
  update; which technique fits (cover with sprites, or plot to a scratch page) is for the feasibility pass.

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
- 2026-11-17: stage 0 (second pass: room-guided recordings, survey, buffer writers), about 30 min, 6 tool calls.
