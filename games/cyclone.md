# Cyclone (Vortex Software, 1985; 48K) - engine `cyclone` (phase A)

Reference: specnext reference/cyclone/. Status: phase A done 2026-10-21 (decisions below); colour sheets sent, waiting for the painted sheet.
Code so far: nexclash/cyclone.py (colour sheets only).

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

- 2026-10-21: second recording cyclone_scc.rzx = the user's download of the spectrumcomputing.co.uk
  RZX (entry 1206): ONE segment, 179928 frames (60 min), no autosaves, starts at the menu (.z80
  snapshot inside, PC 0xFFFF IM 2). Same game: every routine checked (renderer, compositors,
  ISR, helicopter graphics, 0x6000-0x6950) is byte-identical to cyclone.z80; only data differs.
  Replays to the end with the C simulator in < 1 min (rzx.scan), no desync. Reaches score 11752,
  aircraft, survivors, crates, landings at base, lives lost. Bookmarks (rzx.cut, 2000 frames):
  cyclone_scc_aircraft_24500.rzx, cyclone_scc_aircraft_167000.rzx.

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
- (Corrected 2026-10-21: 0x7ADC draws the SHADOW, 0x86AF the HELICOPTER.)
- Helicopter SHADOW 0x7ADC: 3 x 3 cells from 0xED68 + 72 * (b + 1) (b from heading 0x7507, +8 RES 4
  with 0x7504; cells column-major, bottom up; a cell starting 0xFF is not drawn), with ISOMETRIC OCCLUSION: per cell, by the scenery tile in front (0x7AC1 height table,
  masks at 0xFB18): plain cell -> LDIR (opaque cell), others OR or AND-masked OR; attribute ink
  set to 0 (AND 248) or set to 0x60 / 0x68.
- HELICOPTER 0x86AF: 24 x 24 px buffer 0x6950 (3 columns of 24 bytes, top down): body copied by
  0x8CCD from 0xE8E8 + 72 * (b + 1), rotor XORed in per frame by 0x8CD2 (deltas 0x6700.., crash /
  break-up deltas 0x7000..); drawn 0x750D pixels offset (altitude), OR / AND-NOT into the dynamic
  tiles, occluded by scenery too.
- No game logic reads the composited figure pixels (readers of 0xFCF8-0xFDFF are the renderer and
  the compositors only); screen readers are the map-screen text printer (0x8E34) and the HUD.
- Map screen: 0x8D0E clears the play area and prints the island map (ULA): sprites must hide.
- HUD: wind bar 0x9149, view / altitude / fuel gauges, "BEWARE AIRCRAFT" messages.

## Other figures (cyclone_scc.rzx; tile census of the map at 0xF74E every 5 frames)
- Aircraft (0x88FF): placed IN THE MAP as a 3 x 3 cell block (map codes 0xF6-0xFE, cell steps);
  graphics copied per frame from 0xDDB8 + 72 * (heading/4 [+8 with 0x7504]) to tiles 60-68
  (0xFBE0), its shadow = the same graphic dithered (AND 0xAA / 0x55) in tiles 51-59 (0xFB98),
  placed 0x7524 / 0x7525 away (altitude). No direct screen plotter (screen writers in the
  bookmarks = the same set as the short RZX).
- Survivors (0x8C53 writes map codes 0-3): single map cells, cell aligned, scenery-like.
- Crates: single map cells (yellow) on the coast.
- The cyclone itself: not seen as an in-play figure in the hour (only the red spiral on the map
  screen and the wind gauge); every tile first seen late in the run is scenery.

## Clash today (preview frames)
Helicopter cells take ink 0 over the scenery: over a red roof the whole 8x8 cell turns black on
red; over the grey yard the shadow cuts grey cells. Over the sea it is fine (black on cyan).

## Decisions (user, 2026-10-21)
- Sprites: helicopter, its shadow, the aircraft, the aircraft's shadow. Survivors and crates stay
  map cells (ULA).
- Depth: as the original - helicopter and shadow behind the scenery in front (the game's own
  occlusion masks).
- Shadows: dithered see-through, as drawn.
- Mask (user, 2026-10-21): helicopter and aircraft (not the shadows) get an opaque mask: every
  pixel 4-adjacent to ink (no diagonals) plus everything it encloses (no transparent pixel inside);
  default bright white (15), paintable (keys M + figure + line + byte; cyclone.add_mask).
- Colours: painted by the user (sheets below); defaults black (palette index 8).

## Colour sheets (2026-10-21)
`python -m nexclash.cyclone sheet cyclone.rzx cyclone_scc_aircraft_24500.rzx
cyclone_scc_aircraft_167000.rzx --z80 cyclone.z80 -o cyclone` (12 s): PAINTING 71 figures, REFERENCE
102 (56 helicopter drawings incl. crash frames, 16 shadow headings, 3 aircraft headings seen +
13 from the code, aircraft shadows likewise). Keys: H/S/A/a + graphics byte; rotor pixels R + offset
in 0x6950 (one colour per rotor pixel position). Files: specnext reference/cyclone/.

## Phase B design (2026-10-21, before the first build)
User: "start the build" with the sheets' defaults (no painting yet): ink black, mask white.

Main loop (0x5B3C..0x5B86): 0x76D2 map build, 0x7E10 map translate + strip copy (0x7F21) + shadow
(CALL NZ 0x7ADC at 0x7F77), 0x86AF helicopter, 0xF39A, 0x8A7A, 0x85D4 FRONT PASS (redraws scenery
in front of the helicopter, and an aircraft in front, over the dynamic tiles: this is the
original's occlusion), then 0x762C renders the map (~ every 11 frames). Aircraft are in the map at
render time as tiles 0x3C-0x44 (aircraft, column-major 3 x 3, top down) and 0x33-0x3B (shadow).
Renders also at 0x9246 / 0x9284 (crash). Screen clears: 0x84D6 (whole screen), 0x8D0E (play area,
map screen).

Principle: the game's compositing runs UNCHANGED (all game memory identical by construction); only
what the render shows changes, plus snapshots in a private Next page.
- Hook page: Next page 26 (bank 13 low) at slot 6 (0xC000-0xDFFF) only while a hook runs (the ISR
  never touches slot 6: `isr`); code + data + private stack there. ROM stubs (alt ROM image 1 at
  0x386E, below 0x3AFF: the IM 2 vector bytes 0x3AFF/0x3B00 stay FF FF) map / unmap it. MMU6 is
  restored to page 0 before any game code runs. Hooks never touch IX / IY / I / IFF; SP is either
  the game's or the private stack in the mapped page. Turbo (NEXTREG 7 = 3) only around hook work,
  never while game code (the renderer) runs: the game has no frame sync, render speed = game speed.
- Sites (original bytes checked):
  0x7F72 `3A 05 75` LD A,(29957) -> JP e_s0: S0 = dynamic tiles 0xFCF8-0xFDFF (264) + attributes
          0xFE5F-0xFE7F (33) = the scenery of the strip (map rows 5-15, columns 10-12).
  0x7F7A `00 00 00` -> CALL e_s1: S1 = the tiles after the shadow.
  0x5B4E, 0x9281 `CD AF 86` -> CALL e_h: CALL 0x86AF, then HB = 0x6950 (72) and A = (0x750D):
          helicopter column c (0-2) rows 0-23 drawn at strip column c, line 62 - A (checked: 100 %
          of HB's ink bits are set in the rendered tiles at that place; A = 0..60 in the RZXs).
  0x762C `1E 00 DD` -> JP e_r (render): pre = build the sprite canvas from S0 / S1 / HB / the final
          tiles F, save F + the strip attributes + aircraft tile graphics (0xFB98-0xFC27), put S0
          (tiles + attributes) in place and zero the aircraft tiles; run the game's renderer (LD E,0;
          LD IX,0xF74E; JP 0x7632) at the original speed; post = restore everything, set sprites.
  0x84D6 `21 00 40`, 0x8D0E `21 00 58` -> hide all sprites (whole / play-area clear).
- Sprite canvas (strip + border): x 72-119, y 32-143 = 3 x 7 sprites of 16 (slots 4-24,
  4-bit patterns 4-24). Per strip cell whose map entry at render is its own dynamic tile
  (0x5F + 11 c + r; else the cell shows something else, e.g. an aircraft): shadow SH = S1 & ~S0 & F;
  helicopter HE = within the helicopter box only: (F & ~S1) | (F & S1 & HB); other diffs outside the
  box -> ink too. Mask (helicopter only) = HE dilated by 4-neighbours, plus every pixel of its
  26 x 26 window not 4-connected to the window border; pixel = 1 (ink, black) for HE / SH / other,
  2 (white) for mask, 0 transparent.
- Aircraft (slots 25-28, mask as above) and its shadow (slots 0-3, no mask): from the map cells
  holding 0x3C-0x44 / 0x33-0x3B at render (visible cells only = the original's occlusion), ink =
  those tiles' graphics; the ULA cells show only the tiles' attribute (graphics zeroed during the
  render). Everything clipped to the play area (x < 184, y < 176).
- Approximations (to tell the user): the mask is drawn around VISIBLE helicopter ink, so where
  front scenery cuts the helicopter the 1 px outline can lie over that scenery; shadow pixels that
  coincide with scenery ink are not separable (they are ink either way); where the original's
  opaque shadow cell erased scenery ink, the scenery ink now shows through the shadow's gaps.
- Verify: at every hook site, original vs patched from the same state (registers, all memory
  outside the screen and the hook page, interrupt safety); at renders, the patched screen = the
  original renderer on S0 / zeroed aircraft tiles (model), sprite pixels = the Python model of the
  canvas / aircraft rules from the verifier's own S0 / S1 / HB / F.

## Open
- Painted sheet -> docs/profiles/cyclone_colours.json; per-pixel colour map + recolour (today:
  defaults only, palette entries 1 = black, 2 = white).
