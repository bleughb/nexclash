# The Arc of Yesod (Thor / Odin, 1985; 128K release)
Techniques: detect.gameplay-screen-readers

## Next session
Stage: 3 (prove + deliver)  State: `selftest.py --game arc_of_yesod --verify --stamp` PASSED 2026-11-17 (stamped); loading
screen and .nxc 1.0 built (below), the owner saw the Enhanced build in OverSpec (surface) and called it a first-pass
1.0; no hardware run yet
Inputs (private, pilot runs/arc_of_yesod/reference_files/arc_of_yesod, the selftest's reference folder): the archive's
"Arc of Yesod, The (1985)(Thor Computer)(128K).z80" as arc_of_yesod.z80, md5 f58236395e737aaa0fac1f8476711ad8; arc_s1,
arc_a1..a6, arc_over (from that snapshot), arc_tele and arc_end (from poked states, below). Scripts: runs/.../2026-11-17.
Branch: add-arc-of-yesod    Commit: this one    Checks: selftest --game arc_of_yesod --verify (see State), doccheck
Pending user answers: none
Start with: the colour sheets and the hardware checklist to the owner, then the pace measurement
Read: PLAYBOOK stage 3 (6a, 6b, 7), docs/COLOURS.md, "What the port changed" and the open items below
Open: the list in the open-items section.

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
- e_over is the OUT OF TIME / percentage screen (0xDA50), not a lost last life; a teleporter pad's colour bars (0xDE75,
  0xDE77) are the game's own screen writes and are allowed for in the bare-colour check.
- Results (2026-11-17): ten recordings, 22,957 frames, all IDENTICAL (registers with R, memory, sprites over the bare
  picture, the patched replay's state). Unit tests: 1,254 positions over 114 graphics, 7 interrupted uploads, 16
  objects, shadow page cases: PASS. Broken builds: 28, each on a recording that reaches its hook. Builds: plain
  9858d3f2, sprites 7aa17d81, Enhanced 7da91d6d. The sprite and plain builds start and play in OverSpec (surface).

## How the recordings were made
- Scripted, no human player (the checklist's human recording is still owed). All but two start at the archive snapshot.
- The descent (found 2026-11-17 after the owner showed it could be done): a surface room with a hatch has a gap in
  its floor row (cell map row 17, columns 13-15); with the astronaut wholly inside the gap (x = 105 in room 74) the
  up row (Q) takes him down to the room below (74 -> 90). Script: `wait 20, 1 5, wait 60, 1 260, wait 60, M 250,
  wait 10, Q 26, wait 30` (down.txt). An earlier search missed it by watching the height and new code, not the room.
- arc_s1 (2,605 frames): the surface both ways, jumps, fire, the ENTER window. arc_a1..a6 (15,800 frames): the descent,
  then routes picked from four coverage- and room-guided searches (explore.py, mkrzx2.py): 33 rooms, a1 alone 28.
  arc_over (2,602): the three lives lost. A search run that executed far more code than the game has (a crash after
  some key mix, not looked into) was left out.
- arc_tele (720) and arc_end (1,230) start at poked states, as Nodes' room recordings do: the cavern state after the
  descent with the room and the astronaut's place set onto a teleporter pad (room 88 -> 39, table 0x7C8C: room, x, y,
  destination - 1; twelve pads), and with the count at 23487 set to 16 (the main loop's test at 0xBAEC: OUT OF TIME,
  the percentage screen, the menu and a new game). So e_tele and e_over run in a recording; neither state was played to.
- The first cavern recordings (arc_u1..4, from the owner's OverSpec resume save converted by ovs.py) found the beam and
  the appear effect; they are no longer in the record (their snapshot was not the archive's).

## Open
- A human recording (RECORDING_CHECKLIST); later rooms, the twelve teleporters in play, the ending by play.
- Pace: Nodes' windows are in and pass the speed-true line-clock check; not measured against the original in JNext.
  The new hooks (beam, second random read, live tiles: about 1.8 ms at 28 MHz an update while the effect runs) are
  not in the pace account.
- A teleporter pad writes its colour bars over cells a figure may have painted; the shadow page then still holds the
  figure's ink for those cells. A beam or random read there would differ from the original: the verifier's first
  replay would report it (hook against original); it has not happened in a recording.
- The beam's pixels stay on the ULA under a sprite until the game wipes them (the original's next copy removes them).
- Live tiles have ink only: no black fill, no painted colours while the astronaut appears or vanishes.
- Colour sheets to the owner, hardware.
- Loading screen: arc_of_yesod_loading.scr beside the snapshot (the 128K tape's 6,914-byte block, flag and checksum
  dropped, MD5 6bd06bf8; game data, local only) gives arc_of_yesod_sprites_loading.nex 16deee35 and
  arc_of_yesod_enhanced_loading.nex 1736ef8c; `auto` packs them as arc_of_yesod.nxc (38,316 bytes, version 1.0,
  colour set Enhanced). Not published.
- Cheats: arc_of_yesod.pok beside the snapshot (local only), seven for the 128K release: infinite lives 48264,0
  (Gerard Sweeney); from The Tipshop (Martin 'Pugsy' Pugh): infinite time 56364,58; infinite energy 50556,0 50328,0
  50329,0; drop from any height 48966,0; no reversed controls 50529,24; no bouncing 48433,195; no crystal stealing
  50821,24. Each checked against the snapshot's instruction; addresses from 0xC000 named bank 0 (import-pok refuses
  bank 8 there on a 128K game). None is at a patch site. Not played with the cheats on.
- The Tipshop lists a complete solution recording in the RZX Archive (Xmikex and Jamie Angus): the human recording
  this game lacks, if it is of the 128K release. Not fetched.
- A scripted 128K recorder in the toolkit (machine.py has no paging); the search that crashed the game.
- Nodes' bare-RET plotter case and wrong-clip case: no such plotter seen in Arc's ten recordings.

## Decisions
- 2026-11-17 (owner): base look as Nodes of Yesod: the astronaut, the sphere and the enemies as sprites in their own
  colours, scenery as the game draws it. Enhanced is built in the same pass: the astronaut's painted colours are
  carried over from Nodes by bitmap ("yes do that, i'll paint the enemies later that dont match"); Arc's own enemies
  stay in the game's colours in Enhanced until the owner paints them. Backdrops: not asked for, not in this pass.
  Done 2026-11-17: 36 of Arc's 114 graphics are the same bitmap as a painted Nodes graphic (all the shared astronaut
  frames); their 2,807 painted bytes are in docs/profiles/arc_of_yesod_colours.json, with Nodes' Enhanced palette.
  No near match was found (the one candidate is a graphic the game rewrites). 76 graphics are left for the owner.
- 2026-11-17 (owner): "anything we can reuse and save me repaint the same sprites the better". So the carry-over is
  not only exact bitmaps: once Arc's graphics are catalogued, compare each with every painted Nodes graphic (same
  size, shifted, mirrored, a few pixels changed), carry the paint for near matches too, and give the owner one sheet
  showing what was carried exactly, what was carried with differing pixels (marked), and what is left to paint.

## Hardware checklist (for the owner; nothing here has run on a board)
1. The menu: 1 for keyboard, then hold 1 until the game starts (the original is slow to see the key).
2. Surface: the astronaut walks, jumps and fires with no colour change on the skyline or the ground; stars twinkle.
3. The hatch: stop wholly inside the opening and press the up row; the cavern below is drawn, the astronaut appears.
4. Caverns: each enemy kind in its own colour over the scenery, no coloured squares around figures; the beam; a lost
   life; the appear and vanish effect (plain ink, no fill: expected).
5. A teleporter pad (its colour bars), the out-of-time screen, a new game.
6. Enhanced: the astronaut painted (orange pack, pink visor) in every pose; enemies in the game's colours.
7. Speed and music against the original 128K game.

## Lessons
- [deferred Open: reconsider when a second 128K game needs a scripted recording] `nexclash.py record` drives a 48K
  machine only; the 128K recordings here were made with the pilot's m128.py. Reason: paging is not in machine.py.
- [local: this game's intake] A new-code count misses a move into a place that runs the same code: the descent search
  reported nothing because the caverns reuse the surface's routines. Watch a game variable (here the room number).
- [local: this game's port] A port of an engine by matching bytes finds the sites but not their spans: the copy hook's
  exit was one instruction short (the loop's own JP), seen only as R one out. Compare each site's whole original span.
- [local: this game's port] Reads of the screen that the first game never made: once a paint stops writing, every reader
  of what it wrote has to be found (scan the screen's readers), not only the ones the model engine hooks.
- [local: this game's port] A graphic the game rewrites in place cannot have a pre-built pattern: scan the graphics for
  writers before trusting a catalogue of patterns.
- [deferred Open: reconsider when the selftest's check is next touched] nextboot.rom_paths treats a recording that starts
  at another state as starting at the build's snapshot: a tail in write-first memory is then reported as read. Reason:
  it has no notion of a recording's own start state; here the tails went to never-touched bytes.

## Friction
- reuse: [none: nothing reused yet]
- retries: [local: this game's intake] the descent search was rerun four ways before the owner's save settled it.
- hand-rolled: [local: private run folder, 128K only] m128.py, a 128K copy of machine.py's frame loop.
- environment: [local: this machine] no Fuse here; OverSpec does not write RZX, but its resume save converts to a .z80.
- scratch: [local: private run folder] explore.py, mkrzx.py, ovs.py, m128.py kept with the inputs, not in the repo.

## Technique use
- detect.gameplay-screen-readers: helped: the random reads were ported from Nodes with it; it also named the question that
  found the beam's read of a cell's colour (who reads the screen once the paint stops) before any hardware saw it.
- patch.xor-overlay-keep-ula: no help: Arc copies a back buffer; the Nodes engine was the model, not a card.
- detect.pacing-structure: no help: the pace windows came with the Nodes port; Arc's own pacing was not measured.

## Stage log
- 2026-11-17: stage 0, about 3 h, about 90 tool calls, 3 user rounds (most of it on the descent).
- 2026-11-17: stages 1-3 (design, port, verify, record), about 5 h, about 150 tool calls, 3 user rounds.
