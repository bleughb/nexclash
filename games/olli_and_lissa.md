# Olli and Lissa: The Ghost of Shilmoore Castle (Firebird, 1986; 48K code, a 128K snapshot)

## Next session
Stage: 3 (verified, stamped, published as an .nxc for the tape)   State: 2026-11-19: every moving figure a sprite on
its own pixels, white with a black edge, and an Enhanced set painted in a first pass; both builds verify on two whole
recordings; runs in OverSpec from its menu; not on hardware
Inputs (private, pilot runs/olli_and_lissa/reference_files/olli_and_lissa): olli_and_lissa.z80 + olli_nr.rzx (the
rzxarchive's "no rollback" recording and the 128K snapshot inside it), olli_b.rzx (the archive's other recording, its own
snapshot inside), olli_and_lissa_colours.json (the painted map); the Firebird tape (.tzx) is in the run folder
Branch: add-olli-and-lissa    Commit: this one    Checks: selftest --game olli_and_lissa --verify --stamp, doccheck
Pending user answers: "Open" 1-2
Start with: the owner's review of the painting, then "Open" 3
Read: "Build", "Open"

## Result (2026-11-19)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.display-atomic-switch`, `patch.pace-limiter`,
`patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

Two whole recordings from the rzxarchive (83,418 and 63,734 frames), both builds.

| | |
|---|---|
| Builds | olli_and_lissa_sprites.nex 61e0b6d0 (white with a black edge), olli_and_lissa_enhanced.nex b9c71476 (painted), plain 12be0e0a |
| Verify | IDENTICAL on both recordings, both builds: 154,081 figures and 180 wipes; every register with R and all game memory after each; 45,004,708 sprite pixels against a model of the routine; the model against the pixels the original has just drawn (none off); no sprite over a figure the screen has lost |
| Painted | every figure drawn is in the painted map (154,081 of 154,081) |
| Most at a time | 7 figures, 34 sprites; none left to the game for want of an entry or patterns |
| Pace | the hooks take 0.010% to 0.016% of a recording's time more than the routine; a figure at most 1,501 T over, 859 T under; 429 of 308,162 calls more than 3 lines off |
| Unit | PASS: 14 cases (the same picture twice, a new picture, no free entry, no free pattern, a size the table does not hold, the right edge, the top of the screen at y = 168, 169 and 172, a scene over a figure and clear of one, the wipe with interrupts on and off) |
| Negative | 9 broken builds, all detected |
| Boot | simulated, with and without NEXLOAD's printer buffer: registers and RAM as the snapshot |
| ROM paths | pass: every ROM byte the game runs or reads is as recorded |
| OverSpec | from the patch's menu, default and Enhanced: through lost lives to game over and back to the title |

## Feasibility (PLAYBOOK 3d, 2026-11-19; the recording's snapshot and its first 15,000 frames)
- 128K snapshot of the 48K game (7FFD 0x10: ROM 1, bank 0). In play interrupts are off (IM 1; they are on at the
  title, and at the title's wipe): nothing syncs the game to the frame, so the time a hook takes is game speed.
- It runs no ROM code and reads one ROM byte as data (0x0BEA).
- Every moving figure is drawn straight to the screen by one routine, 0x89DA: HL = a pair of pointers (graphic, mask),
  B = y (counted up from the bottom of the play area: the graphic's first line is 175 - y), C = x, D = rows, E = bytes
  a row. It takes the clean room from a copy at 0xE000 (the screen address OR 0xA000) into a buffer, ANDs the mask,
  ORs the graphic, and copies the buffer to the screen with a few rows of clean room above and below: a figure rubs
  its own trail out. The graphic is rows x bytes; the mask is (rows + 2) x (bytes + 1) and starts a row above and a
  pixel left of the graphic: every figure has a one-pixel edge of cleared room all round.
- Five CALLs of it: 0x88B7 Olli (24 x 24), 0x8C18 the room's objects (records of 0x13 bytes through IY: x, y, step,
  frame table, size), 0x8946 the cauldron's steam, 0x8F51 Sir Humphrey (48 lines), 0x86B2 Olli with his thought
  bubble (40 lines, at his own place: the same figure as 0x88B7's). Sizes drawn: 16, 24, 32, 40 and 48 lines by 2, 3
  or 4 bytes.
- Olli caught: the game plays a scene over him through the objects' CALL with records of its own (0x824D, then
  0x8260; the room's are from 0x92D6), 32 then 40 lines at his place, and draws nothing else until the wipe that
  follows: the scene rubs out Olli and whatever creature overlaps its box, and they stay rubbed out.
- Two more plotters draw things that do not move over the room: 0xFD51 (a block with its own attributes: the
  pick-ups, the title's pictures) and 0x918A (unmasked, shifted; never called in either recording). Left as they are.
- A new room and every other change of scene goes through the wipe at 0x82EB (five CALLs).
- The routine's own time: 23,648 T (16 lines, 2 bytes, no shift) to 77,218 T (48 lines, 4 bytes); it depends on the
  size and the shift (x AND 7) and on nothing else but a few T at a cell boundary.
- R is never read (no LD A,R in the code); the hooks leave it as the original all the same.

## Build (stage 2, 2026-11-19; asm/olli_and_lissa_hooks.asm, nexclash/olli_and_lissa.py)
The game's memory and screen stay the original's; sprites lie on the figures' own pixels.
- The five CALLs go to one hook: 28 MHz; the figure's picture as 4-bit patterns (1 where the graphic is set, 2 where
  the mask clears, made from the game's own bytes through two nibble tables; or its painted tiles from a page at slot
  2), sent into patterns no sprite shows; then the attributes of the figure's own sprites (12 a figure, 10 figures at a
  time, known by its record's address or its CALL); then the game's routine; then the rest of its own time waited out
  on the video line (a table by size and shift, made by the build from a run of the routine itself).
- A figure that shows the same graphic as last time gets only its attributes: nothing is sent again.
- A new picture goes into free patterns and the old ones are freed after the attributes change: a shown pattern is
  never written.
- The wipe's five CALLs: every sprite off, every figure and pattern forgotten.
- A scene's record (an object's key below 0x9000): every other figure whose box the scene's touches has its sprites
  switched off and its patterns freed, so it shows as the game has left it (rubbed out under the scene); a figure
  clear of the scene keeps its sprites. Each figure's entry keeps its x and y for this.
- The sprites' window ends at line 175, above the panel. A figure with no free entry or patterns, or of a size the
  time table does not hold, is left as the game draws it (counted; none in the recordings).
- Code in the alt ROM from 0x2800 (Sinclair's ROM around it: the byte at 0x0BEA is the original's); the state page at
  slot 0 inside a hook. The setup puts the printer buffer back after NEXLOAD (the game keeps data at 0x5B00).
- DMA / DDMA (docs/DDMA.md): not used. A hook sends at most 1,536 pattern bytes, each made from two table lookups, or
  an OTIR of ready tiles; the whole hook already fits inside the routine's own time at 28 MHz with room to spare, and
  a DMA transfer to the pattern port would need the bytes laid out first, which is the cost.

## Enhanced (2026-11-19, first pass; owner: "White plus painted")
- Sheet: every figure the two recordings draw (68: Olli's 16 frames, Lissa, Sir Humphrey with his thought bubbles, the
  ghosts, bats, spiders, frogs and the rest), each in its mask's box; painted by a Codex pass from a brief (Olli
  green, Lissa pink, the ghosts white with a pale blue shade; 4 palette lines of 15 colours); files in the owner's
  painting folder (`nexclash-olli`), `sheet2colours.py` makes `olli_and_lissa_colours.json`, kept beside the snapshot:
  it holds the figures, so it is not in this repository.
- In the build: a figure is known by its graphic's address and size (the build checks the bytes there against the
  painted map's key; all 68 figures' bytes are constant over both recordings); the state page holds an index of 8
  bytes a figure, pages from 28 hold its tiles as the sprites take them (128 bytes a sprite), with its palette line.
- A figure the map does not know is drawn in the plain colours.

## Hardware checklist
Starts from the menu; Olli, the creatures and Sir Humphrey visible, moving in step with the room, with no trail and no
flash; nothing left behind after a room change or a lost life; the panel untouched; sound unchanged; the game's speed
as the original's over a minute of play. Enhanced: the same with the painted colours.

## Open
1. The painting is a first pass the owner has not seen in play.
2. Where the painted map lives for a public patch (it holds the figures; the .nxc carries the painted tiles).
3. The unmasked plotter (0x918A) is never called in the recordings: a figure drawn through it stays the game's own
   drawing.
4. Pace is from the simulator's line clock; no JNext or hardware timing.
5. The pick-ups and the title's pictures keep their Spectrum colours (they do not move).

## Decisions
- 2026-11-19 (owner, stage 1): "White plus painted (Recommended)": moving figures as sprites in bright white with a
  black edge, an Enhanced option painted in a first pass for review; rooms and pick-ups as the game draws them.
- 2026-11-19: the figures stay in the bitmap under their sprites (as Heartland and The Simpsons): nothing of the game
  changes, so nothing that reads the screen can differ.

## Lessons
- [local: this game's verifier] The first recording run whole found a fifth fault after the second had passed whole:
  Olli caught (the second recording's player is never caught). The scene the game plays over him left his sprite and
  the creature's on over pixels the game had rubbed out. One whole recording is not all the game's paths either.
- [local: this game's verifier] The first 1,500 frames passed everything; the second whole recording found four faults:
  the routine draws a figure a line lower from y = 169 (it starts at the screen's first line), a wipe runs with
  interrupts on at the title, one pose of Olli is drawn through its own CALL and never again, and a later room's data
  sits where the first 15,000 frames touched nothing (the start-up tail was put there). Whole recordings before the
  record, and a tail address from every recording, not from the survey's first minutes.
- [local: this game's hooks] A hook at a site where interrupts can be on must not map the state page over the ROM's
  handler before DI: the wipe's hook takes the caller's interrupt state first (hlib_iff) and writes four bytes under
  the game's stack pointer to do it; the verifier allows exactly those.
- [local: this game's verifier] "A sprite where the screen no longer has the figure" fired 6,074 times and all but 12
  were two figures overlapping: the game's routine rubs out whatever is in its box and the other figure is drawn again
  within five calls. The check now waits eight calls before it asks.
- [local: this game's hooks] The shared model counts a 256-byte pattern as shown when either of its 4-bit halves is: a
  build that keeps its 4-bit patterns apart needs its own test of the half (this module's Model.halves).
- [local: this game's build] The routine's own time by size and shift comes from running the routine itself at build
  time on the snapshot's memory: no fitting from recordings, and the hooks came out within 0.01% at the first try
  once the constant for the hook's own entry and exit was set.
- [local: this game's painting] OverSpec resumes a game's last session from its data folder: a second scripted run
  never saw the patch menu, so "Enhanced" looked like the plain build until the run used a fresh folder.

## Friction
- reuse: [local: this game's module] Gauntlet's module shape (128K snapshot of a 48K game, alt ROM from 0x2800, state
  page at slot 0) and The Simpsons' painting tools.
- retries: [local: this game's analysis] the first model of the figure's layout was wrong (the mask is a row and a byte
  larger and starts a pixel left); the game's own routine run on an empty and a full background showed the layout.
- hand-rolled: [local: this game's module] the Next model's sprites carried between hooks; the survey's analysis pass
  on an 83,418-frame recording did not finish in 15 minutes and was run again with --stop 15000.
- environment: [local: this machine] the full check of both recordings and both builds takes about two hours.
- scratch: [local: private run folder] NOTES.md and tools/ (dumps, disassembly, the placement experiments).

## Technique use
- patch.xor-overlay-keep-ula: helped: the whole design; the game's memory compared equal from the first run.
- patch.pace-limiter: helped: one window a figure with the routine inside it.
- patch.display-atomic-switch: helped: the rule that a shown pattern is never written gave the free-pattern list.
- patch.runtime-colour-map: helped: the idea; the tiles are sent whole, keyed by the graphic's address.
- patch.preserve-r: used: R is not read by the game; the library's macros cost nothing to keep it equal.
- patch.restore-speed: used.
- patch.whole-altrom-image: helped: the one ROM byte the game reads needed nothing.

## Stage log
- 2026-11-19: stages 0-3 in one session (two archive recordings, the routine read and modelled, hooks, verifier, a
  Codex painting pass, the patch), about 9 h (two full checks of about 2 h each), about 150 tool calls, 2 user rounds (the request, the stage-1 question).
