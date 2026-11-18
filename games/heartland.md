# Heartland (Odin, 1986; 48K)

## Next session
Stage: 3 (prove + deliver)   State: built and verified 2026-11-18; starts and plays in OverSpec; not on hardware; no Enhanced set, no colour sheets yet
Inputs (private, pilot runs/heartland/reference_files/heartland): heartland.z80 = TOSEC "Heartland (1986)(Odin Computer
Graphics).z80", md5 07bfa8f74d60a53ab64e5b092ffd6cca; heart_h1.rzx (the owner's play in Fuse, 12,178 frames, autosaves
stripped); heartR_1..6.rzx (13,461 frames, scripted).
Branch: add-heartland    Commit: this one    Checks: selftest --game heartland --verify --stamp, doccheck    Pending user answers: none
Start with: the hardware checklist below with the owner; then the Enhanced set (needs patterns made ahead: see Open)
Read: "Build" and "Open" below
Open: hardware; pace on hardware; Enhanced colours and sheets; the border's colour on a room with coloured paper.

## Result (2026-11-18)
Techniques: `detect.gameplay-screen-readers`, `patch.xor-overlay-keep-ula`, `patch.preserve-r`, `patch.restore-speed`,
`patch.pace-limiter`, `patch.whole-altrom-image`

| | |
|---|---|
| Builds | heartland.nex 33283547 (plain), heartland_sprites.nex 7a14d2f1 |
| Verify | IDENTICAL on 7 recordings, 25,639 frames: 5,049 game steps, 5,026 screen copies, 11,723 figures noted, 9,158 paints, 267 random bytes; every register with R and all game memory after every hook; 3,158,110 sprite pixels against the model and the game's own picture |
| Unit | PASS: 119 cases in 24 groups (the two copies with nothing to do, 144 lines, a 16-piece foreground list, the attribute copy's three ways, the random byte at all 256 addresses and from a cell with its paint lifted, full tables, the game's interrupt at 13 points inside each hook) |
| Negative | 11 broken builds, 11 detected |
| Pace | the hooks take +0.32% of the recordings' time more than the two copies they stand for (a wait on the video line holds the game's copy to its own time) |
| Known differences | the bolt (0xFC4A) is XORed through a figure in the original; the build's figure stays whole over it (275 pixels in the recordings). The mask's cleared border is black; in the original it is the cell's paper. Small figures are bright white; in the original they take the cell's ink |

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
| Verdict | feasible, built another way (below): the buffer cannot lose its figures, the game reads random bytes from all of memory |
| Answered | the random routine (0xBBF3) reads a byte at address A * 257 with A = R XOR the last byte: buffer, screen, saved bytes, ROM. Foreground: clipped out of the patterns. Pace: held by a wait |

Stage 2 facts (2026-11-17, same state):
- Position: +9 = x pixel, +10 = line; 0xA703 gives the buffer address 0xC000 + (line * 256 + x) / 8, so a figure sits on
  a byte boundary and its frame carries the fine offset (0xAA96: the frame comes from the record's sequence at +1 and
  x / 2). The buffer (32 bytes a line, 112 or 144 lines) goes to the screen from line 48 (0x40C0); attributes
  0xD200 -> 0xD440 (0xA5E8, the clean copy each step) -> 0x58C0 (0xA615).
- Large frames: table 0xE10C, 49 words (0-7 empty): 8-31 are 4 bytes x 33 lines (the player and the walkers, 0xE1BA up),
  32-35 other sizes, 36-48 3 bytes x 33. The plotters' width and row skip are self-modified operands (0xA7D4-0xA7DF).
- Masks are not data: 0xA714 builds one from the frame (the frame ORed with itself moved one pixel each way, inverted)
  into the record's own mask buffer (+5), every time the frame changes (0xAAC4, also 0xA097, 0xADB0, 0xB735).
- Small frames: table 0xE16E, 2 bytes x 16 lines, 32 bytes apart (0xF590 up; 20-23 and 38-39 empty); 0xA989 shifts one
  by x AND 7 into 0xD680 and 0xA714 builds its mask at 0xD708.
- The fourth large record can show the shift buffer itself (graphic 0xD680, mask 0xD708): a live graphic, not a table
  frame, so the hook needs a live upload path as Arc of Yesod's dynload.
- Callers: plot 0xA558 / 0xA55D (large), 0xB74E (small); restore 0xA512 / 0xA517, 0xB76F; attribute OR 0xA790 from
  0xA561 only.

Preview check: with the six entry points returned at once (0xA523, 0xA527, 0xA4F2, 0xA4F6, 0xB702, 0xB75A) the room draws
complete without figures, and the figures are exactly the difference to the original screen.

## Build (stage 2, 2026-11-18; asm/heartland_hooks.asm, nexclash/heartland.py)
- First try: the plotters' buffer writes turned into reads (LD (HL),A -> LD A,(HL): same T, same M1s), figures only as
  sprites. The picture matched at every copy, but the game's state left the original's at step 906 of the owner's
  recording: 0xBBF3 takes its random byte from address A * 257 (A = R XOR the last byte, kept in its own operand at
  0xBBF7), and that address had held a figure's pixels in the buffer. Dropped.
- As built: every byte of the game's memory and of the screen bitmap stays the original's. The figures stay in the buffer
  and on the ULA; each sprite lies on its figure's own pixels (card patch.xor-overlay-keep-ula). The only thing kept off
  the screen is the paint of bright white under a large figure (0xA790 ORs 0x47 into the attribute copy): the clash.
- Sites (addresses in play; the snapshot holds them 0x6AC higher, the game moves itself down at 0xE436):
  0xA7D4, 0xA88D, 0xA837 (the plotters' first instruction): note buffer address, graphic, mask; a graphic in the shift
  buffer (0xD680: every small figure, and the fourth large one) is copied with its mask, since the next small figure
  overwrites it before the screen copy.
  0xA790 (the paint): note each cell's address and colour before it.
  0xA56F (the screen copy): 4-bit patterns from graphic and mask through two 256-byte nibble tables (1 ink, 2 the mask's
  cleared border, 0 clear), minus the pixels the foreground pieces own (a coverage map made from the list at 0xA10B
  when it changes: data OR NOT mask, as 0xA09B plots); the game's own copy called at 28 MHz; then all 48 sprite
  attributes in one run (pattern sets alternate, so no shown pattern is written); then a wait on the video line for the
  rest of the copy's own time (65,335 T for 112 lines, 83,978 T for 144; shared pace library).
  0xA615 (the attribute copy): cells that still hold their paint (colour before OR 0x47) get their colour back, the
  game's copy runs at its own speed, the paint goes back. R is set to the original's before the call: one way through
  the copy reads R (0xA6B0). Where a cell's own ink is under the ink limit of 0xA6C6 the game's copy takes a shorter
  path than with the paint: R is corrected by 2 per such cell.
  0xBBF4 (the random byte): the same byte as the original at every address. The build's memory differs only in the
  attribute file's painted cells, and the routine can read two of them (0x5959, 0x5A5A): the attribute copy keeps what
  the build and the original hold there, and the hook answers with the original's while the build's is still there.
  The stubs end below 0x3939, the first hook-area ROM byte it can read, so those stay the ROM's 0xFF.
- Memory: stubs in the ROM's 0xFF area (alt ROM, 140 bytes); bodies in a RAM copy of 0x2000-0x3FFF (page 24) mapped at
  slot 1 inside a hook; state in page 26 at slot 4. The game's interrupt (IM 2, 0xF3F3 -> 0x60F3: sound, the hourglass)
  saves every register and touches neither slot in any recording (`isr`); it runs inside the hooks.
- Start: the snapshot's own BASIC (PAUSE 0, RANDOMIZE USR 25000) runs on Sinclair's ROM as alt ROM image 1; tail at
  0x5E00 in BASIC's spare memory, overwritten by the game's own move before any read.
- DMA / DDMA (docs/DDMA.md): the uploads are 256 or 768 bytes from a RAM buffer by OTIR; the hook is already faster
  than the copy it wraps and waits out the rest, so a blitter would only lengthen the wait. Not used.
- Not built: colour sheets, recolour, an Enhanced set. Patterns are made at run time from the game's 1-bit graphics, so a
  painted graphic needs patterns made ahead and a lookup by graphic address (as Nodes of Yesod has).

## Hardware checklist
- Loading screen, any key, 1 (keyboard): the game starts as the original.
- Figures are bright white over every room colour; nothing of a figure in the room's colours, no white wash on scenery.
- A figure behind a foreground piece (the bed's posts, arches) is cut by it as in the original.
- No trace of a figure left behind when it moves or a room changes; no flicker as the room is redrawn.
- The bolt fired across a figure: the figure stays whole.
- Sound and speed as the original over a minute of walking; the hourglass runs at the original's rate.

## Stage 1 question (asked 2026-11-17; owner: "yes go ahead with heartland as you proposed")
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
- Hardware: nothing run on a board; the checklist above. Sound: an interrupt inside the copy hook's 28 MHz part runs the
  game's handler at 28 MHz for that frame.
- Enhanced colours, colour sheets, recolour: not built (Build, last line). The owner paints later.
- The mask's border is black in the build and the cell's paper in the original: the same on black paper; on a room with
  coloured paper it is a black edge. Not seen by the owner yet.
- The random byte's two cells: if something other than the attribute copy writes 0x5959 or 0x5A5A the very byte the
  build's copy left there, the hook answers with the original's old colour. No recording reads either cell with the
  paint lifted (none of the screen reads in the recordings).
- A figure that wraps past the buffer's right edge shows on the next line in the original; a sprite would be cut at the
  window. Not reached in the recordings (the sprite model compares every copy).

## Decisions
- 2026-11-17 (owner): the defaults as proposed: every figure a sprite in bright white, rooms and panel on the ULA in
  their own colours, figures behind the foreground pieces as in the original, sparks on the ULA; Enhanced colours later.
- 2026-11-18: the figures also stay in the bitmap under their sprites, and the bolt passes behind a figure (Build): the
  game's random bytes need the buffer and the bitmap as the original has them. To tell the owner with the build.

## Lessons
- [local: this game's design] A game that draws random numbers from a byte at an address made of R can read any byte of
  memory: taking figures out of a buffer or off the screen changes the game. The first design passed every picture check
  and failed only the whole-state comparison, 906 steps in. Reason: the per-hook checks cannot see a reader elsewhere.
- [local: this game's hooks] A hook that wraps one of the game's own routines must hand it the original's R, not only
  leave the original's R after it: the attribute copy reads R on one of its three ways. Found by a unit case that forces
  each way; the recordings only take the plain one.
- [local: this game's hooks] Changing the data a wrapped routine works on can change how many instructions it runs: the
  ink limit takes a shorter path for a cell without its paint, so R needs a correction per cell.
- [local: this game's verifier] The game keeps its random routine's XOR operand in the routine's own code (0xBBF7): a
  hook that copies the listing's constant is wrong from the second call.
- [local: this game's intake] The snapshot is the tape's BASIC start and the game moves itself down by 0x6AC before it
  runs: every site is patched at its snapshot address and verified at its address in play.
- [local: this game's intake] The owner's four minutes of play gave 2,485 game steps and the bolt; six scripted
  recordings gave about 550 steps each and no bolt.
- [deferred Open: reconsider when the engine is designed] The coverage gate passes on a game that composes its
  figures in a back buffer, because none of their plotters is a screen writer. Reason: it only follows screen writes.

## Friction
- reuse: [local: private run folder] the Arc of Yesod search and RZX scripts, with the toolkit's 48K machine.
- retries: [local: this game's design] one full design thrown away (figures out of the buffer), see Build.
- hand-rolled: [local: this game's module] a paged memory view and hook runner, as Father Christmas has its own.
- environment: [local: this machine] Fuse 1.9.1 for the owner's recording; OverSpec's --ui-script for a scripted start.
- scratch: [local: private run folder] explore.py, mkrzx.py, play48.py, zd.py kept with the inputs.

## Technique use
- patch.xor-overlay-keep-ula: helped: the second design is this card on a back-buffer game (the bitmap untouched,
  sprites on the figures' own pixels).
- detect.gameplay-screen-readers: helped late: `scan --writers` named the one reader of the buffer outside the plotters
  (0xBBFA) once the state comparison had failed; run it on the buffer before the design next time.
- patch.preserve-r: helped: the library's set / add calls carried every hook, the wrapped routines included.
- patch.pace-limiter: helped: one window around the screen copy, the other hooks as debt.
- patch.whole-altrom-image: helped: the BASIC start needed nothing in the engine.
- detect.pacing-structure: no help: the copy's time was read off the verifier's own run of the routine.

## Stage log
- 2026-11-18: stages 2-3 (the owner's recording; first design, dropped; second design, verifier, unit cases, broken
  builds, pace, record), about 6 h, about 150 tool calls, 3 user rounds. Whole-module reads: none; Cobra's and Father
  Christmas's patch classes and the Nodes header were read in part as models.
- 2026-11-17: stage 0 (first pass), about 30 min, about 10 tool calls, 1 user round.
- 2026-11-17: stage 1 (feasibility: disassembly of the update, the three plotters, restore, foreground list, sparks; preview), about 30 min, 9 tool calls.
- 2026-11-17: stage 0 (second pass: room-guided recordings, survey, buffer writers), about 30 min, 6 tool calls.
