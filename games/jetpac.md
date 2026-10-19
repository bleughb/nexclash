# Jetpac (Ultimate Play The Game, 1983) - engine `jetpac` (phase A)

48K (16K game). Reference: specnext reference/jetpac/Jetpac_1983_Ultimate_Play_The_Game_a_16K.z80
(BASIC loader state: PC 29026 in game code, menu not yet shown; Dean, 2026-10-19).
NO RECORDING this time (Dean, 2026-10-19: "no rzx this time"). `auto` makes a synthetic
_auto.rzx, but it runs out of port readings at frame 532 under `scan` (desync): analysis below
used it to frame 530 and free runs (`--frames N --keys K`). Differential verification against a
real recording is OPEN until one exists.

## Snapshot (inspect)
- IM 1, DI at snapshot, I = 0x3F, SP 0x5CE6, RAMTOP 24575; game code 0x6000-0x7FFF.
- Menu: 1/2 players, 3 keyboard, 4 Kempston, 5 start. Free-run start keys: `10-12:1;20-22:3;30-32:5`.
- ISR = ROM 0x0038 (reads IY: keep IY = 0x5C3A); slots 1, 3-7 never touched by the handler.
- `auto`: engine unknown; plain .nex builds (tail 0x5B00, checked safe).

## Rendering model (one plotter for every moving figure)
- Move-and-redraw at 30522 (0x773A): per object, erase the OLD frame with CPL/AND (30529-30532)
  and draw the NEW one with OR (30559-30561), line by line, wrapping within the 32-byte row;
  29422 = next pixel line up. Old frame from (24000-24006), new from IX (+0 type/dir/flags,
  +1 x, +2 y). Entries: 29290 (move), 29278, 29339/29344/29349/29365 (draw / erase only).
- Graphic: [y offset, W bytes, H lines, W*H bytes], rows stored BOTTOM line first (the plotter
  steps up a line, 29422; first sheets were upside down - Dean, 2026-10-19). Pre-shifted: 4 shifts by x&6, direction =
  bit 6 of (IX+0); table 30458 word index (type-1)*8 + dir*4 + (x&6)/2:
  type 1 Jetman walking, type 2 Jetman flying (ROM data 30614-31640), type 3/4 = RAM buffers
  24064-24470 (aliens, explosion).
- Aliens: built per level into 24064/24166 by 26921 from table 26949 [(24048) & 7] (8 types;
  calling 26921 with 24048 = L builds level L's aliens - used for the colour sheet).
- Rockets, fuel, items: graphic pointer from table 26563 (+(IX+6)): words 0-11 = 4 rockets x 3
  parts (rocket r = words r, r+4, r+8; r+8 = nose, r = base), 12-15 fuel pod, 16-20 five bonus items.
- Plot callers (code): 25685, 25778, 25823, 25925, 25940, 25950, 26052, 26255, 26261, 26265,
  26299, 26305, 26403, 26446, 26846, 26871, 28037, 28146, 29895. Seen in free runs: 28149
  aliens, 29898 Jetman, 26449/25943/25928 rocket parts, 26849/26874 explosion.
- Other screen writers (scan, frames 0-530): 29023, 29119 (clear), 29171, 29060, 25038, 28829,
  28708/28717 - lasers, platforms, HUD/text: not classified yet.

## Dean's decisions (2026-10-19)
- Split APPROVED: Jetman, aliens, rocket parts, fuel pod, bonus items, explosions -> sprites;
  lasers, platforms, HUD, text -> ULA. Sprites in front of the ULA.
- Colours: the game's own (the ULA ink each figure gets in play: Jetman/rockets white, aliens
  their per-object attribute colour, etc.) - no painted sheet; the colours json is generated
  from the game's attributes. Sheets regenerated in those colours before delivery.

## Colours (game's own; measured at 29160 = LD D,(IX+3), the attr 29135 paints after each draw)
- Jetman 71 (bright white), rocket parts 71 (filled: 67 bright magenta, 26524), aliens 2-5 by
  object slot (27204: ((IX>>3)&3)+2 -> red, magenta, green, cyan), explosion cycles 66/67/70/71.
- Items (code, 25794 table by (IX+6)&15): offset 32 -> 70 yellow, 34/36 -> 69 cyan (0 when
  (24012)&31 >= 24: flashing), 38 -> 68 green, 40 and fuel (24) -> 25870: ((24012)>>2)&7 | 64
  (cycling bright colour). Fuel/items never reached in a free run: from code, not measured.
- The engine applies the object's (IX+3) ink per sprite (palette offset) at run time, so
  per-slot and cycling colours stay the game's. Sheets show the first/default colour.
- Sheet builder: tools/prototypes/jetpac_sheets.py (moves into nexclash/jetpac.py in phase B).

## Phase A question (sent 2026-10-19)
Proposed: Jetman, aliens, rocket parts, fuel pod, bonus items, explosions -> sprites; lasers,
platforms, HUD, text -> ULA. Depth: sprites over the ULA. Colours: Dean paints
jetpac_PAINTING_SPRITES.png (sheets in specnext reference/jetpac/; built by the phase-A script,
defaults all white until painted).

## Open
- Real recording (Fuse RZX) for the differential test; synthetic _auto.rzx desyncs at 532.
- Lasers: drawn by other routines; classify (sprite vs ULA) in phase B.
- Laser/HUD writers above not classified.
