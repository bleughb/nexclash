# Match Day (Ocean, 1985; Jon Ritman / Chris Clarke) - engine `matchday` (phase A)

48K. Code: nexclash/matchday.py (phase A: facts, shadow model, colour-sheet capture, preview).
Reference (specnext/reference/match_day/): Match_Day_1985_Ocean.z80 + Match_Day_1985_Ocean.rzx
(Dean, 2026-10-20; 6210 frames, 124 s: title, menu, walk-on scene, the first ~6 match minutes with
a goal and a keeper dive) + Match_Day_spectrumcomputing.rzx (50403 frames, 1008 s; from
spectrumcomputing.co.uk entry 3067, supplied by Dean 2026-10-20; its own start snapshot: code
identical at every plotter / line writer, 13 bytes of game state differ). Manual: gamesdatabase.org scan (image only, no text layer).

    python -m nexclash.matchday sheet   Match_Day_1985_Ocean.z80 Match_Day_1985_Ocean.rzx Match_Day_spectrumcomputing.rzx -o match_day
    python -m nexclash.matchday preview Match_Day_1985_Ocean.z80 Match_Day_1985_Ocean.rzx --at 2200,3760,5400,6100

## Status
Phase A done and agreed (2026-10-20 16:43). Phase B (build) in progress.

## Snapshot (0b)
- 48K, PC 0x0038 (in the ROM IM 1 handler), DI, IM 1, I=0x3F, SP 0xBDBC, border 0. Title/menu.
- In game: IM 2, I=0x3B, vector 0x3BFF -> 0xFFFF (x4729 in the RZX); menus run IM 1 (x1231).
- ISR (`isr`): reads the interrupted IY (ROM keyboard scan: LD C,(IY+7) at 764...), uses AF'
  (35320, 35352, 45917), <= 24 bytes of stack, OUT (254) only. Slots never touched: 3, 6.
- Plain conversion: tail 0xBD5C (converter default, checked safe).
- RZX: one segment; SZX snapshot with a ZXPR block (skoolkit warns "unsupported", harmless).

## Game facts (from the code + the RZX)
- Every figure is drawn by XOR straight to the screen; each draw erases the old image and draws
  the new one in ONE pass (old XOR new per byte; separate old / new loops when the address moved).
- Players: 0x8B45, IX = object record (27 bytes). 16 pitch objects at 0xB4FC + 27k (k = 0..15),
  the spare 0xB6AC (the keeper's second half while diving, also walk-on scene). Callers 0x821F loop
  (return 0x8223), 0x8250 loop (0x825A), 0x826D (single). The depth sort SWAPS whole records, so a
  figure changes IX between frames: identify a figure by its buffer pair (IX+0x14..0x17).
  - Fields: +0 flags (bit 0 = upper-body variant, bit 5 = which buffer, bit 6 = bottom-edge
    path), +3 frame, +5 x, +7 y, +8/9 new screen address, +0x0E STRIP colour, +0x0F SOCKS colour,
    +0x10 upper-body frame, +0x14/+0x16 the two image buffers (3 bytes x rows).
  - 0x8DEC builds an image: HL = graphics, B = rows/2 (TWO rows per iteration), A&6 = shift
    (0 / 2 / 4 / 6 px: 0x8E04, 0x8E9B, 0x8E1C+0x8E30 RLD, 0x8E57 stack). 28-row frames at
    0xC460 + 56n (n = 0..119; 72.. = the keeper's dive, left half 2k / right half 2k+1, 16 px apart);
    the 0x8CDA path: the frame's lower 14 rows + an 18-row upper body at 0xDDC0 + 36u (u = 0..17:
    arms up, headers, throw-ins), upper body first in the buffer.
  - 0x8ECE dispatches on ($93AC) (old + new row counts) to the XOR loops 0x8EF0-0x9165 (unrolled,
    clipped at the screen edges); the draw runs from the buffer's end = bottom row, upwards.
  - Cell paints 0x9168-0x9348 (writers 0x934E / 0x9369 / 0x937D): old cells back to the pitch ink
    ($93A5), new cells: bottom 1-2 cell rows (BIT 2 of y) IX+0x0F, 3 rows above IX+0x0E.
  - Socks indicator (Dean, 2026-10-20: "the player is indicated on-screen by his socks turning the
    colour of the rest of his strip"): 0x82BD-0x82CD writes the controlled players' IX+0x0F
    from $897F / $8981.
- Ball: 0x9FCF: shadow (B=1) then ball (5 rows) through 0xA046 (XOR old + new, 2 bytes a row);
  graphics 0xA111 + 14 * (x & 7) (pre-shifted); off screen = address 0x2000 (a ROM write).
- Scenery writers, all stay on the ULA: XOR line / block writers (pitch lines, boxes, goals, net):
  0x5F2A / 0x5F2E, 0x62D3 / 0x62DB, 0xE73B-0xEBED, 0xEC50-0xECB1, 0xEF3F-0xEF74, 0xF049-0xF0BA, 0xF198-0xF1C9; overwriters: screen
  clears 0x87DF / 0xEFAD, crowd copier 0x9936-0x9987 + 0x99DF attrs, the walk-on scene's 2x plotter
  0x95A6 (overwrites), text 0x5F2B.., 0x6136.., HUD.
- Pixel readers (an2 pass over BOTH recordings, 56k frames): every read of a figure byte is a writer
  reading the byte it rewrites (XOR writers, overwriters, the crowd LDI once); no collision or logic
  reads the screen -> no virtual reads needed.
- Shadow model (matchday.Capture): figure XOR writes into a 1-bit shadow, overwriters clear the
  shadow at the bytes they write; ULA XOR shadow = scenery only, checked by eye on 5 frames
  (preview) and by the per-figure footprints (XOR of the footprints == the shadow).
- Overwriters on figure bytes in the RZX: 0x9973 crowd copier x4 (a figure at the top edge), 0xEFB3
  screen clear x145 (end of the match part): both handled by the overwriter rule.
- Menus: "Main Menu", "Change Match Details" (length, difficulty, players, computer opponent,
  Colours: strip colours, border), "Change Team Names", pause key, "FINAL SCORE", "Kick Off",
  "Start Second Half", "Begin Extra Time", "MATCH TO BE DECIDED BY REPLAY" (strings at 0x5Fxx-0x7Exx).
  Team colours come from the menu at run time -> sprites must take IX+0x0E / IX+0x0F live.

## Coverage (sheet, both recordings)
- Frames drawn 0-115 (of 120), upper bodies 0-17 (all), ball all 8 shifts. Frames 116-119 (one dive
  pair look-alike + two halves) only "From the code" (2 figures). Dive halves are joined on the
  sheet only as matching pairs (2k left + 2k+1 right): the alternate-frame lag mixes steps.

## Dean's decisions (2026-10-20)
- Players SOLID: the see-through pixels (paper enclosed by the figure, `matchday.enclosed`) in the
  PITCH GREEN, opaque (14:08; replaces "opposite team's colours" 14:01 and "black" 14:05): the
  lines behind a player no longer show through. Preview: match_day_PREVIEW_solid.png.
- Bottom edge: as the original (figures drawn over the score line, no clipping).
- Keeper dive "torn in half" (Dean, from the preview): the ORIGINAL tears the same way - the keeper
  and the spare object 0xB6AC are drawn on alternate frames, so while the camera scrolls one half
  lags one update (~4 px; RZX frame 3760: halves 12 px apart instead of 8 by ink, frames 92/93 fit
  exactly 16 px apart). Fix (Dean 14:08: "still has a tear" = fix it): the spare half's sprite is
  shifted by (camera x at its draw - camera x at the keeper half's draw) (camera = 0xE60B), so
  both halves sit where they would at the same camera position; the shadow model and the logic
  unchanged. Preview: match_day_PREVIEW_dive.png (top original, bottom planned, frames 3746-3790).
- No further recording of his own (14:08); then supplied the spectrumcomputing.co.uk RZX (14:13),
  which covers all but frames 116-119 (unit tests for those).
- Sheet: Dean paints it later; build with the defaults (roles) until then, recolour afterwards.

## Phase A proposal - AGREED by Dean 2026-10-20 16:43 ("1-3, i agree"; no messages over the pitch)
- Sprites: every player (both teams, keepers, the dive joined), ball, ball shadow. ULA: pitch,
  lines, goals, crowd, clock, score, menus, the walk-on scene (2x overwriting plotter, no clash
  problem on a still screen).
- Colours by ROLE: sheet swatch 1 (orange) = the object's STRIP colour (IX+0x0E), swatch 2 (lilac)
  = its SOCKS colour (IX+0x0F), both from the game at run time (menu colours and the socks
  indicator keep working), swatches 3-15 fixed colours. Default: the bottom 8 rows SOCKS, the rest
  STRIP; ball / shadow white. Paper bits are paintable (outline / filled gaps).
- Depth: lower on the screen (nearer) in front; ball by its ground (shadow) position; shadow under
  every player.

## Open (ask, do not decide)
(none from phase A; Dean found no message window over the pitch either)

## Hardware checklist
(none yet)
