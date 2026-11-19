# Gauntlet (US Gold, 1986; 48K code, the 128K's AY)

## Next session
Stage: 3 (verified and stamped from one snapshot; not delivered as a game)   State: 2026-11-19: plain, painted
("sprites", with the panel) and steady-speed builds from a cut of the first level block in play; record stamped; both
builds run in OverSpec; not on hardware; no .nxc published (a build asks for the tape after its block)
Inputs (private, pilot runs/gauntlet/reference_files/gauntlet): gauntlet_p1.z80 + gauntlet_p1.rzx (the record's:
the rzxarchive's block 1 recording cut at frame 1501); gauntlet_b1, b2, b10 (the same archive's recordings from the
"rewind tape" prompt); gauntlet_colours.json (the painted map); 28 more block recordings in the run folder
Branch: add-gauntlet    Commit: this one    Checks: selftest --game gauntlet --verify --stamp, doccheck
Pending user answers: "Open" 1-3
Start with: "Open" 1 (the tape's level blocks from memory)
Read: "Build", "Panel", "Open"

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

## Painting (2026-11-19, first pass)
- Sheet of 716 pictures (607 tiles with their colour schemes, 109 generator pieces) painted by a Codex pass after the
  arcade game (58 colours, 9 palette lines); the owner's painting folder `nexclash-gauntlet`; `sheet2colours.py` makes
  `gauntlet_colours.json` (1,553 cells), kept beside the snapshots: it holds the game's pictures, so not in this repo.
- 216 cells are painted differently in two pictures that share them (the first is kept).

## Hardware checklist
Not built for hardware yet (the level blocks first).

## Open
1. The tape: a build starts in its block's levels and then asks for the tape. One program needs the 31 blocks in
   memory and the loader call answered from them. Owner's decision how to ship meanwhile.
2. Steady speed: 3 frames an update is the original's fastest; the owner has not tried it. The option's place in the
   .nxc menu is not made (`auto` writes NAME_steady.nex beside the others).
3. The painted map holds the game's pictures: where it lives for a public patch.
4. The floor (blank cells) is left black; the panel and all text stay as they are.
5. The tile layer is written before the copies: for part of a frame the tiles are one update ahead of the screen
   under them (cells that are not painted). A definition slot can be reused while its old tile is still on the map
   for part of a pass. Neither seen in OverSpec in a short run; not looked for on hardware.
6. 28 block recordings not yet run; the reference files are not in the maintainers' reference set.

## Decisions
- 2026-11-19 (owner): "Go ahead with you recommendation": everything painted, on the tile layer.
- 2026-11-19 (owner): the slowdown "might be an opportunity to fix that in the nxc patch option": the steady build.

## Lessons
- [local: this game's design] A game that draws only grid-aligned blocks needs no plot hooks: the picture is looked up
  from the finished hidden screen, so nothing of the game is touched and scrolling needs no tracking.
- [local: this game's hooks] A pace window longer than a frame loses a frame unless its clock is read inside it: the
  pass on a full screen took 70,000 T too long until it read the clock every row.
- [local: this game's hooks] A hook where interrupts are on cannot map the state page when the handler reads the ROM:
  the clear's hook only changes the speed and its saved time is waited out in a hook that runs with interrupts off.
- [local: this game's verifier] A broken build must be one the data can show: "attribute not compared" cannot fail
  here, because the attribute already picks the chain.
- [local: this game's intake] The archive's block snapshots are taken at the "rewind tape" prompt; a build that starts
  in play needs the recording cut at a frame where the game waits at its HALT (`rzx.cut`).

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
