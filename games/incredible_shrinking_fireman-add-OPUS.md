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
Open: Dean's answers; painted sheet; a recording reaching the 21 undrawn graphics.

## Open
- Phase A answers (above). Then phase B design + build.
