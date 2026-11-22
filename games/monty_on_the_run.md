# Monty on the Run (Gremlin Graphics, 1985) - new engine

## Next session
Stage 1 (design) in progress, 2026-11-21 night. Jon asked for the Monty Mole series after the overnight list; first
release = clash fix (figures as sprites, the attribute painter skipped for them) + checked cheats. Inputs (local, not
in the repo): rzxarchive montyontherun.rzx (61,198 frames, 20 min), its snapshot extracted as motr_start.z80 (48K,
PC 0xAAC5, IM 1, DI). Survey: 803dad54 scratchpad motr/survey/ (first 15,000 frames; GATE OK).

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

## Plan
Sprites for the figures each plotter draws, the attribute painter skipped for those cells, the XOR plots kept off the
ULA (no screen reads depend on them). Template: the Finders Keepers engine (wt-finders_keepers: e_pt / e_rm / e_cl
hooks, verifier with per-hook events, figure truth layers, unit tests, negatives).
