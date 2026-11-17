# The Arc of Yesod (Thor / Odin, 1985; 128K release)

## Next session
Stage: 2 (build)            State: design approved 2026-11-17 (Decisions below); feasibility done: a port of the Nodes engine
Inputs (private, pilot runs/arc_of_yesod/2026-11-17): the archive's "Arc of Yesod, The (1985)(Thor Computer)(128K).z80",
md5 f58236395e737aaa0fac1f8476711ad8 (control menu); under.z80, md5 f3c07b0b (a cavern, from the owner's play, below);
arc_u1..4.rzx (4,231 frames, start at under.z80); survey in arc_of_yesod_survey/; the scripts (m128.py, sites.py, ...).
Branch: add-arc-of-yesod    Commit: this one    Checks: survey, doccheck    Pending user answers: none
Start with: the seven sites the byte search did not settle (Feasibility table), then copy nexclash/nodes_of_yesod.py and
asm/nodes_of_yesod_hooks.asm to arc_of_yesod with Arc's addresses, in stages (sites, hooks, verify, unit tests)
Read: PLAYBOOK stage 2, docs/ENGINE_CONTRACT.md, nexclash/nodes_of_yesod.py (constants, NodesPatch, event, verify),
asm/nodes_of_yesod_hooks.asm header
Open: Arc's object table and graphic tables (Nodes: 0xFC00 x 16, tables 0xB700 / 0xC700); free RAM for the hook state;
the scrolling surface strip (0xBC19); the descent by script and a recording from the archive snapshot; the three
unreached CALL sites; carrying the astronaut's painted colours over by bitmap (Decisions).

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
  Against the painted map itself (docs/profiles/nodes_of_yesod_colours.json, 6,726 painted bytes; match2.py): 2,413
  have their 32 surrounding bytes in Arc unchanged: the astronaut block (Nodes 0xB762-0xBFF0, 1,675 of them) and
  smaller runs at Nodes 0xC300-0xC35A, 0xCB10-0xCBF0, 0xD31A-0xD4F4, 0xD5F8-0xD63F and a few short ones (not yet
  identified as figures). The other 4,313 painted bytes belong to Nodes graphics Arc does not have.
- Main loop 0xBAE8; 0xBC19 copies the scrolling surface strip (x 0-223, y 88-183) as a block.
- Survey (4 recordings, 4,231 frames, no desync): screen writers 0xBC19, 0xD2EF (3 of 6 CALL sites reached; not
  reached 0xAC0D, 0xBBF8), 0xDC7F (HUD), 0xAAF1 (room draw), 0xC9F4 (1 of 2; not reached 0xBC6D), 0xBE79.
  The recordings cover caverns, three enemy kinds, a lost life, game over and a new game on the surface.

## Feasibility against the Nodes engine (2026-11-17, sites.py in the run folder)
The code around each Nodes patch site, searched for in Arc (same bytes):
| Nodes site | hook | Arc |
|---|---|---|
| 36680 (0x8F48) | e_blit (the copy, IX = object) | 0xD4AF, 24 bytes identical |
| 36851 (0x8FF3) | e_attr_enter | 0xD55A |
| 36889 (0x9019) | e_attr (the store) | 0xD580 |
| 31996 (0x7CFC) | e_random | 0xC355 |
| 33946 (0x849A) | e_new2 | 0xAA3F |
| 39125 (0x98D5) | e_irq_out | 0xDDEE |
| 33766, 38127, 41596 | e_new1, e_over, e_tele | short patterns, several places (0xA985, 0xC112): to settle by reading |
| 34268, 36898, 39083, 40048 | e_room, e_attr_row, e_irq_in, e_player | no byte match: the code changed, find by role |
About 15% of Nodes' code (0x7000-0xB200, 16-byte windows) is in Arc unchanged. So: the same design, a port of
nexclash/nodes_of_yesod.py and its .asm with Arc's addresses, seven sites to locate by reading; not a new engine design.

## Build design (stage 2; facts measured 2026-11-17 on arc_s1 + arc_u1..4, 6,836 frames)
- Sites (original bytes -> hook, exit), all in bank 0, which is at 0xC000 whenever game code runs (bank 6 is only
  the AY music, called from the handler through the stub at 0x5C2E): 0xD4AF 06 00 08 e_blit -> 0xD4D8; 0xD55A DD 7E 05
  e_attr_enter -> 0xD55D; 0xD580 77 e_attr -> 0xD581; 0xD589 15 C2 62 D5 e_attr_row -> 0xD58D; 0xBAF8 DD 21 E0 FD
  e_player -> 0xBAFC (once a main-loop pass, 2,694 times); 0xDDB3 F5 C5 D5 e_irq_in -> 0xDDB6; 0xDDEE E1 D1 C1
  e_irq_out -> 0xDDF1; 0xC355 7E E6 0F e_random -> 0xC358; 0xAAF1 21 BD 5B e_room -> 0xAAF4 (room draw, 11 calls);
  0xA985 and 0xAA3F 21 00 40 e_new1 / e_new2; 0xDA50 21 00 40 e_over; 0xC112 21 00 58 e_tele. Another attribute
  wipe at 0xBCF8 (LD HL,22528 / LD BC,672 / LD (HL),E with LD A,R) writes the screen itself: to look at.
- Objects: 32-byte records from 0xFC00 (seen: 0xFC00, 0xFD00, 0xFD20, 0xFD40, 0xFDC0 the sphere, 0xFDE0 the
  astronaut), the Nodes layout; header before each graphic = width, height, colour, the same as record +3, +4, +5.
- Graphics: two pointer tables, 0x7E1C (41 words, the astronaut, graphics 0x7E70-0x8D54) and 0x8D55 (98 words,
  the rest, up to about 0xA400). 62 graphics seen in the recordings, colours 66-71 (bright red .. white).
- Memory for the hooks: the game leaves no zero run of 120 bytes below 0xC000. Free: 0x5B00-0x5B5A (91 bytes, never
  touched; the stack's low-water mark is 0x5B61) and bank 0 0xFBA0-0xFBFF (96 bytes: the cell map's rows 21-23,
  never touched). Written before read from the archive snapshot on: 0x5BBC-0x5C18, with 0x5C19-0x5C2D untouched.
  Banks 1 and 3 are all zero and never paged; bank 7 and bank 4 do not change after the menu.
- Recording from the archive snapshot: arc_s1.rzx (2,605 frames: start, the surface both ways, jumps, fire, the
  ENTER window), md5 in the run folder.

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
- 2026-11-17 (owner): base look as Nodes of Yesod: the astronaut, the sphere and the enemies as sprites in their own
  colours, scenery as the game draws it. Enhanced is built in the same pass: the astronaut's painted colours are
  carried over from Nodes by bitmap ("yes do that, i'll paint the enemies later that dont match"); Arc's own enemies
  stay in the game's colours in Enhanced until the owner paints them. Backdrops: not asked for, not in this pass.
- 2026-11-17 (owner): "anything we can reuse and save me repaint the same sprites the better". So the carry-over is
  not only exact bitmaps: once Arc's graphics are catalogued, compare each with every painted Nodes graphic (same
  size, shifted, mirrored, a few pixels changed), carry the paint for near matches too, and give the owner one sheet
  showing what was carried exactly, what was carried with differing pixels (marked), and what is left to paint.

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
