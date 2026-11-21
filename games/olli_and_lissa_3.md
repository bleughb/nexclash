# Olli and Lissa III: The Candlelight Adventure (Codemasters, 1989; 48K)

## Next session
Stage: 3 (verified, stamped, published as an .nxc for the tape)   State: 2026-11-20: every moving figure a sprite on
its own pixels, white with a black edge where the game has a mask, and an Enhanced set painted in a first pass; both
builds verify on two whole machine-played recordings (7 rooms); boots to the title in OverSpec; not on hardware
Inputs (private, pilot runs/olli_and_lissa_3/reference_files/olli_and_lissa_3): olli_and_lissa_3.z80 (TOSEC, at the
title menu), olli3_car1.rzx + olli3_car2.rzx (machine-played, see "Recordings"), olli_and_lissa_3_colours.json (the
painted map); the Codemasters tape (.tap) is in the run folder
Branch: add-olli-and-lissa-3    Commit: this one    Checks: selftest --game olli_and_lissa_3 --verify --stamp, doccheck
Pending user answers: "Open" 1-3
Start with: a recording played by hand through later rooms ("Open" 1), then the owner's review of the painting
Read: "Build", "Recordings", "Open"

## Result (2026-11-20)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.display-atomic-switch`, `patch.pace-limiter`,
`patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

Two whole machine-played recordings (20,210 and 20,168 frames, 7 rooms), both builds.

| | |
|---|---|
| Builds | olli_and_lissa_3_sprites.nex 4eeda9b6 (white, Olli with a black edge), olli_and_lissa_3_enhanced.nex c7056f6d (painted), plain db9e1215 |
| Verify | IDENTICAL on both recordings, both builds: 81,604 adds and 27,012 plays; every register with R and all game memory after each; after a play the sprites against a model of the adder for the pass's figures (56,199 figures, 15,058,713 sprite pixels) and the model against the pixels the original's player has just drawn (none off) |
| Painted | every figure drawn is in the painted map (56,199 of 56,199) |
| Most at a time | 4 figures, 10 sprites; none left to the game |
| Pace | the hooks within -0.031% to +0.033% of the original's adds and plays over a recording; in any 10 seconds the game loses at most 107,309 T (1.5 frames) and gains at most 108,409 T: a new picture's tiles are made once and the time is made up over the next seconds |
| Unit | PASS: 17 cases (a masked figure, the next pass's pattern set, a play with nothing added, a mask with no graphic or away from it, the right edge, a figure with no mask, more rows than the table, the adder's flags, above the top of the screen, the stage full, the pattern set full, the tile cache full, each JP site, two figures over each other) |
| Negative | 9 broken builds, all detected |
| Boot | simulated, with and without NEXLOAD's printer buffer: registers and RAM as the snapshot |
| ROM paths | pass: the game runs no ROM code |
| OverSpec | the build boots to the game's title; play not driven there |

## Recordings
- The rzxarchive lists a recording of this game and denies its distribution. The two here are machine-played from the
  TOSEC snapshot: the toolkit's recorder (48K, Kempston) driven by a small explorer that, from the current state,
  tries six bursts of input, keeps the one that reaches a new room or else runs the most new code, and plays on: one
  unbroken recording, no state reloaded (the explorer is in the pilot run folder).
- The start is scripted: 3 (Kempston), ENTER, the car (1 or 2), the colour (1 or 4). olli3_car1.rzx: 20,210 frames;
  olli3_car2.rzx: 20,168 frames. Seven rooms each, Olli walking, climbing, dazed, with his bubbles, about 40
  creature pictures. Later rooms, their creatures and the car in play are not reached.
- The recorder's own automatic recordings (several parts, each from a reloaded state) lose sync in the replay for
  this game at the first part's end; a single part does not.

## Feasibility (PLAYBOOK 3d, 2026-11-20)
- 48K. Interrupts are off in every frame of the recordings (IM 2 with I = 0x3F in the snapshot, never enabled):
  nothing syncs the game to the frame, so the time a hook takes is game speed.
- The game runs no ROM code.
- Each pass of the main loop (0x8057 to 0x8085) the game ADDS every moving figure to a list of draw jobs and then
  PLAYS the list. The adder, 0x86B8: HL = the picture, D = y (the picture's first line is 175 - y), E = x, B = rows,
  C = bytes a row (2, 3 or 4; bits 7 and 6 are flags for pictures taken as they are, never set in the recordings).
  It shifts the picture into a buffer and writes a job of 10 bytes (line, column, rows, bytes, kind, pointers).
  With 3 bytes a row it puts an empty row above and below; a row's bytes are stored byte 0, byte 2, byte 1 (2 bytes:
  byte 1, byte 0). With 4 bytes the picture is a mask (1 = kept), shifted right with ones.
- The player, 0x8863: sorts the jobs' lines and works down the screen band by band: last pass's figures put back
  (the background each graphic's OR saved), masks ANDed, graphics ORed and the background under them saved. A figure
  the game does not add again is gone after the next play. Jobs run in the order they were added: a later figure is
  in front.
- Five sites of the adder: 0x866C Olli's graphic (24, 32 or 40 rows of 3 bytes), 0x8672 his mask (two rows more, 4
  bytes, the same y and x: it starts a row above and a pixel left of the graphic), and three JPs for everything
  else, with no mask: 0x86A6 (2 rows of 3 bytes: dust at his feet), 0xA2A4 and 0xA50C (the creatures, 16 rows of 2
  bytes). At most 5 adds a pass in the recordings, 4 figures.
- Twelve CALLs of the player: 0x8082 in the loop; the others draw rooms and scenes with jobs of their own (no figure).
- The adder's own time depends on bytes a row, rows and the shift (x AND 7) and nothing else below the top of the
  screen: 2,100 T (16 rows of 2 bytes) to 12,800 T (40 rows of 3). The player's time depends on the whole list
  (44,000 T with Olli and two creatures).
- Other writers of the screen in play: the room builder and block copies through the same list (pick-ups, text):
  they do not move. Left as they are.

## Build (stage 2, 2026-11-20; asm/olli_and_lissa_3_hooks.asm, nexclash/olli_and_lissa_3.py)
The game's memory and screen stay the original's; sprites lie on the figures' own pixels.
- The adder's five sites go to one hook: 28 MHz; the figure's tiles (4-bit patterns: 1 where the graphic is set, 2
  where the mask clears, or its painted tiles) are sent into the pattern set no sprite shows and the figure is staged
  (place, sprites, patterns); then the game's adder; then the rest of its own time waited out on the video line (a
  table by bytes, rows and shift, made by the build from a run of the adder itself). Olli's graphic is only kept at
  its own CALL; his figure is made at his mask's.
- The player's twelve CALLs go to a second hook: the staged figures' sprites switched on in the order they were
  added (a later sprite is in front, as the game's jobs), every other sprite off, the two pattern sets change over;
  then the player as the original runs it. A pass that adds nothing switches every sprite off: a room change needs
  no hook of its own.
- The player's hook has no time of its own to hide in: its cost (35 sixteenths of a line and 4 a sprite) is owed and
  given back in the adds' windows that follow.
- Plain tiles are made once a picture and kept in a tile cache (8 pages from page 40: an index of 256 entries by
  graphic and mask, then the tiles); after that they are sent with OTIR. Made every time they cost more than the
  adds' windows hold (Olli changes picture nearly every pass: the game ran 1% slow). With the cache full, or no
  index entry free near a picture's, the tiles are made each time (unit case).
- A set's patterns that already hold the picture a figure wants (the same picture two passes on) get nothing sent.
- A figure the hooks do not hold is left as the game draws it and the adder runs as the original: more than 50
  rows, the adder's flags in the width, a place above the top of the screen (the adder cuts it), a mask with no
  graphic kept or at another place, no room in the stage (12 figures) or the set (64 patterns). Counted; none in the
  recordings.
- The sprites' window ends at line 175, above the panel.
- Code in the alt ROM from 0x2800; the state page at slot 0 inside a hook, a cache or painted page at slot 2 while
  tiles are made or sent. The setup puts the printer buffer back after NEXLOAD.
- DMA / DDMA (docs/DDMA.md): not used. A hook sends at most 768 pattern bytes with OTIR from ready tiles (21 T a
  byte at 28 MHz, under 3 T at the game's clock); a DMA transfer would save about 1,000 T of an Olli add whose window is
  5,000 T and already holds it, and the DDMA blitter does not write the pattern port.

## Enhanced (2026-11-20, first pass; owner: "White plus painted")
- Sheet: every figure the two recordings draw (66: Olli's 28 poses in their masks' boxes, with his stars and his
  bubbles; the dust; 36 creature and effect pictures, lit pixels only), painted by a Codex pass from a brief (Olli
  green as in the first game's painting, orange feet, a gold shell; the creatures in their own colours; 2 palette
  lines); files in the owner's painting folder (`nexclash-olli3`), `sheet2colours.py` makes
  `olli_and_lissa_3_colours.json`, kept beside the snapshot: it holds the figures, so it is not in this repository.
- In the build: a figure is known by its graphic's address and size (the build checks the bytes there against the
  painted map's key; all 66 figures' bytes are constant over both recordings); the state page holds an index of 8
  bytes a figure, pages from 28 hold its tiles as the sprites take them, with its palette line.
- A figure the map does not know is drawn in the plain colours (through the tile cache).

## Hardware checklist
Starts from the menu; the title, the car and colour choice as the original; Olli and the creatures visible, moving in
step with the room, with no trail and no flash; nothing left behind after a room change or a lost life; the panel
untouched; sound unchanged; the game's speed as the original's over a minute of play. Enhanced: the same with the
painted colours.

## Open
1. The recordings are machine-played and reach 7 rooms: later rooms, their creatures and the car in play are proven
   only by the hooks' rules (anything they do not hold is left as the game draws it). Owner 2026-11-20: publish on
   these; a recording played by hand can be added.
2. The painting is a first pass the owner has not seen in play.
3. Where the painted map lives for a public patch (it holds the figures; the .nxc carries the painted tiles).
4. Pace is from the simulator's line clock; no JNext or hardware timing.
5. OverSpec: the build boots to the game's title; play was not driven there (see "Friction").
6. The creatures have no mask in the game, so no black edge: a white creature on a white part of a room does not
   stand out. The pick-ups keep their Spectrum colours (they do not move).

## Decisions
- 2026-11-20 (owner, stage 1): "White plus painted (Recommended)": moving figures as sprites in bright white with a
  black edge, an Enhanced option painted in a first pass for review; rooms, pick-ups and the panel as the game draws
  them.
- 2026-11-20 (owner): "Publish on mine (Recommended)": verify and publish on the two machine-played recordings and
  say plainly that later rooms are unproven.
- 2026-11-20: the figures stay in the bitmap under their sprites (as the first game): nothing of the game changes.

## Lessons
- [local: this game's hooks] Building 4-bit patterns from the game's bytes at run time (two table lookups a byte)
  cost 113 T a byte at 28 MHz: more than the displaced routine's time when the player's picture changes every pass.
  Made once and kept in spare pages, then OTIR: the hooks fit and the pace came out within 0.07%.
- [local: this game's hooks] A list the game fills and then plays gives the display switch for nothing: stage at the
  add, switch on at the play, and a pass that adds nothing clears the sprites. No hook at room changes, no stale
  sprite to look for (the first game needed both).
- [local: this game's verifier] A hook with no window of its own (the player's) makes single calls run long and the
  next windows short: a per-call limit fails though the game keeps time. The check is the recording's whole drift
  and the largest excursion beside it.
- [local: this game's verifier] The first pace check counted a steady drift of 0.07% as "13 frames ahead": steady
  drift and bursts are two numbers.
- [local: this game's analysis] The game's own routines run on an empty and a full screen gave the layout (byte order
  in a row, the empty rows, the mask's corner) at the first try: the model matched at every shift.
- [backlog C2 #15] The toolkit's recorder writes its automatic recordings in parts from reloaded states; for this
  game the replay loses sync at the first part's end, and the parts cannot be joined (each starts from another
  state). An explorer that plays on from the current state gives one part that replays.

## Friction
- reuse: [local: this game's module] the first Olli and Lissa module's shape (model, verifier, unit cases, the
  painting tools); the hooks are new (another developer's engine).
- retries: [local: this game's hooks] three versions of the picture upload (made each time; a per-set memory of
  what the patterns hold; the tile cache) before the pace held.
- hand-rolled: [local: private run folder] explore.py (the unbroken explorer), shots.py (what the Next shows, from
  the verifier's state), adds.py, cap.py, exp.py.
- environment: [local: this machine] OverSpec's scripted keys reach it only while its window has the focus; with the
  owner's desktop in use neither the patch menu nor the game took a key (the first game's known-good patch the
  same), so play was shown from the verifier's state instead.
- scratch: [local: private run folder] NOTES.md and tools/.

## Technique use
- patch.xor-overlay-keep-ula: helped: the whole design; the game's memory compared equal from the first run.
- patch.display-atomic-switch: helped: two pattern sets changed over at the game's own play.
- patch.pace-limiter: helped: windows on the adds, the debt for the player's hook.
- patch.runtime-colour-map: helped: painted tiles keyed by the graphic's address; the tile cache is the same idea
  filled at run time.
- patch.preserve-r: used.
- patch.restore-speed: used.
- patch.whole-altrom-image: used: the game runs no ROM code.

## Stage log
- 2026-11-20: stages 0-3 in one session (no recording to be had: a machine-played one; the list engine read and
  modelled; hooks, verifier, a Codex painting pass, the patch), about 6 h (two full checks of about 1 h), about 110 tool calls, 3 user rounds
  (the request, the two stage-1 questions).
