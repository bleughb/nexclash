# Jetpac (Ultimate Play The Game, 1983) - engine `jetpac`

48K (16K game). Code: nexclash/jetpac.py, asm/jetpac_hooks.asm, asm/jetpac_tables.asm (GENERATED:
`python -m nexclash.jetpac tables GAME.z80`, then `python tools/asm2profile.py jetpac`),
docs/profiles/jetpac.json. Dispatch: nexclash.py cmd_auto, by signature at 30522 (the plotter).
Reference: specnext reference/jetpac/Jetpac_1983_Ultimate_Play_The_Game_a_16K.z80 (Dean, 2026-10-19).
NO RECORDING (Dean, 2026-10-19: "no rzx this time"): the differential test runs on a 6000-frame free
run (jetpac.free_keys: menu 1/3/5, then Jetman walks, flies and fires both ways) + unit tests over
every graphic. A real Fuse RZX would add the game's own paths (rocket build, fuel, items, levels 2+).

    python nexclash.py auto Jetpac.z80 --no-record

| Output | MD5 | Status |
|---|---|---|
| jetpac.nex (plain, tail 0x5B00) | feff51b7038606d21c03c260055481e4 | boot sim OK |
| jetpac_sprites.nex (altrom, stateless hooks, 82 patterns) | 2db185f7bf2a515898389f14e0f1651b | free run IDENTICAL, unit PASS; hardware untested |

Verification (2026-10-19): free run 6000 frames: 20433 draws, 100 erases, 23192 colour paints,
5 screen clears, 2193166 sprite pixels = the original plot; unit: 5712 graphic cases (every graphic
incl. all 8 levels' aliens and the 12 carried rocket parts x 8 positions incl. both edges x 3 inks x
first/last object), erase 12 (incl. the flame erase with the rocket visible; the round-1 build fails those 6), clear 1, guard 1, negative control 40/40.

## Patch design
- Alt ROM only (hooks + tables 0x386E-0x3C4F, 993 bytes): no RAM page, no state. 82 4-bit patterns
  (bank 11, uploaded at setup across both 8K pages), sprite palette offset n index 1 = Spectrum
  colour n (8-15 bright). Tail 0x5B00 (0x5B00-0x5B7F zero; a loader leftover at 0x5B80-0x5B8D is
  never touched).
- e_nw at 29263 (replaces LD A,(DE) / LD B,A / LD (24004),A, all replayed): object i = (IX-23808)/8;
  graphic (DE-1) looked up in gtab: static graphics directly, alien buffers by (24048) & 7, carried
  part buffers by (23860) * 4 + ((24048) >> 2) & 3; sprite x = byte column * 8 + the graphic's left
  trim, y = bottom line - 16 * rows + 1 (patterns bottom-aligned); up to 2x2 sprites, the column
  crossing x = 256 copied at x - 256 (the ULA row wrap); colour = (IX+3) ink + 8 * bright as the
  palette offset; unused sprites of the object hidden. Runs at 28 MHz (NEXTREG $07 3 -> 0): ~4K T
  per draw in the simulator.
- e_e1 / e_e2 at 29344 / 29349 (CALL 29223 / 29220, erase only): hide the object's 6 sprites; at
  29344 a FLAME graphic in DE (32652 / 32687) hides only the flame's sprites 102-107.
- Rocket flame (26217-26308): drawn and erased on the rocket BASE object (y + 21); with the rocket on
  the ground both flames are erased every frame. Own sprite group 102-107 for draw and erase
  (Dean's hardware video 2026-10-19: rocket pieces flickered - the erase hid the rocket each frame).
- e_cls at 24717 (CALL 29112, every new screen): hide sprites 0-107.
- Screen-write removals: 30532 77 -> 00 (erase AND), 30561 77 -> 00 (draw OR), 29171 72 -> 00
  (object colour over its cells). The plotter keeps running: all game state stays the original's.
- Stack: lowest SP inside the hooks 23762 (sites >= 23782); + the ROM ISR's 16 bytes = 23746, above
  the code the game runs at 23728-23730 (the game alone reaches 23742).

## Hardware checklist (first test)
- Boots to the menu (1, 3, 5) and plays; Jetman, aliens, rocket parts, fuel, items, explosions are
  sprites in their game colours (aliens red / magenta / green / cyan by slot, items cycling).
- No colour clash: platforms and lasers keep their own colours where figures pass.
- Aliens wrapping across the left/right edge show on both sides like the original.
- Rocket assembly, fuel filling (parts turn magenta), take-off, level 2+ aliens (not reached by the
  toolkit's free run: proven by unit tests only).
- Speed: the same as the plain .nex (hooks at 28 MHz).
- Game over / new game: no sprites left on the menu.

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
- Real recording (Fuse RZX) for the differential test: the free run never builds the rocket, so
  fuel, items, take-off and levels 2+ are proven by unit tests on the hooks only. The synthetic
  _auto.rzx stops at frame 532 under scan (BRIEFING C2 29).
- Recolour (PLAYBOOK 3b): not built. Dean chose the game's own colours (2026-10-19), which the
  hooks take from (IX+3) at run time; a painted sheet would need per-pixel nibbles in the patterns.
- Two-player games: the alien lookup assumes (24048) is the level the aliens were built for
  (26921 runs at each level start); not exercised (the free run is 1 player).
- Lasers, platforms, HUD and text stay on the ULA (decision); their writers (29023, 29060, 28708 /
  28717, 28829) are untouched.
