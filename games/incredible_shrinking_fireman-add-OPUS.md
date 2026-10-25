# The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_opus` (phase A)

Reference: specnext reference/incredible_shrinking_fireman-add-OPUS/ (branch
claude/incredible-shrinking-fireman-add-OPUS; the "-add-OPUS" suffix is this run's naming, Dean 2026-10-25).
Status: phase A done 2026-10-25, design question sent to Dean (below). No build yet.
Code: nexclash/incredible_shrinking_fireman_add_opus.py (capture + colour sheets so far).

    python -m nexclash.incredible_shrinking_fireman_add_opus sheet incrediblefireman.rzx \
        --z80 Incredible_Shrinking_Fireman_The_1986_Mastertronic.z80 -o incredible_shrinking_fireman-add-OPUS

## Inputs (2026-10-25)
- Incredible_Shrinking_Fireman_The_1986_Mastertronic.z80, MD5 fc8e7535fc42afb60c12625b5fdfd064.
- incrediblefireman.rzx (Dean), MD5 8154d148d90b0f3cc94229bc143bac68: 1 segment, 32492 frames
  (650 s), 29891 interrupts. Replays to the end with the C simulator, no desync. Covers the title,
  many rooms, enemies, the fire-engine room, the option table and "YOU ARE CARRYING" screens, the
  title again at the end. 21 graphics of the bank are never drawn in it (sheet group "From the code").

## Snapshot facts (PLAYBOOK 0b)
- 48K, in game code (PC 0xC524), BASIC loader above (CLEAR 24999). IM 2, I = 0x39, EI, SP 0x618A.
- ISR: vector read from the ROM at 0x39FF/0x3A00 (FF FF) -> 0xFFFF: JR with offset = ROM 0x0000 (F3)
  -> 0xFFF4: JP 0xC24C. Alt-ROM hook code must keep 0x39FF-0x3A00 = FF FF and ROM 0x0000 = F3.
  (`inspect` says "IM 2 handler in ROM (0x0000)": the same toolkit misreport as Cyclone.)
- ISR 0xC24C (`isr`): 942 distinct instructions - the game logic runs in it: plays the player's move
  (0xC269 CALL 0xB950 when 0xC1F2 is set by the main code before its HALT), enemies (0xE8E5 ...),
  sound (ROM BEEPER at 0x03B5). Reads the interrupted IX (0xBCD9 painter runs in it), uses EXX and
  EX AF,AF', up to 42 bytes of stack, writes 4601 RAM addresses, every slot touched.
  A hook with interrupts on must keep SP with >= 44 free bytes, IX, the alternate set.
- Untouched RAM (whole RZX): 0x8B15-0x9C3F (4395), 0xF3F6-0xFFF3 (3070), 0xAB70-0xB08F (1312),
  0x5C49-0x615B (1299), 0xB4D9-0xB94F (1143), 0xA870-0xAAAF (576). Lowest SP 0x4000 (SP used as a
  data pointer somewhere: check before choosing a hook stack).

## Rendering model (PLAYBOOK 2): pure XOR to the screen, delta draw
- 0xB950 = move object A (table 0xBCF7, 8 bytes: x, y, frame, -, dx, dy, attribute E, keep-mask D)
  to (x + dx, y + dy) showing frame (0xBCF6). One pass XORs old ^ new graphic into the screen
  (main set new, alternate set old; 3 or 4 bytes a line), plus the |dy| lines at either end.
  Frame 0 = blank: appear / disappear. Then 0xBC5F paints the figure's cells (2 x 3, 3 x 4 when
  unaligned): attr = (scr ^ E) & D ^ E, skipping cells with bit 6 in the 768-byte map 0xBD44
  (scenery whose colour figures never take). Writes back x, y, frame at 0xBC4F.
- Graphics: 16 x 24 px, 2 bytes a line top down, at (0xBD42) = 0x9C40 + ((3 * frame) & 255) * 16:
  the 8-bit multiply wraps for frames >= 86 (frames 97-108 drawn in the RZX read misaligned bytes).
- Objects: 0 = the fireman (callers 0xC269 in the ISR, 0xC2EB / 0xC7F6 falling, 0xC93A, 0xC94D,
  0xCBA5), 1 and 2 = the room's two enemies (0xEA9B / 0xEAC1 moving, 0xE9CC / 0xE9D8 room entry,
  0xEB72 / 0xEB7A / 0xEB83 clear all three - not in the RZX). 13 callers, all listed.
  Fireman: attribute 7, mask 0x40 (white, bright from the scenery). Enemies: bright inks 1-7, mask
  0, the ink changes per room; object 2 sometimes attribute 0.
- A room with no visible enemy: both enemies at the same x, y with the same frame -> their XORs
  cancel (nothing drawn), the cells are still painted (e.g. a shelf item shown green).
- Room start 0xE422 zeroes the three frames; the screen clears 0xC4A7 (all) / 0xC5B1 (rows 64-191).
- Other screen writers (all scenery / UI, stay on the ULA): RLE screen decompressor 0xC30C (top
  third: HUD frame), 8x8 cell printer 0xB3D0 (room tiles, collectables, text; attribute masked),
  LDIR clears 0xC4AD / 0xC5BB / 0xC5CA, pixel scrollers 0x7900-0x7BFF: 0x7ADA / 0x7A44 from the
  ISR (0xE912 / 0xE91D: the title's credits line), 0x79AE / 0x7918 from 0xCD38 / 0xCD4B (the option
  table screens, self-modified parameters, rows 160-191).
- Full-screen windows over the play area: "GAME OPTION TABLE" and "YOU ARE CARRYING" (blue). The
  figures' table entries survive them: the build must hide the sprites while one is up.
- Floor test 0xC8C5 (from 0xC7D4 / 0xC2C9 / 0xC8DA): reads the 2 screen bytes on the line 25 below
  the fireman's y (just under his feet): non-zero = standing. An enemy drawn there changes the
  result -> phase B must decide virtual read vs none from the RZX (PLAYBOOK 3, decision table).
- Attribute readers besides the painter: 0xCABF / 0xCAA2 (89856 / 59904 reads) - phase B: check
  whether they read cells the painter changed.

## Phase A question (sent 2026-10-25) - answers go here
Planned: the three objects (fireman + both enemies, every caller) become hardware sprites in front
of everything, no attribute painting (the scenery keeps its colours); scenery, collectables, HUD,
text stay on the ULA; enemies keep the room's ink unless painted; identical overlapping enemies
stay invisible (as the XOR cancel); sprites off while a full-screen window is up.
Answers (Dean, 2026-10-25): "ALL moving figures should become sprites. There are also a number of
collectable items that should become sprites." Depth, enemy colours, hidden pair: no preference ->
the defaults above (in front; live room ink + painted overrides; identical pair stays invisible).
Open: collectables (find their drawing path, add them to the sheets); painted sheet; a recording
reaching the 21 undrawn graphics.

## Phase B analysis (2026-10-25, whole RZX; scratch scripts step3.py / attr3.py, now in the verifier)
- Collectables = the diamonds (above). Items proper are hidden in furniture (EXAMINE: "YOU HAVE
  JUST FOUND A ..."), never drawn; the floating cards / bulbs / clocks are enemies (0xB950).
- Geometry: for all 27883 plots the screen change equals old ^ new graphic at (x, y), lines from the
  table 0xC044, column x >> 3 (+0..2), shift x & 7 - the sprite geometry. y 61-167, x <= 240: never
  off screen.
- The floor test READS figure and collectable pixels: 7263 of 674714 reads give another zero /
  non-zero result without them (fireman standing on an enemy: 2790, on a collectable: 4473). So the
  ULA pixels must stay as the original draws them (or a virtual read): chosen KEEP THEM.
- Attributes: no attribute read in the RZX ever sees a cell the figure painter changed (room-build
  map 0xCAA2 59904 reads, cell printer 0xB3F4 15763, 0xB3C5 3107, point plot 0xB42C 404, floor
  test past line 191: 4) - removing the painting changes no logic.
- ROM: the game reads only 0x0000 and 0x39FF-0x3A00 (IM 2 chain) and runs BEEPER / PIXEL-ADD.

## Phase B design (2026-10-25, before the first build)
Overlay, not removal: the plotter and the collectable drawing keep writing the ULA exactly as the
original (every pixel the game reads is unchanged); each figure gets hardware sprites exactly on its
pixels, in front. Every ULA pixel that differs from the clean scenery is a figure ink pixel under its
own sprite, so the picture = clean scenery + sprites. The figure attribute painting is removed (0xBCDF
LD (IX+0),A -> NOP NOP NOP: the value is dead; the scenery keeps its colours).
- Sites (original bytes checked): 0xBC5C DD E1 C9 (plotter exit POP IX / RET) -> JP e_plot;
  0xECFF 11 14 ED (collectable draw) -> JP e_item (back to 0xED02); clears 0xC4A7 / 0xB4AD
  21 00 40 and 0xC5B1 21 00 48 -> JP e_clr* (hide all, back to site + 3); 0xBCDF DD 77 00 -> 00 00 00.
- Hooks: alt ROM image 1 at 0x3A01-0x3CFF (+0x386E-0x39FE; 0x39FF-0x3A00 stay FF FF for the IM 2
  chain). DI inside (IFF saved with LD A,I twice, restored), 28 MHz inside (NEXTREG $07), state and
  the colour map in Next pages 26-30 mapped at slot 0 only while a hook runs (MMU0 back to $FF).
- Object a = (HL - 0xBCF9) / 8 at 0xBC5C. Sprites: collectables 0-4 (4-bit patterns 0-4), enemy 2 =
  5/6, enemy 1 = 7/8, fireman = 9/10 (higher on top: fireman in front). A figure = two 4-bit sprites
  (lines 0-15, 16-23) from one 256-byte pattern slot (5 - a), built at every plot from the game's
  graphic + live ink + colour map. Collectable k = 5 - (loop counter on the stack), pattern k.
- Visibility: shown[a] = frame != 0 at its last plot, cleared by the three screen clears; enemies 1
  and 2 both shown at the same x, y, frame -> both hidden (the XOR cancel).
- Colours: palette = the sheet's (index 0 transparent); pixel = painted nibble when the entry's check
  byte equals the graphics byte, else the live ink: E & 7 (0 -> black 8), bright if E or the keep-
  mask D has bit 6 (the room build sets BRIGHT everywhere). Collectable: its cell's ink.
  Colour map: index i = address - 0x9C40 (graphics, 0..4143) / 4144 + address - 0xED14
  (collectable); entry = page 26 + i / 1024, offset (i % 1024) * 8: 4 nibble bytes + check. Flags
  byte: page 30 offset 0x1F00.
- Verify (per event, original vs patched from one state): registers, all memory (dead stack excepted),
  sprite pixels + colours vs the model; S = figure pixels in the ULA (from the original's screen
  changes) must lie under visible sprite ink; attribute-difference model checked at every attribute
  reader; interrupt safety before the DI.

## Open
- Build + verify (phase B). Paint sheet (Dean).
