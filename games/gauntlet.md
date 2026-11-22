# Gauntlet (US Gold, 1986; 48K code, the 128K's AY)

## Next session
Stage: 3 (verified, stamped, published as an .nxc for the tape)   State: 2026-11-19: the whole game from both sides of
the tape, starting at the title picture (record `gauntlet_tape`); the main game's hooks proven from a cut of level block 1
in play (record `gauntlet`); all four heroes and the panel painted; a steady-speed toggle; runs in OverSpec; not on hardware
Inputs (private, pilot runs/gauntlet/reference_files/gauntlet): gauntlet_start.z80 + .rzx (the archive's Main Title
recording cut at frame 72) and the US Gold tape's two sides; gauntlet_p1.z80 + .rzx; gauntlet_b1, b2, b10;
gauntlet_colours.json (the painted map); 28 more block recordings in the run folder
Branch: add-gauntlet    Commit: this one    Checks: selftest --game gauntlet / gauntlet_tape --verify --stamp, doccheck
Pending user answers: "Open" 2-4
Start with: "Open" 1 (the shots), or the owner's review
Read: "Build", "The whole game from the tape", "Open"

## Result (2026-11-19)
Techniques: `patch.hybrid-display-replacement`, `patch.pace-limiter`, `patch.preserve-r`, `patch.restore-speed`

Whole recordings of blocks 1, 2 and 10 from the "rewind tape" prompt, and block 1 again from a cut in play (61,548 frames).

| | |
|---|---|
| Builds | from the play cut: gauntlet_p1_sprites.nex 1ad7e77e (painted, the original's pace), gauntlet_p1_steady.nex 255412ee, plain ad2ec631; blocks 2 and 10: ccb49e72 / 67e0ae62, 7c357316 / f60f6e52 |
| Verify | IDENTICAL on all four: 11,502 updates; every register with R and all game memory after each of the five hooks; 7,361,280 cells of the hidden copy against the painted map (2,396,518 painted cells shown); every 4th frame's tiles against the visible screen (10,735 frames, none off) |
| Tiles | at most 146 distinct tiles in a pass (205 slots); no cell left unpainted for want of a slot |
| Steady | the steady build's hooks and tile layer IDENTICAL on the first 3,000 frames of each (the wait itself: unit cases) |
| Unit | PASS: 25 cases (first pass on a dirty page, the same picture twice, the pass counter's wrap, no free slot, slots taken from cells off the screen, the steady wait from 0, 1, 2, 3 and 7 frames) |
| Negative | 5 broken builds a recording, all detected |
| Pace | the hooks take 0.03% to 0.08% of a recording's time less than the copies and the clear they stand for; an update within about 1,300 T, but the first (one clear's time, once) |
| Emulator | both builds of the play cut start and run in OverSpec (scripted, 4 captures each); nobody has played them |
| Known differences | none in the game. The steady build is a different pace by design: an update every 3 frames |

## Feasibility (2026-11-18; block 1's snapshot)
- 128K snapshot of the 48K game: 7FFD 0xD0 (ROM 1, bank 0, paging locked). IM 2 (I 0xDB, 0xDADA -> 0xA29F): sound and
  a frame counter (INC (IY+24) = 0x8497). The game runs in the main thread.
- A hidden copy of the screen at 0xC000-0xDAFF. Every update: `HALT / DI`, three stack copies (0x9CDC: the top third,
  the attributes, the rest of the 20-row window: 35,796 + 10,587 + 53,684 T, always the same), the handler called by
  hand, then the hidden copy cleared (0xB4FF, 34,357 T) and everything drawn again.
- Everything is drawn by four plain block plotters (0x9DD2 16 x 16, 0x9E4B 8 x 16, 0x9EA0 16 x 8, 0x9ED7 8 x 8): no
  mask, no shift, the block's attribute written to its cells. Creatures move on the 8-pixel grid, one ink on black.
- 284 block pictures in all 31 block recordings (607 with the walls' colour schemes), 867 distinct 8 x 8 cells in them;
  the monster generator's box is mixed at run time from 109 more cells.
- An update takes 3 to 8 frames (mean about 5): the slowdown the owner remembers. At most 189 distinct non-blank cells
  in the window at once (five long recordings).
- The tape's levels load in 31 blocks through the ROM loader; a block snapshot starts at the "rewind tape" prompt.

## Build (stage 2, 2026-11-19; asm/gauntlet_hooks.asm, nexclash/gauntlet.py)
Nothing of the game changes; the Next's tile layer shows a painted tile over each cell it knows.
- `e_c1 / e_c2 / e_c3` (the three CALLs of the copies): 28 MHz, the game's own copy, its own time waited out. Before
  the first copy the tile pass: each of the window's 640 cells of the hidden copy is looked up by its 8 bytes and its
  attribute (two 8-bit sums pick one of 1,024 chains; the entry's 9 bytes are compared); a painted cell gets a map
  entry and, when it has none, a tile definition (205 slots: the map's own bytes for the window's rows take 50 of the
  256; the slot no cell of this pass shows is taken, its owner forgets it); any other cell the clear tile.
- `e_cl` (the CALL of the clear): 28 MHz with nothing mapped and no wait (interrupts are on there and the handler reads
  the ROM); the time it saves is added to the first copy's target. It pays for the pass on a screen full of walls.
- `e_pre` (the CALL after the game's `HALT / DI`): nothing at the original's pace. Steady speed: the game at 28 MHz and
  each update shown 3 frames after the last (the original's fastest), by the game's own frame counter.
- The tile layer: bank 7's first 8K (the 48K game never pages it), map and definitions from its first byte, clipped
  to the window; palette of 16 lines, index 0 clear. The page is cleared by the first pass.
- Code in the alt ROM from 0x2800 (the game loads through the ROM below it); state page at slot 0, the tile layer's
  page at slot 2, the cell table at slots 3-5 inside the pass (interrupts off: the game's own DI).

## Panel (2026-11-19; owner: "Can you fix up the hud?")
- The status panel (screen rows 20-23: the class, score, health, keys, potions, the logo, PRESS FIRE) is drawn by the
  game straight on the screen. The tile pass copies its 4 rows aside, and each of its 128 cells that changed since the
  last pass is looked up by its bytes alone and drawn as 64 painted pixels on Layer 2's last page (lines 160-191), or
  cleared. Layer 2 lies over the ULA and the tile layer; its colour 0 is the transparent one.
- Why Layer 2 and not tiles: with the panel on the tile layer one pass showed 192 distinct tiles of the 195 slots left.
- A cell left of column 16 whose ink is its paper is hidden by the game (a number kept dark) and stays hidden. The logo
  (columns 16-31), which the game blinks and colour-cycles the same way, is shown steady: 45 cells redrawn at every
  blink cost about 55,000 T, and the brief asked for one painting.
- 69 panel cells painted by a second Codex pass (gold logo, red class name, parchment labels, bright digits).
- Verify: Layer 2's page equal to the painted panel after every pass; a unit case changes a digit on the screen.
- After the panel: builds gauntlet_p1_sprites.nex 546393f1, _steady e93290d1 (blocks 1, 2, 10: ed5bd3bd, c7984e3a,
  66c98358); all four recordings PASSED again; 6 broken builds each; pace -0.016% to +0.072%; block 10 has 21 of 2,041
  updates more than 5,000 T over (a pass that redraws many panel cells).

## Levels from memory (2026-11-19; owner: "Yes" to starting it)
- The tape's second side is 31 headerless blocks: the first with flag 0x80, the rest 0xC0. The game's loader (0x9203)
  asks the ROM (CALL 0x056B at 0x9247, up to 0x1100 bytes at 0xC000) for flag 0x80 at the start of a game and for 0xC0
  after that, so it takes whichever 0xC0 block comes next on the tape; it accepts a block by its 0xFF end mark and
  runs the block's own code at 0xC000.
- With `--tape SIDE_B.tzx` (profile `tape_sets`: US Gold, Erbe and Kixx hold the same blocks) the build carries the
  blocks in pages from 40 and answers the CALL from them (`e_load`: block 1 for 0x80, then 2 to 31 in order and round
  again from 2); the "start the tape" messages and their key wait are passed (`e_ld0`), the "rewind tape to start of
  side 2, then press space" prompt is a RET (0xB494).
- Proof: recording 1 holds the real tape load of block 1; the hook's bytes at 0xC000-0xD010 equal it. A unit case asks
  35 times and gets the blocks in tape order. Each later archive recording's snapshot holds its own block's bytes
  (blocks 2-31 matched to recordings 2-31 by content, runner-up far behind). From the end of recordings 1, 2 and 9 the
  next block from memory installs and the game reaches its next update.
- Runs in OverSpec from the block-1 snapshot: the attract loop, fire, "LEVEL : 1", the level.
- Not done: the record and the .nxc for the tape build; the title, the controls menu and the choice of character live
  in a front end that loads the main game from side A (the block-1 snapshot is the main game with player 1 = warrior,
  player 2 = valkyrie, Sinclair joystick keys); the valkyrie, wizard and elf, the thrown weapons and player 1's logo
  are not painted (no archive recording shows them).

## The whole game from the tape (2026-11-19; owner: "Yes go ahead")
- Side A: a BASIC loader, the front end (flag 0x80, 21,008 bytes at 0x8600: title, credits, the heroes' screen, the
  controls menu), then flag 0x81 (2,881 bytes at 0x73DA) and flag 0x82, the main game (30,583 bytes at 0x8400). The
  tape's loader (0xFF00) calls the front end, then loads the two blocks and jumps to 0x8400. The front end leaves the
  choices at 0xFFFB-0xFFFF (controls, player 2's hero at 0xFFFE, player 1's at 0xFFFF); the main game's start builds
  each player's 32 pictures (33 bytes each: attribute, 16 x 16) at 0x5F00 and 0x6320 from them.
- A build from the front end's snapshot with both sides (`--tape SIDE_A --tape SIDE_B`): the two blocks sit in pages
  from 52, the main game's with this build's CALLs already in it; `e_main` (the loader's instruction after the front
  end returns, 0xFF12) copies both and jumps. The loader's stack is in slot 2, so the hook uses none.
- The start: the archive's Main Title recording, cut at frame 72: its "stop tape and press space" is answered and the
  title picture is on the screen. The setup puts the printer buffer back (the loader's stack is there).
- Proof: the front end's recording runs the tape's own code (IDENTICAL, 2,153 frames). The hand-over is a unit case
  from the snapshot (both blocks where the loader puts them, the main game the tape's but for the build's sites,
  nothing else written) with one broken build. No recording crosses the hand-over or a level change.
- The cell table has a fourth page at 0xE000 during a tile pass (1,999 cells; a hook has its own stack and interrupts
  are off, so the game's stack page can be away).
- The other heroes: the valkyrie, the wizard and the elf (32 pictures each, taken from the game's own tables after its
  start with each choice) and the panel's cells for them are painted (377 cells added; 15 palette lines).
- .nxc: made by the nxc repository's tool against the tape set (`make ... --also SIDE_B --start gauntlet_start.z80
  --tape-bank 20..28`): the main game and the level blocks are copies from the player's tape, none of them carried;
  it rebuilds both builds byte for byte. "Steady speed" is a toggle, off by default.

## Painting (2026-11-19, first pass)
- Sheet of 716 pictures (607 tiles with their colour schemes, 109 generator pieces) painted by a Codex pass after the
  arcade game (58 colours, 9 palette lines); the owner's painting folder `nexclash-gauntlet`; `sheet2colours.py` makes
  `gauntlet_colours.json` (1,553 cells), kept beside the snapshots: it holds the game's pictures, so not in this repo.
- 216 cells are painted differently in two pictures that share them (the first is kept).

## Hardware checklist
Not built for hardware yet (the level blocks first).

## Open
1. Shots: the heroes' and monsters' shots are drawn at pixel positions (not by the block plotters), so their cells are
   endless in number and stay unpainted: Spectrum colours, a block of the wall's colours where one crosses a wall.
   Sprites for the shots would fix it; the owner decides.
2. Steady speed: 3 frames an update is the original's fastest; the owner has not tried it.
3. The painted map holds the game's pictures: where it lives for a public patch (the .nxc carries the painted pages).
4. The owner has not reviewed the painting (tiles, panel, the three later heroes) in play.
5. The high score tables and name entry keep their Spectrum colours (text cells are not painted).
6. Kixx and Erbe tapes hold the same blocks (profile `tape_sets`); the .nxc accepts the US Gold set only so far.
7. Nothing has run on a board; no recording crosses the hand-over or a level change.

## Decisions
- 2026-11-19 (owner): "Go ahead with you recommendation": everything painted, on the tile layer.
- 2026-11-19 (owner): the slowdown "might be an opportunity to fix that in the nxc patch option": the steady build.

## Lessons
- [local: a clear's speed-up pays the pace] e_cl must run the clear at 28 MHz (its saved time pays for the tile
  pass) and give back the caller's speed within STACK (6 bytes): A kept for the clear, the speed below it, EX (SP),HL
  to restore it without touching the clear's outputs (F = 66, B = 0). The replay alone passed a fix that lost A:
  it always enters with A = 0 at 3.5 MHz; the unit case at speeds 1-3 caught it.
- [local: this game's design] A game that draws only grid-aligned blocks needs no plot hooks: the picture is looked up
  from the finished hidden screen, so nothing of the game is touched and scrolling needs no tracking.
- [local: this game's hooks] A pace window longer than a frame loses a frame unless its clock is read inside it: the
  pass on a full screen took 70,000 T too long until it read the clock every row.
- [local: this game's hooks] A hook where interrupts are on cannot map the state page when the handler reads the ROM:
  the clear's hook only changes the speed and its saved time is waited out in a hook that runs with interrupts off.
- [local: this game's verifier] A broken build must be one the data can show: "attribute not compared" cannot fail
  here, because the attribute already picks the chain.
- [local: this game's intake] The archive's block snapshots are taken at the "rewind tape" prompt; a build that starts
  in play needs the recording cut at a frame where the game waits at its HALT.

- [local: this game's tape] A multiload's blocks and a front end's hand-over need no recording across them to prove the
  bytes: one recording that holds a real tape load fixes the layout, and the rest compare with the tape file itself.
- [local: this game's colours] Pictures no recording shows can be taken from the game's own tables once its start is
  understood (the heroes), but anything drawn at pixel positions (shots) has no finite set of cells: decide that at
  the design stage, not after the painting.
- [local: this game's start] A front end's snapshot can open on a tape prompt: cut the recording past it and the build
  opens on the title, with the cut's recording still proving the rest.

## Friction
- reuse: [local: this game's module] the Simpsons engine's hook runner and report shape (that branch is not merged).
- retries: [local: this game's hooks] three pace fixes (debt cap, the clock in the pass, the clear as a second source).
- environment: [local: this machine] `auto` on a whole block takes about 10 minutes; three in parallel.
- hand-rolled: [local: this game's module] a paged memory view for five pages, the tile layer and Layer 2 as plain pages.
- scratch: [local: private run folder] NOTES.md and collect.py; the trace and timing scripts were session scratch.

## Technique use
- patch.pace-limiter: helped; its debt carried the tile pass's cost to the later copies' waits.
- patch.preserve-r: helped: the library in the wrappers, an inline form where nothing may be mapped.
- patch.hybrid-display-replacement: helped: the idea of a Next layer over an unchanged original display; here the
  original's routines are not replaced at all.
- patch.restore-speed: helped: the library in the wrappers.

## Stage log
- 2026-11-18/19: stages 0-2 in one session (32 recordings replayed, the art set counted, a Codex painting pass, hooks,
  verifier, steady speed), about 4 h, about 60 tool calls, 3 user rounds.
