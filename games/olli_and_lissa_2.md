# Olli and Lissa II: Halloween (Silverbird, 1987; 48K)

## Next session
Stage: 3 (verified, stamped, published as an .nxc for the tape)   State: 2026-11-20: every moving figure a sprite on
its own pixels, white with a black edge where the game has a mask, and an Enhanced set painted in a first pass; both
builds verify on the rzxarchive's whole recording (39 minutes); not on hardware
Inputs (private, pilot runs/olli_and_lissa_2/reference_files/olli_and_lissa_2): olli_and_lissa_2.z80 (the
recording's own snapshot, at the title menu), olli2.rzx (rzxarchive), olli_and_lissa_2_colours.json (the painted
map); the Silverbird tapes are in the run folder
Branch: add-olli-and-lissa-2    Commit: this one    Checks: selftest --game olli_and_lissa_2 --verify --stamp, doccheck
Pending user answers: "Open" 1-2
Start with: the owner's review of the painting, then hardware
Read: "Build", "Open"

## Result (2026-11-20)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.display-atomic-switch`, `patch.pace-limiter`,
`patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

The rzxarchive's whole recording (116,586 frames, 39 minutes), both builds.

| | |
|---|---|
| Builds | olli_and_lissa_2_sprites.nex dedec792 (white, Olli with a black edge), olli_and_lissa_2_enhanced.nex 2744a1af (painted), plain 53516907 |
| Verify | IDENTICAL, both builds: 193,740 draws and 82,619 plays; every register with R and all game memory after each; after a play the sprites against a model of the routine for the pass's figures (193,737 figures, 44,974,516 sprite pixels) and the model against the pixels the original has just copied to the screen (none off); no sprite on after the 339 fades and scenes |
| Painted | every figure drawn is in the painted map (193,737 of 193,737) |
| Most at a time | 5 figures, 11 sprites; none left to the game |
| Pace | the hooks within -0.004% (white) and -0.002% (painted) of the original's draws and plays over the recording; in any 10 seconds the game loses at most 15,629 T (0.2 frames) and gains at most 29,572 T (0.4 frames) |
| Unit | PASS: 35 cases (each of the three kinds staged and shown, the next pass's pattern set, a play with nothing drawn, the right edge, sizes, flags and places the hooks do not hold, the stage full, the pattern set full, the tile cache full, each JP site, two figures over each other, each fade and scene CALL with figures shown and staged, the CALL NZ not taken) |
| Negative | 10 broken builds, all detected |
| Boot | simulated, with and without NEXLOAD's printer buffer: registers and RAM as the snapshot |
| ROM paths | pass: the game runs no ROM code |
| OverSpec | the patch from its menu, Enhanced on: the title, play, Olli walking and jumping on scripted keys |

## Recording
- rzxarchive `o/olli2.rzx`: one part, 116,586 frames (39 minutes), with its own snapshot at the title menu (two
  bytes from TOSEC's "Olli & Lissa II - Halloween (1987)(Silverbird Software).z80", none of them code). It replays to
  its end.

## Feasibility (PLAYBOOK 3d, 2026-11-20)
- 48K. Interrupts are off in every frame of the recording: nothing syncs the game to the frame, so the time a hook
  takes is game speed. The game runs no ROM code.
- Another engine than the first and the third game's (neither one's routines are in it).
- The game keeps a copy of the screen at 0xC000 (the screen's addresses with bit 15 set; the attributes at 0xD800).
  Each pass of the main loop (0x80CC to 0x810C) it DRAWS every moving figure into the copy with one routine, 0x92E7:
  HL -> the picture's address (and, with A odd, the mask's after it), B = y, C = x, D = rows, E = bytes a row. The
  routine saves the copy under a rectangle round the figure on a list, ANDs the mask (5 bytes a row, two rows more
  than the graphic, 1 = kept) and ORs the graphic. Then 0x9453 PLAYS the list: each rectangle copied to the screen,
  then the copy put back as it was. The rectangle is 5 rows and a byte wider than the figure on each side, so the
  copy also rubs out the figure's last place. Figures drawn later are in front.
- A figure's box starts at line 174 - y; a masked graphic sits a row below and a pixel right of its mask's corner
  (the mask's first 7 bits and last 7 are always kept: the box is 26 lines of 32 pixels).
- Five JPs of the routine: 0x82B6 Olli (24 rows of 3 bytes, with a mask), 0x9052 Olli appearing and vanishing (the
  same), 0x8D6D sparkles (24 rows of 3 bytes, no mask), 0x8AFD the creatures and 0x8887 their puffs of smoke (16
  rows of 2 bytes, no mask). At most 5 figures a pass in the recording. 72 pictures (70 by their bytes); no
  picture's bytes change in the recording.
- One CALL of 0x9453, in the loop (0x80F2).
- The routine's own time is the sum of a term in the figure's kind and x AND 7 and a term in the kind and y (the
  screen rows the rectangle crosses): 10,200 T (16 rows of 2 bytes) to 34,000 T (Olli with his mask).
- The screen without figures: a new room (0x8646) and the title (0x9950) start with a fade of the attributes to
  black (0x9AC4), and so does the end of the game (0x815C); a lost life plays a scene on a black screen (0x82B9,
  CALLed from 0x8101 and 0x81DD). The figures on the screen fade or go black with it.
- R: the routine keeps a flag in R (LD R,A at its start) and the fade and the end sequence read R: a hook must leave
  R as the original.
- Other writers of the screen in play: the room builder, the pick-ups (0x8B4E, with their attributes), the score.
  They do not move. Left as they are. A creature that dies is rubbed out at once from the copy (0x88B9).

## Build (stage 2, 2026-11-20; asm/olli_and_lissa_2_hooks.asm, nexclash/olli_and_lissa_2.py)
The game's memory and screen stay the original's; sprites lie on the figures' own pixels.
- The routine's five JPs go to one hook: 28 MHz; the figure's tiles (4-bit patterns: 1 where the graphic is set, 2
  where the mask clears, or its painted tiles) are sent into the pattern set no sprite shows and the figure is staged
  (place, sprites, patterns); then the game's routine; then the rest of its own time waited out on the video line (a
  table by kind, shift and class of y, made by the build from runs of the routine itself).
- The CALL of the play goes to a second hook: the staged figures' sprites switched on in the order they were drawn
  (a later sprite is in front), every other sprite off, the two pattern sets change over; then the play as the
  original runs it. A pass that draws nothing switches every sprite off.
- The CALLs of the fade (0x8646, 0x815C, 0x9950) and of the scene (0x8101, 0x81DD) go to the same hook with the
  pass's figures dropped: every sprite off, and the figures the game drew fade or go black with the screen as in
  the original. They come back at the next play.
- The play's hook has no time of its own to hide in: its cost (35 sixteenths of a line and 4 a sprite) is owed and
  given back in the figures' windows that follow.
- Plain tiles are made once a picture and kept in a tile cache (8 pages from page 40: an index of 256 entries by
  graphic and mask, then the tiles); after that they are sent with OTIR. With the cache full, or no index entry free
  near a picture's, the tiles are made each time (unit case).
- A set's patterns that already hold the picture a figure wants (the same picture two passes on) get nothing sent.
- The hooks hold the three kinds the game draws: 16 rows of 2 bytes, 24 rows of 3 bytes, the same with a mask. Any
  other size, a mask asked for and not used (A even and not 0), y of 176 or more, no room in the stage (12 figures)
  or the set (64 patterns): the figure is left as the game draws it and the routine runs as the original. Counted;
  none in the recording.
- The sprites' window is the whole display (Olli's box reaches a line into the panel at the bottom of a room).
- Code in the alt ROM from 0x2800; the state page at slot 0 inside a hook, a cache or painted page at slot 2 while
  tiles are made or sent. The setup runs in the stub's own bank and puts the printer buffer back after NEXLOAD; the
  start-up tail is at 0x5C00 (0x5B00-0x6A20 is never touched).
- Every register and flag passes through the hooks; nothing is written below the game's stack (the first version
  saved AF there: the verifier's memory comparison found it).
- DMA / DDMA (docs/DDMA.md): not used. A hook sends at most 512 pattern bytes with OTIR from ready tiles (21 T a
  byte at 28 MHz, under 3 T at the game's clock) inside a window of 10,000 T or more that already holds it, and the
  DDMA blitter does not write the pattern port.

## Enhanced (2026-11-20, first pass)
- Sheet: every figure the recording draws (70 by their bytes: Olli's 22 poses in their masks' boxes, with his
  sparks, his fading and his tumbling; 6 rings and bursts of sparkles; 42 creature and effect pictures, lit pixels
  only), painted by a Codex pass from a brief (Olli green as in the first and third game's paintings, in a blue hat
  and robe; the creatures in their own colours; 3 palette lines); files in the owner's painting folder
  (`nexclash-olli2`), `sheet2colours.py` makes `olli_and_lissa_2_colours.json`, kept beside the snapshot: it
  holds the figures, so it is not in this repository.
- Two star bursts are the third game's pictures and take its colours.
- In the build: a figure is known by its graphic's address and size (the build checks the bytes there against the
  painted map's key; no picture's bytes change in the recording); the state page holds an index of 8 bytes a
  figure, pages from 28 hold its tiles as the sprites take them, with its palette line.
- A figure the map does not know is drawn in the plain colours (through the tile cache).

## Hardware checklist
Starts from the menu; the title and its fade as the original; Olli and the creatures visible, moving in step with
the room, with no trail and no flash; nothing left behind after a room change, a lost life or the end of the game;
the panel untouched; sound unchanged; the game's speed as the original's over a minute of play. Enhanced: the same
with the painted colours.

## Open
1. The painting is a first pass the owner has not seen in play.
2. Where the painted map lives for a public patch (it holds the figures; the .nxc carries the painted tiles).
3. Pace is from the simulator's line clock; no JNext or hardware timing.
4. The creatures have no mask in the game, so no black edge: a white creature on a white part of a room does not
   stand out. The pick-ups keep their Spectrum colours (they do not move).
5. During a fade the figures fade with the room as the game draws them (the sprites are off); they are white or
   painted again at the first play of the new room.

## Decisions
- 2026-11-20 (owner, for the first and the third game: "White plus painted (Recommended)"; this game follows them):
  moving figures as sprites in bright white with a black edge where the game has a mask, an Enhanced option painted
  in a first pass for review; rooms, pick-ups and the panel as the game draws them.
- 2026-11-20: the figures stay in the bitmap under their sprites (as the first and the third game): nothing of the
  game changes.

## Lessons
- [kb lesson.hook-stack-below-sp: this game's hooks] A hook that saves AF on the game's stack before switching to its own writes two bytes
  below the game's SP: the comparison of all game memory found it in the first run. HLIB_R_IN goes after the stack
  switch.
- [kb lesson.exact-silhouette-from-plotter-run: this game's analysis] The routine run on an empty and on a full copy of the screen gave the layout at
  once, and showed that an unmasked figure starts a line higher than a masked graphic (the OR loop starts at the
  mask's first row).
- [local: this game's verifier] A CALL before a routine that waits for keys (the title) cannot be compared at the
  routine's end from a copy of the state: the hook is compared where the routine starts.
- [kb lesson.fades-need-sprites-off: this game's design] A fade to black and a scene on a black screen need the sprites off for their length:
  the figures the game drew fade or go black with the attributes, and a sprite would not.

## Friction
- reuse: [local: this game's module] the third game's module and hooks, turned into this game's by two scripts
  (sites, figure layouts, the time table's keys, the fades); about a third of the lines are new.
- retries: [local: this game's hooks] R's two constants and the debt for a draw (97 ran 0.17% fast, 91 holds) from
  the first two short runs.
- hand-rolled: [local: private run folder] adds.py (draws and plays), tt.py (the routine's time), geo.py (the model
  against the routine), shots.py (what the Next shows, from the verifier's state).
- environment: [kb lesson.long-job-background-no-limit: this machine] a background command given a time limit is stopped at the limit: the long
  check runs with none.
- scratch: [local: private run folder] NOTES.md and tools/.

## Technique use
- patch.xor-overlay-keep-ula: helped: the whole design; the game's memory compared equal once the hooks kept off
  the game's stack.
- patch.display-atomic-switch: helped: two pattern sets changed over at the game's own play.
- patch.pace-limiter: helped: windows on the figures, the debt for the play's hook.
- patch.runtime-colour-map: helped: painted tiles keyed by the graphic's address; the tile cache is the same idea
  filled at run time.
- patch.preserve-r: helped: the game reads R; the constants came from the verifier's first comparison.
- patch.restore-speed: used.
- patch.whole-altrom-image: used: the game runs no ROM code.

## Stage log
- 2026-11-20: stages 0-3 in one session (the archive's recording; a third engine read and modelled; the third
  game's module and hooks adapted; a Codex painting pass; the patch run in OverSpec), about 5 h (one full check of
  about 3 h in the background), about 90 tool calls, 1 user round (the request; the design follows the owner's
  answers for the first and third game).
