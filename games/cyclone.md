# Cyclone (Vortex Software, 1985; 48K) - engine `cyclone` (phase A)

Reference: specnext reference/cyclone/. Status: phase A (analysis); design question to the user open.

## Inputs (2026-10-21)
- User sent Cyclone_1985_Vortex_Software_a.z80 + .rzx (Fuse 1.x, Windows).
- The .z80 is NOT usable as the start state: saved mid tape load (PC 0x0604 = ROM LD-BYTES, DI,
  IM 1); a .nex of it would sit in LD-BYTES with no tape. 3355 bytes differ from the RZX start.
- cyclone.z80 = the RZX's first snapshot (SZX -> .z80 with SkoolKit get_state / write_snapshot;
  RAM and every register identical; LEARNINGS 2.4): PC 0xFFFF, SP 0xFFE0, IM 2, I 0x3A, DI (an
  interrupt just accepted). MD5 745cb8f59f865db5118e6dc98d09e385.
- cyclone.rzx = the RZX stripped (`rzx strip`: 8 autosaves dropped), 4700 frames (94 s), replays
  to the end. MD5 77010f7b6d806fbe44bf6c5dcfc7bec8. Covers: take-off at base, flying over land and
  sea, the map screen (twice), "BEWARE AIRCRAFT" at the end. NOT covered: the cyclone, crates,
  survivors, aircraft, landing / pick-up, refuelling, losing a life, game over, the menu.

## Snapshot facts (PLAYBOOK 0b)
- 48K, ROM 48K BASIC, IM 2 with I = 0x3A: the vector is read from the ROM (0x3AFF/0x3B00 = FF FF)
  -> 0xFFFF: JR 0xF3 (ROM byte 0x0000) -> 0xFFF4: JP 0x83C2 (the handler). Hook code in the alt ROM
  must keep 0x3AFF-0x3B00 = FF FF (and ROM 0x0000 = F3).
  `inspect` reports "IM 2 handler in ROM (0x0000)": it reads the vector from zeroed ROM (toolkit
  bug, not fixed here).
- ISR (`isr`): 109 instructions, saves IX before use, up to 14 bytes of stack; border OUTs;
  slots 5, 6 never touched by it.
- Plain build: tail 79 bytes at 0x5D24 (`convert --tail 0x5D24`): 0x5C78-0x5FDB is never read or
  written in the RZX (old BASIC area); 0x5D21-0x5D89 is zero. nextboot.check OK.
  cyclone.nex MD5 (tail 0x5D24) recorded in specnext reference/README.md.
- Free / untouched RAM (RZX): 0xDDCA-0xE27F (1206), 0x5C78-0x5FDB (868), 0x6BE9-0x6EFF (791),
  0xE436-0xE6FF (714), 0xB73F-0xB8D9 (411), 0x78F2-0x7A80 (399). Lowest SP 0xFFCE.

## Rendering model (PLAYBOOK 2: tile map / full redraw)
- Play area 23 x 22 cells (columns 0-22, rows 0-21); HUD at columns 23-31 and rows 22-23.
- Tile map 23 x 22 at 0xF74E (one byte per cell), built each move from the world (records at
  0xF230, 20 bytes each; 0x76D2 clears and builds, tall scenery stacked upwards by 0x7E10-0x7F20
  from the tables at 0x6300-0x6AFF).
- 0x762C draws the whole map: attribute = (0xFE00 + tile), pixels (tile < 128) = 0xFA00 + 8*tile
  (tile >= 128: attribute only). Writers 0x763F/0x7652/0x7671/0x7684/0x76A3/0x76B6.
- Figures are COMPOSITED INTO TILES, never drawn to the screen: 0x7F21 copies the 3 x 11 strip of
  map cells at 0xF7CB (columns 10-12, rows 5-15) into 33 dynamic tiles 0x5F-0x7F (graphics
  0xFCF8-0xFDFF, attributes 0xFE5F-0xFE7F), then CALL NZ 0x7ADC (helicopter) at 0x7F77, then the
  shadow (0x86AF), then writes the dynamic tile numbers into the map (table 0x7F98).
- Helicopter 0x7ADC: 3 x 3 cells from 0xED68 + 72 * frame (frame from heading 0x7507 and rotor
  0x7504), with ISOMETRIC OCCLUSION: per cell, by the scenery tile in front (0x7AC1 height table,
  masks at 0xFB18): plain cell -> LDIR (opaque cell), others OR or AND-masked OR; attribute ink
  set to 0 (AND 248) or set to 0x60 / 0x68.
- Shadow 0x86AF: 24 x 24 px at 0x6950 (rotor animation XORed in by 0x8CD2 from 0x6700), drawn
  0x750D pixels below (altitude), OR / AND-NOT into the dynamic tiles, occluded by scenery too.
- No game logic reads the composited figure pixels (readers of 0xFCF8-0xFDFF are the renderer and
  the compositors only); screen readers are the map-screen text printer (0x8E34) and the HUD.
- Map screen: 0x8D0E clears the play area and prints the island map (ULA): sprites must hide.
- HUD: wind bar 0x9149, view / altitude / fuel gauges, "BEWARE AIRCRAFT" messages.

## Clash today (preview frames)
Helicopter cells take ink 0 over the scenery: over a red roof the whole 8x8 cell turns black on
red; over the grey yard the shadow cuts grey cells. Over the sea it is fine (black on cyan).

## Open (phase A question to the user)
- A longer recording reaching the cyclone, crates, survivors, aircraft, landing / pick-up,
  refuelling, a lost life and game over (other figures may be composited the same way or be map
  tiles: not yet seen).
- Which figures become sprites (helicopter, shadow; others once seen), depth (the game's own
  occlusion behind scenery, or always in front), colours (colour sheet after the recording).
