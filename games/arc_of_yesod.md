# The Arc of Yesod (Thor / Odin, 1985; 128K release)

## Next session
Stage: 2 (build)            State: engine ported from Nodes; five recordings verify IDENTICAL (2026-11-17); unit tests,
negative controls, the record, Enhanced and the .nxc are not done
Inputs (private, pilot runs/arc_of_yesod/2026-11-17): the archive's "Arc of Yesod, The (1985)(Thor Computer)(128K).z80",
md5 f58236395e737aaa0fac1f8476711ad8 (control menu); under.z80, md5 f3c07b0b (a cavern, from the owner's play, below);
arc_s1.rzx (2,605 frames, from the archive snapshot, the surface) and arc_u1..4.rzx (4,231 frames, from under.z80).
Branch: add-arc-of-yesod    Commit: this one    Checks: auto with the five recordings (IDENTICAL, rom_paths pass), doccheck
Pending user answers: none
Start with: `python nexclash.py auto arc_of_yesod.z80 --no-nxc --rzx arc_s1.rzx --rzx arc_u1.rzx ...` (must still say
IDENTICAL), then port unit_tests / negative_patches / negative_real from nexclash/nodes_of_yesod.py (lines 1158-1530)
Read: PLAYBOOK stage 2-3, docs/ENGINE_CONTRACT.md, "Build design" and "What the port changed" below
Open: unit tests and negative controls; hooks never run in a recording (e_over, e_tele: no game over, no window refresh
yet); pace (the Nodes windows are in, not measured for Arc); the evidence record; Enhanced (the astronaut's colours from
Nodes by bitmap, near matches, the owner's sheet); loading screen; the .nxc; the descent by script; hardware.

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

## What the port changed from Nodes (2026-11-17)
- Sites as in "Build design", with these corrections found by the verifier: the copy hook leaves to 0xD552 (where the
  loop's own JP 0xD552 goes; R was one short with 0xD4D8); the room-drawn points are 0xAB6E (colours) and 0xAB9F
  (picture); the surface's star cells are the 16 at 45391, rooms 64-79; the room number is at 23479.
- Not in Nodes: a second random read at 0xC1CC (LD L,A / LD H,A / LD A,(HL), address R * 257): hook e_random2, flags kept.
- Not in Nodes: the beam (0xCEAF-0xCF18) writes its pixels straight to the screen and colours a cell whose ink is
  black, reading the screen's colour at 0xCF07. With the paint no longer written the build would take the other branch
  and R would drift. So the hooks keep the ink the original would have painted in a shadow page (Next page 23, at slot 4
  for one access; cleared when a room is drawn), and e_beam, e_random and e_random2 read through it. The verifier's
  second replay does the same. The beam's own pixels are left out of the screen comparison while it is there (the
  original's next copy over them restores the buffer's bytes, the build's does not): a small visible difference.
- Not in Nodes: the appear / vanish effect rewrites two graphics in place (0x8C92, 0x8CF5; code 0xC185, 0xC1A0), so their
  tiles are made from the live bytes at each update (dynload: ink only, no fill), and checked against the live bytes.
- Memory: object state in bank 0 at 0xFBA0-0xFBE2, the rest at 0x5B00-0x5B22; the sprite build's tail at 0x5B24-0x5B58,
  the plain build's at 0x5B00-0x5B4E, both in bytes the game never touches. Both builds' set-up puts the printer
  buffer back (NEXLOAD uses it; the game's stack is there). Deepest stack at a hook 0x5B9B, the handler 46 bytes:
  the hooks (36) and the handler inside one reach 0x5B41, above the state.
- Left out: backdrops, the Enhanced HUD, the clip window change by room (Arc's play area is always 168 lines), Nodes'
  wrong-clip and bare-RET plotter cases (no such plotter seen in Arc: to recheck with wider recordings).
- Results: arc_s1 2,605 frames 2,059 copies; arc_u1 1,447 / 1,489; arc_u2 583 / 541; arc_u3 1,258 / 1,314; arc_u4
  943 / 1,157: all IDENTICAL (registers with R, memory, sprites over the bare picture, the patched replay's state).
  1,038 copies in the cavern recordings come before a room is drawn and have no bare picture to check against.
  Builds: plain 9858d3f2, sprites 7aa17d81 (not final). Both start and play in OverSpec (surface only).

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
