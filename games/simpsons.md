# The Simpsons: Bart vs. the Space Mutants (Ocean, 1991; 128K only)

## Next session
Stage: 3 (verified and published a level a patch; not one game yet)   State: 2026-11-19: each of the tape's five levels
builds from its own snapshot (plain, sprites, Enhanced), verifies on its whole recording and is stamped (records
simpsons_l1..l5); five .nxc patches for the Ocean tape are published (owner: "Publish it"); all five start and play in
OverSpec from their menus; not on hardware
Inputs (private, pilot runs/simpsons/reference_files/simpsons): simpsons_l1..l5.z80 and .rzx = the rzxarchive's five
level recordings (SPIN 0.5), each with its own 128K snapshot; simpsons_colours.json (the painted map); the tape
(Simpsons - Bart vs the Space Mutants (1991)(Ocean)[128K].tap, md5 8e08c32c3265f6c4a65cf7e5f72b9913) is in the run folder
Branch: add-simpsons    Checks: `selftest.py --game simpsons_lN --verify --stamp` (one level a run), doccheck
Pending user answers: see "Open" 1-3
Start with: "Open" 1 (one game from five loads)
Read: "Build", "Open"

## Result (2026-11-18)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.display-atomic-switch`, `patch.preserve-r`,
`patch.restore-speed`, `patch.pace-limiter`, `patch.whole-altrom-image`

One recording a level (the rzxarchive's, 102,687 frames in all), each from its own snapshot; both builds of every level.

| | |
|---|---|
| Builds | level 1: simpsons_l1_sprites.nex fa3a5f41, _enhanced a7ab6c76; level 2: a634bef1, 647240a6; level 3: 0530f110, f47b2a8f; level 4: 866dd924, 09610b67; level 5: bbe3b9b8, a9e3b97e ; plain: 706e2084, 3ec33dfe, 3e348c60, 5421d05c, 8d894a9c |
| Verify | IDENTICAL on all five, both builds: 89,375 draw passes, 368,703 draws, 331,486 figures, 91,073 flips; every register with R and all game memory after every pass and flip; 51,315,968 sprite pixels against a model of the width loops; every frame's shown sprites against the visible screen (91,353 frames) |
| Painted | 51,603,165 painted sprite pixels equal to the painted map; all but 288 of the figures are painted (the rest: shapes drawn from the middle of their rows by the game's own top clip) |
| Unit | PASS on all five, both builds: 15 cases plain, 18 or 19 painted (flips with nothing to do, the sprite list and the pattern set full, a pass with no objects, a shape the map does not know) |
| Negative | 10 or 11 broken builds a level, all detected on all five |
| Pace | the hooks take 0.12% to 0.24% of a recording's time less than the draw passes they stand for; 2% to 4% of passes land more than 3 video lines from the original's time (the wait ends on whole lines and carries the rest) |
| Known differences | level 5: 11 figures in 9 frames where the game redraws scenery over a figure it has just drawn: the build shows the figure. Bytes past the right edge and rows past a clipped shape's end stay the game's own drawing in the scenery's colours (as the original). The plain build's figures are black and white everywhere; in the original they take the cell's colours |
| Emulator | all five start from their .nxc menu in OverSpec with Enhanced on and play past the level intro (scripted keys, 2026-11-19) |
| Published | 2026-11-19: five .nxc patches for the Ocean tape, each from the tape with the level's snapshot as its start state (6 to 10 KB of the start state is not on the tape and is carried); each rebuilds its two builds byte for byte |

## Feasibility (PLAYBOOK 3d, 2026-11-18; disassembly of level 1 in play, addresses are level 1's)
- 128K only, ROM 0 selected in play. IM 2 (vector 0x80FF -> 0x8181 -> 0xA2B5): the whole game runs in the interrupt
  handler, 50 times a second (DI at each state handler's start, EI before RETI); the main thread is `JP $`.
- Two screens (bank 5 and bank 7), flipped every frame: 0xA38B toggles its own operand (0xA38C), sets the row tables and
  the save lists of the new back screen; the 7FFD OUT follows in the music call's wrapper.
- A frame of play (0x9CA2): flip, input, erase the figures drawn two frames ago on the back screen (0xB492, from a save
  list), draw every object (0xB170: three fixed records - Bart is a head and a body - and nine of 0x1C bytes).
- The draw routine (0xB1C3, IX = the object): the pre-shifted shape for x AND 7, clipped to the view (160 lines, the
  view's x), then one of eight width loops (1-4 bytes a row, plain or mirrored through a bit-reverse table): the screen
  byte saved, then (screen AND mask) OR graphic from byte pairs taken off the stack pointer. The graphic's pixels take
  the cell's ink, the mask's cleared pixels its paper: a figure wears the scenery's colours.
- The same routines sit at other addresses in each of the tape's five loads; three of them differ a little (the draw
  pass begins with a counter in levels 1, 2, 5). The sites are found by their bytes (`find_sites`).
- Bart's body shapes are rewritten in place as he moves: a shape is known by its bytes, not its address.
- The game reads 128K ROM 0 bytes as data (0x0562-0x0570, 0x05E7-0x05F9, through the stack pointer) and keeps data in
  the printer buffer (0x5B00-): alt ROM image 0 = that ROM, and the setup puts the printer buffer back after NEXLOAD.
- The R register is read by the handler (music bank), so every hook leaves R as the original does.

## Build (stage 2, 2026-11-18; asm/simpsons_hooks.asm, nexclash/simpsons.py)
The game's memory and both screens stay the original's; sprites lie on the figures' own pixels.
- `e_all` (the draw pass, at its `LD HL,(nn)`): 28 MHz for the pass, the routine's return taken through the hook, then
  the pass's own time waited out on the video line: the loop's, plus a time for each draw by width code and rows, the
  object's pre-shift kind, clipped or not (`TIMES`, `ROW_T`, fitted from the recordings by `fit_times`).
- `e_shape` (`POP HL / POP DE / LD SP,HL`): the shape's address and size, no stack (SP is the data pointer).
- `e_note` (`LD (nn),HL`, the width loop chosen): the figure is clipped; its 16 x 16 patterns go straight to the pattern
  port (4 bit: 1 graphic, 2 cleared, from two nibble tables), its sprites are listed. Bytes past the right edge wrap in
  the original (an 8-bit address); they stay the game's own drawing, the sprites are clipped there.
- `e_flip` (`LD (nn),A` of the flip): the listed attributes in one run, the sprites of the last list beyond them off,
  the other pattern set (64 patterns each) for the next frame.
- Code and tables in both alt ROM images from 0x2000; the state page at slot 0 inside a hook; a colour page at slot 2
  while its bytes are sent. Interrupts are off wherever the hooks run (the game's own DI): the verifier checks it.
- R: `e_shape` and `e_note` leave R as the instruction they replace; `e_all` hands the routine the original's R and
  takes it back after; the constants are in the source.

## Enhanced (2026-11-18, first pass; owner: "Colourize the sprites, using the carton show as a reference")
- Sheet: every picture the five recordings draw (237, cropped shapes), painted by a Codex pass from a brief with the
  cartoon's colours (33 colours); files in the owner's painting folder (`nexclash-simpsons`), `sheet2colours.py` makes
  `simpsons_colours.json`, kept beside the snapshots: it holds the figures' outlines, so it is not in this repository.
- In the build: a shape's bytes give three keys (their sum and a 16-bit hash) and its size; the index page maps them to
  the picture's strips (each 16-pixel column's 8 bytes a line), as stored and mirrored, with its palette line and x
  offset. A level's pictures share at most 15 palette lines of 15 colours (3 to 5 used).
- A shape the map does not know is drawn in the plain colours. Rows the original draws past a shape's end (clipped at
  the top it goes one row into the next shape) stay its own drawing on the screen.

## Hardware checklist
Each level: starts from the menu; Bart and the other figures visible and animating, in step with the scenery as it
scrolls; no figure left behind after a screen change; music unchanged; Enhanced: the same with the painted colours.

## Open
1. One game: the tape loads each level over the last. The five builds are five separate programs that start in their
   level. A single .nex that holds all five and changes level from memory needs the game's loader call found and a
   recording that crosses a level change (the owner's, or scripted with a cheat). Owner's decision how to ship meanwhile.
2. The painted map holds the figures' shapes: where it lives for a public patch (the .nxc carries the colour pages
   anyway; the map itself is the question).
3. Shapes no recording draws stay unpainted; the owner has not seen the painted sheet in the game.
4. Level 5: nine frames where the game redraws scenery over a figure it has just drawn; the build shows the figure.
5. hlib's shared sprite model still lets NextReg 0x34 select the attribute port
   (this engine's own model refuses it, as Heartland's).
6. Pace is from the simulator's line clock; nothing has run in JNext or on a board.
7. A level's build stops at its end, where the game asks for the tape: the player starts the next level's patch.

## Decisions
- 2026-11-18 (owner): Enhanced from the cartoon's colours. The plain sprite build's look (graphic black, cleared white)
  was not asked: it is what the game shows on its white pavement.
- 2026-11-19 (owner): "Publish it": a patch a level for the Ocean tape now, one program from the five loads later.
- 2026-11-18: the figures stay in the bitmap under their sprites (as Heartland): nothing of the game changes.

## Lessons
- [kb lesson.hook-call-overhead-at-28mhz: this game's hooks] A wait per figure cost about 1,600 T of 3.5 MHz time each (the limiter's own polls and the
  speed changes), more than the 28 MHz saved on a small figure: the first build was slower than the original with no
  wait at all. One window around the whole draw pass, with each figure adding its time to the target, fixed it.
- [local: this game's hooks] The game's stack pointer is its data pointer inside the draw routine: a hook there has no
  stack until it sets its own, and a register that looks dead (C at the shape) is live on the early exits.
- [local: this game's verifier] A Next model made new for every hook run forgets where the pattern and attribute ports
  stood: a build that never selected the attribute port's sprite passed until the model carried both between hooks.
- [local: this game's colours] The original's top clip steps 6 bytes a row whatever the shape's width and draws one row
  past a clipped shape's end: a painted strip there would be the wrong rows. Those figures and rows are left as the
  game draws them. Found only by whole recordings (3 of 5 levels), never in the first 1,500 frames.
- [kb lesson.graphic-keys-collide-or-move: this game's colours] Three 8-bit keys (sum, sum of sums, rotate and XOR) gave two of level 2's striped poles
  the same keys; a sum and a 16-bit hash (x 3 + byte + 1) with the size has no clash in 1,239 shapes.
- [kb lesson.byte-pattern-regex-escape: this game's verifier] Byte patterns for site search go through re.escape: 0x2A, 0x28 and 0x5B are regex
  syntax, and a bare pattern failed only on the levels whose code differs.
- [backlog C2 #15] `nexclash.py new` stopped on this 128K snapshot ('Machine' object has no attribute 'ay': the 48K-only
  analysis); the work went on with scan, isr, preview and a trace script.
- [deferred Open: reconsider when the levels become one program (Open 1)] Sites found by their bytes let one engine build five
  loads; the timing constants still had to be fitted per load.

## Friction
- reuse: [local: this game's module] Heartland's hook runner, model and report shape (that branch is not merged).
- retries: [local: this game's hooks] the per-figure wait, dropped for one window a pass; three painted rules found by
  whole-recording runs.
- hand-rolled: [local: this game's module] a 128K memory view, a per-frame check at the interrupt's entry.
- environment: [kb lesson.long-job-background-no-limit: this machine] five full runs in parallel take about 25 minutes; `auto` prints nothing until it ends.
- scratch: [local: private run folder] NOTES.md with the session's facts; the trace and fit scripts were session scratch.

## Technique use
- patch.xor-overlay-keep-ula: helped: the whole design; the game's memory compared equal from the first run.
- patch.pace-limiter: helped once used as one window a pass; its per-window cost is the lesson above.
- patch.preserve-r: helped: the library for the two wrapping hooks, an inline form where there is no stack.
- patch.runtime-colour-map: helped: the idea (per-image tables applied at the upload); the strips are sent whole
  instead of a mask pass, keyed by content because shapes are rewritten in place.
- patch.display-atomic-switch: helped: two pattern sets, attributes in one run at the game's own flip.
- patch.whole-altrom-image: helped (with `patch.altrom0`): the ROM 0 bytes the game reads needed nothing in the engine.

## Stage log
- 2026-11-18: stages 0-2 in one session (five recordings found and replayed, the routine read, hooks, verifier, painted
  path, a Codex painting pass), about 6 h, about 150 tool calls, 2 user rounds.
- 2026-11-19: stage 3: five records, each level's full verify and stamp (builds unchanged after merging main), five
  tape patches made and run in OverSpec, published at the owner's word; about 1.5 h, about 40 tool calls, 1 user round.
