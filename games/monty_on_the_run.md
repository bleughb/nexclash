# Monty on the Run (Gremlin Graphics, 1985) - new engine

Techniques: `detect.gameplay-screen-readers`, `patch.xor-overlay-keep-ula`, `patch.whole-altrom-image`, `patch.restore-speed`

## Next session
Stage 3 (prove + deliver) done 2026-11-22; Stage 4 (hardware + colour rounds) next. First release = clash fix
(figures as sprites, the attribute painter skipped for them) + checked cheats. Inputs (local, not in the repo):
rzxarchive montyontherun.rzx (61,198 frames, 20 min); the record's snapshot is TOSEC "Monty on the Run
(1985)(Gremlin Graphics Software).z80" (48K, same code). Record docs/records/monty_on_the_run.json, verified and
stamped (sprite build 7fdb25d9). Open: reference files to specnext; republish the nxc patch (hook bytes changed by
the speed fix) after the owner's quick test; owner play.

## Observed engine (static reading, motr_start.z80)
- Enemy figures: 46207 (0xB47F) draws up to 4 slots. New positions at 46963 (x, y per slot), old at 46971, records at
  46987 (8 bytes each; IX+4 = the figure's colour). Graphics: two buffers whose pointers (47019 / 47021) swap each
  frame; 46325 (0xB4F5) XORs the previous image at the old position and the current one at the new, 16 rows x 3
  bytes, merging rows where they overlap (0xB503 / 0xB550 / 0xB566). Row address helper 47027 (0xB7B3), from B (y)
  and C (column).
- Attribute painter 46491 (0xB59B), called first for each figure: paints a 3-cell-wide block with IX+4 on cells whose
  background map entry (34752 + cell) is 0, rows 4..21 only. This is the clash: coloured blocks behind every figure.
- Other XOR plotters: 0xEFE4 (61412.., 1 + 7 + 1 rows, IX and DE streams: probably Monty), 0xE68D (59021.., 6 rows:
  small objects / shots). 61081 (0xEE99) ANDs scenery away 8 rows at a time (crumbling), a write, not a test.
  62690 (0xF4E2) cycles an attribute's ink (AND 7). No routine reads screen pixels for collisions (survey readers:
  all are the plotters' own read-modify-write).
- Room drawing: 0xE319 (from 0xE2A6, 40 calls, whole screen), 0xE38E (tiles, attrs + pixels), 0xF6F1 (from 0xF6DC).

## Design (built 2026-11-21, standing default: figures as sprites in the game's own colours, colour paint off)
- Overlay: every pixel write stays; two 16 x 16 4-bit sprites per figure cover its 24-pixel pre-shifted image.
  Enemies 0-3 = sprites 2i / 2i + 1 in their own ink (record +4: ink + 8 x BRIGHT); Monty = sprites 8 / 9, BRIGHT
  white (he has no colour of his own: he took each cell's). Rows outside 16..175 are blank, as the game clips them;
  Monty at column 30 / 31 is hidden (his row helper 59065 refuses those columns, nothing is drawn).
- Sites: 46313 enemy hook (after the XORs; the buffer pointers have just swapped, so the current images are at
  (47021)); 63169 Monty hook (after his XOR); 57984 room set-up and 37386 new game hide all; the attribute
  painter's three LD (DE),A (46542 / 46552 / 46562) become NOPs.
- Pace: about 1.9% (hook T over the first 3,000 frames: enemy hook ~37.8k, Monty ~12.6k T at 28 MHz; they run on
  about one frame in 4.75). The pixel conversion is a 16-entry nibble table, inline.

## Verification (nexclash/monty_on_the_run.py)
- Events at every hook and at every painter call (CALL 46491 -> 46328): original and patched code from the same
  state, all registers but R, all memory but the dead stack; the patched painter must write no attribute.
- Figure truth: each figure's XOR layer from its plotter's writes; other screen writes classified by instruction
  (LD (HL)/(DE)/(BC),A after XOR or AND (HL)/(IX+d): another XOR plot leaves figures' pixels, the crumbling AND keeps
  what it keeps, anything else replaces the byte). Sprites against layers after every enemy / Monty hook; all ten
  hidden after a room set-up or new game. A figure is unchecked from a segment start, or after the lift block (0x9D44
  slides a 4 x 72 column up a row a frame, figures' pixels with it) touches it, to the next room set-up.
- Known differences: where the lift block slides an enemy, the original then XORs its old image where it no longer
  is (scrambled pixels); the sprite shows the enemy. Where another figure's XOR overlaps, the sprite is in front.

## Results
- Whole recording, 61,198 frames: IDENTICAL. 28,680 enemy draws, 28,425 Monty draws, 157 rooms, 57,105 figure
  checks, 13.7M sprite pixels; 32,790 attribute bytes not painted. Units: Monty 200, enemy 200, menu, new game and
  room hooks 8 each, at the four CPU speeds; negative controls 10 of 10 (incl. a hook left at 28 MHz).
- Tang board (hov2-p1r2, automap on, leftover sprites): loads, reaches the menu.

## Lessons
- [local: the card already covers it] every hook left NR 7 at 3.5 MHz; HK_IN keeps the caller's speed on the stack
  (card patch.restore-speed), the verifier fails an event that leaves another speed.
- [local: negative controls] auto now runs the unit cases and every negative control, and fails a desynchronised
  replay or a run with no figure coverage.

## Friction
- reuse: [local: Finders Keepers' engine shape (hooks, events, truth layers, units, negatives) followed]
- retries: [local: the review's speed finding needed a hook and verifier change; re-verified on the whole recording]
- environment: [local: reference files staged from the scratchpad; not yet in specnext]
- hand-rolled: [none: the record was written with the records module's checks and selftest]
- scratch: [none: the staging script stays in the session's scratchpad]

## Technique use
- detect.gameplay-screen-readers: helped: the survey showed no collision reads of screen pixels.
- patch.xor-overlay-keep-ula: used: both XOR plotters kept, two sprites per figure.
- patch.whole-altrom-image: used: hooks at 0x386E in the 48K ROM image.
- patch.restore-speed: used: the caller's NR 7 kept and put back.
