# The Arc of Yesod (Thor / Odin, 1985; 128K release)

## Next session
Stage: 1 (design)           State: intake done 2026-11-17, design question asked, no answer yet
Inputs (private, pilot runs/arc_of_yesod/2026-11-17): the archive's "Arc of Yesod, The (1985)(Thor Computer)(128K).z80",
md5 f58236395e737aaa0fac1f8476711ad8 (control menu); under.z80, md5 f3c07b0b (a cavern, from the owner's play, below);
arc_u1..4.rzx (4,231 frames, start at under.z80); survey in arc_of_yesod_survey/.
Branch: add-arc-of-yesod    Commit: this one    Checks: survey, doccheck    Pending user answers: the design question
Start with: the owner's answer, then PLAYBOOK 3d feasibility against nexclash/nodes_of_yesod.py (same family, below)
Read: PLAYBOOK stage 1-2, games/nodes_of_yesod.md, nexclash/nodes_of_yesod.py SITES_ORIG / event / verify
Open: how the surface hatch takes the player down (not reproduced by script, below); a recording from the archive
snapshot that goes down by itself; the three unreached CALL sites.

## Facts (snapshot check, survey)
- 128K, 7FFD 0x10 at the menu, in play it switches 0x10 / 0x16 (bank 6 at C000 holds most of the code). IM 2, I = 0xE2,
  vector table of 257 x 0xFF, handler entered at 0xFFFF. SP 0x5BB1: the stack is in the printer buffer.
- Start from the archive snapshot: 1 (keyboard), release, hold 1 about 5 s. Keys are whole rows: bottom row alternates
  right / left (M, N), A row = down, Q row = jump, number row = fire, ENTER = a window with a key wait.
- Same family as Nodes of Yesod: figures are plotted into a back buffer at 0xE400 (32 bytes a row), the changed
  rectangle is copied to the screen by the LDIR at 0xD4B3 (routine 0xD2EF, IX = the object), then 0xD552 paints the
  figure's ink (IX+5, AND 0xC7) into the cells it covers: the store at 0xD580 is the clash. That paint reads a cell
  map at attribute address + 0xA100 (0xF900..): bit 7 set or a value other than 0 / 0x47 leaves the cell alone.
- Object record (IX): +0 flags (bit 0 active, 1 changed, 2 drawn, 7 mirrored), +1 x, +2 y, +3 / +4 size, +5 colour,
  +7 / +8 graphic, +14..+21 the last rectangle, +22.. its copy. Player at 0xFDE0, others at 0xFD60, 0xFD80, 0xFDC0.
- Graphics shared with Nodes of Yesod (measured 2026-11-17, match.py in the run folder): of the 27 graphics the Nodes
  engine lists from its reference snapshot, 21 are in Arc byte for byte, header (width, height, colour) included, as
  one block at 0x7E73-0x86E7: Nodes 0xB757-0xBF65, the astronaut's walking (22 x 32) and somersault (30 x 29)
  frames. The other six (0xBFDC, 0xC0AE, 0xC3EA, 0xC40F, 0xC59B, 0xC900) are not in Arc. So Nodes' patterns and its
  painted Enhanced colours for the astronaut can be carried over by bitmap; Arc's enemies need their own.
- Main loop 0xBAE8; 0xBC19 copies the scrolling surface strip (x 0-223, y 88-183) as a block.
- Survey (4 recordings, 4,231 frames, no desync): screen writers 0xBC19, 0xD2EF (3 of 6 CALL sites reached; not
  reached 0xAC0D, 0xBBF8), 0xDC7F (HUD), 0xAAF1 (room draw), 0xC9F4 (1 of 2; not reached 0xBC6D), 0xBE79.
  The recordings cover caverns, three enemy kinds, a lost life, game over and a new game on the surface.

## How the recordings were made (and what that leaves open)
- The archive snapshot is at the control menu and the game starts on the surface. No scripted input took the player
  down: every key at every position, the hatch stood on and jumped on, 400,000 frames of random keys.
- The owner played it in OverSpec and went down ("walked to the ladder and press a or just fell down"). OverSpec's
  automatic resume save from that session, taken in a cavern at timer 0:00:19, was converted to under.z80 (ovs.py in
  the run folder). The recordings start there and were picked from a coverage-guided search (explore.py, mkrzx.py).
- So no recording yet runs from the archive snapshot into the caverns in one piece.

## Open
- A scripted 128K recorder in the toolkit (machine.py has no paging); reconsider when a second 128K game needs one.
- The descent from the surface by script, and a recording from the archive snapshot that goes down in one piece.
- The three unreached CALL sites (0xAC0D, 0xBBF8 to the figure copy; 0xBC6D).

## Decisions
- none yet (the design question is with the owner).

## Lessons
- [deferred Open: reconsider when a second 128K game needs a scripted recording] `nexclash.py record` drives a 48K
  machine only; the 128K recordings here were made with the pilot's m128.py. Reason: paging is not in machine.py.
- [local: this game's intake] A new-code count misses a move into a place that runs the same code: the descent search
  reported nothing because the caverns reuse the surface's routines. Watch a game variable or the screen as well.

## Friction
- reuse: [none: nothing reused yet]
- retries: [local: this game's intake] the descent search was rerun four ways before the owner's save settled it.
- hand-rolled: [local: private run folder, 128K only] m128.py, a 128K copy of machine.py's frame loop.
- environment: [local: this machine] no Fuse here; OverSpec does not write RZX, but its resume save converts to a .z80.
- scratch: [local: private run folder] explore.py, mkrzx.py, ovs.py, m128.py kept with the inputs, not in the repo.

## Technique use
- detect.pacing-structure: no help: stage 0 stopped before pacing was looked at.

## Stage log
- 2026-11-17: stage 0, about 3 h, about 90 tool calls, 3 user rounds (most of it on the descent).
