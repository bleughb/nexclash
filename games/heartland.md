# Heartland (Odin, 1986; 48K)

## Next session
Stage: 1 (design)           State: feasibility done 2026-11-17 (feasible, table below); the stage 1 question is with the owner
Inputs (private, pilot runs/heartland/2026-11-17): TOSEC "Heartland (1986)(Odin Computer Graphics).z80", md5
07bfa8f74d60a53ab64e5b092ffd6cca; heartR_1..6.rzx (13,461 frames, scripted, from that snapshot); heartland_survey2/;
prev.png (original beside figures-lifted-out, three frames of the first room).
Branch: add-heartland    Commit: this one    Checks: doccheck    Pending user answers: the stage 1 question (below)
Start with: the owner's answer, then stage 2: hooks at the two plot loops (0xA527, 0xB702) and their restores
Read: PLAYBOOK stage 1-2, "Feasibility" below
Open: the snapshot is a BASIC program stopped at PAUSE 0 (below); a human recording; hook cost with R kept (0xFCEF reads R).

## Feasibility (PLAYBOOK 3d, 2026-11-17; disassembly of the in-game state)
| Item | Finding |
|---|---|
| Update | 0xA4CA, once per game step: build, plot big (0xA527), plot small (0xB702), sparks (0xFC4A), foreground (0x9FAB), copy pixels (0xA56F), copy attributes (0xA615), restore small (0xB75A), restore big (0xA4F6) |
| Big figures | 4 records of 16 bytes from 0xAC1A, 4 bytes x 34 rows: bit 0 of +0 = shown, bit 7 = mirrored, +3 graphic, +5 mask, +7 save record, +9 position. Plot 0xA7D4, mirrored 0xA88D (through the reverse table at 0xFE00); each saves what is behind, then (buffer AND mask) OR graphic |
| Small figures | 4 records of 16 bytes from 0xB976, 3 bytes x 16 rows, graphic number at +13 (table 0xE16E), shifted at run time into 0xD680 with a built mask at 0xD708; plot 0xA837 |
| Restore | 0xA93B / 0xA934 put the saved bytes back, in reverse order |
| Colour | 0xA7A0 ORs 0x47 (bright white ink) into the attribute buffer (0xD460) under a big figure: the clash |
| Foreground | 0x9FAB: a list at 0xA10B (count, then buffer address and data per piece), masked into the buffer after the figures every step: figures pass behind these pieces |
| Sparks | 0xFC4A-0xFD44: XORs R-derived bytes into buffer rows at 0xCB00 and keeps a copy; reads R twice (0xFCEF, 0xFCF5), so hooks must keep R as the Yesod engines do |
| Verdict | feasible: 8 figures at most (4 x 32x34 = 6 sprites each, 4 x 24x16 = 2 each, 32 sprites), plot and restore calls replaced, the attribute OR dropped, the copy left alone |
| Unknown | whether anything reads the buffer under a figure (collision); the foreground on a layer above the sprites (Layer 2, priority L S U) or clipped out of the patterns; pace |

Preview check: with the six entry points returned at once (0xA523, 0xA527, 0xA4F2, 0xA4F6, 0xB702, 0xB75A) the room draws
complete without figures, and the figures are exactly the difference to the original screen.

## Stage 1 question (asked 2026-11-17, not answered)
Defaults: every figure a sprite in bright white (its colour today), rooms and panel on the ULA in their own colours,
figures behind the foreground pieces as in the original, sparks on the ULA. Enhanced colours painted later.

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
- 2026-11-17: stage 1 (feasibility: disassembly of the update, the three plotters, restore, foreground list, sparks; preview), about 30 min, 9 tool calls.
- 2026-11-17: stage 0 (second pass: room-guided recordings, survey, buffer writers), about 30 min, 6 tool calls.
