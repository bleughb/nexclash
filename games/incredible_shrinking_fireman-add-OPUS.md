# The Incredible Shrinking Fireman (Mastertronic, 1986; 48K) - engine `incredible_shrinking_fireman_add_opus`

Reference: specnext reference/incredible_shrinking_fireman-add-OPUS/ (branch
claude/incredible-shrinking-fireman-add-OPUS; the "-add-OPUS" suffix is this run's naming, Dean 2026-10-25).
Status: sprite build 400d0d11 (plain feb706fc), 2026-10-25: hardware round 1 fixed (plot entry hook) and
the mask added (all three figures, black). dc65565c ran on a real Next (Dean).
Code: nexclash/incredible_shrinking_fireman_add_opus.py (sheets, build, verifier, unit tests, recolour),
asm/incredible_shrinking_fireman-add-OPUS_hooks.asm, docs/profiles/incredible_shrinking_fireman-add-OPUS.json,
record docs/records/incredible_shrinking_fireman-add-OPUS.json.

    python nexclash.py auto incredible_shrinking_fireman-add-OPUS.z80 --rzx incrediblefireman.rzx --no-record

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
Answers (Dean, 2026-10-25, given in the parallel run claude/incredible-shrinking-fireman; confirmed
in this run 13:02): every moving figure becomes a sprite - the fireman, the two moving room figures and
the cut-scene figures, all through the one plotter 47440 (0xB950) - and the collectable items too.
Depth, enemy colours, hidden pair: no preference -> the defaults above (in front; live room ink +
painted overrides; identical pair stays invisible).

## Phase B analysis (2026-10-25, whole RZX; scratch scripts step3.py / attr3.py, now in the verifier)
- Collectables = the diamonds: per room up to 5 entries (flag, x, y) via 0xD6ED; 0xECCF draws each
  with 0xECFF: 7 bytes of 0xED14 written (not XORed), byte j on line B - j (B = y + 8) at column C / 8:
  C is a PIXEL x (0xED1B takes the column from C bits 7-3), not a column. Items proper are hidden in
  furniture (EXAMINE: "YOU HAVE JUST FOUND A ..."), never drawn; the floating cards / bulbs / clocks
  are enemies (0xB950). 0xED4F-0xED74 draws one 8x8 HUD icon via ROM PIXEL-ADD (stays on the ULA).
- The figure and diamond graphics (0x9C40-0xAC6F, 0xED14-0xED1A) are never written in the whole RZX
  (scan, 0 writers): the build precomputes from them (painted-frame table), the verifier fails on a
  write. The printer buffer: 126 bytes non-zero, 0x5B41 read before written -> put back after NEXLOAD.
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

## Hardware round 1 (dc65565c, Dean 2026-10-25)
Runs on a real Next. Two findings: (1) "the fireman sprite needs a surrounding mask (up down left right
pixels only)" - open, colour asked; (2) room 2's purple bulb flickers, room 6's enemy fireman "badly
cycling". Cause: the XOR plot takes 24-27K T (a third of a frame) and 97 %+ of plots run while the beam
draws the picture; dc65565c moved the sprite at the plot's EXIT, so for that third of a frame the half-
done ULA plot showed uncovered, in the cell's own colour (the painting is removed), e.g. cyan beside the
bulb. Worst on the wrapped frames (bulb 97-100, enemy fireman 105-108: big shape changes). The
toolkit could not see it: it checks state at hook boundaries, not what the beam shows mid-plot.
Fix: an ENTRY hook (0xB950) shows the new image on pending sprites before the plot runs; the exit
switches the figure's own sprites to it and hides the pending ones: old and new image covered
throughout. Mask (Dean: "lets do all figures"): fireman and both room figures, black (suggested, not
objected to), the 4-neighbours of ink only; the diamonds unmasked. Build 400d0d11.

## Build (2026-10-25)
Overlay, not removal: the plotter and the diamond drawing keep writing the ULA exactly as the original
(every pixel the game reads is unchanged); each figure gets hardware sprites exactly on its pixels, in
front. Every ULA pixel that differs from the clean scenery is a figure ink pixel under its own sprite,
so the picture = scenery + sprites (where a figure crosses scenery ink the ULA's XOR hole is covered by
the sprite). The figure attribute painting is removed: 0xBCDF LD (IX+0),A -> NOP x3 (value dead).
- Sites (original bytes checked): 0xB950 DD E5 87 (plotter entry PUSH IX / ADD A,A, A = object) -> JP
  e_ent (back with PUSH IX / ADD A,A / JP 0xB953 after the EI); 0xBC5C DD E1 C9 (plotter exit POP IX / RET) -> JP e_plot; 0xECFF
  11 14 ED -> JP e_item (back to 0xED02 with DE = 0xED14); clears 0xC4A7 / 0xB4AD 21 00 40 and 0xC5B1
  21 00 48 -> JP e_c* (HL dead there: loads a per-site tail, hides all, leaves through JP (HL) to the
  tail's LD HL,nn / JP site + 3: no stack in use while interrupts are on); 0xBCDF DD 77 00 -> 00 00 00.
- Hooks: alt ROM image 1, two blocks: 0x3A01- (+ the 20-byte start-up register block; below 0x3D00)
  and 0x386E- (0x39FF-0x3A00 stay FF FF: the IM 2 vector); the figure logic in page 30 at 0xD600 (runs
  only while page 30 is at slot 6; the per-byte colour path and the diamond hook, which map other
  pages at slot 6, stay in ROM). DI inside (IFF saved with
  LD A,I twice, restored), 28 MHz inside (NEXTREG $07 3, back to 0 before the EI), one push (AF) before
  the DI. Hook data in Next pages 26-30 mapped at SLOT 6 (0xC000) only inside a hook, MMU6 back to
  page 0 (as Cyclone; no hook reads game data in 0xC000-0xDFFF; slot 0 would also have done). Tail 0x5D00 (0x5C49-0x615B untouched), printer buffer put back.
- Sprites: diamonds 0-4 (k = 5 - the loop counter on the stack; 4-bit pattern slot k / 2, half k & 1);
  object a at 21 - 8a: its own 4 sprites and, from the plot entry to the exit, 4 pending ones (+4)
  showing the new image at (x + dx, y + dy) (8-bit adds, as 0xB97D / 0xB982), frame (0xBCF6). An image
  = 18 x 26 (the 16 x 24 graphic + the black mask) at (x - 1, y - 1): 4-bit sprites top-left / top-right
  (16 px right) / bottom-left (16 down) / bottom-right from two 256-byte slots. Higher on top:
  diamonds, object 2, 1, fireman. Double-buffered: slots 11 - 4a + 2 buffer (+1); the entry puts the
  new image in the buffer the own sprites do not show (or finds it in either: (frame, ink) cache), the
  exit switches. An exit with no entry before it builds the image itself (unit-tested fallback).
- Shapes precomputed at build time (the graphics are proven never written): frame f's block in page
  32 + f / 8 (+ (f % 8) * 1024), mapped at slot 7 during an upload: pixel-pair codes (ink / mask) for
  the 4 quarters (the right quarters' columns 18-31 are always empty: one code byte per row), the
  painted overrides per pattern byte, a painted flag. Run time: per object a 512-byte table (code ->
  pattern byte in its live ink, rebuilt when its ink changes) - 2 pattern bytes per code byte.
- Colours: palette = the sheet's (index 0 transparent). Figure ink pixel = its painted nibble (built
  into the shape block from docs/profiles/<record>_colours.json: key G + graphics byte address, used
  when the entry's check byte equals the graphics byte) else the live ink E & 7 (0 -> black 8), bright
  if E or the keep-mask D has bit 6 (room cells are BRIGHT); mask = black; paper = transparent
  (painting never covers the scenery). Diamond: its cell's ink, or its colour-map entry (key D +
  address; page 26 + i / 1024, offset (i % 1024) * 8, i = 4144 + address - 0xED14) through emit.
  Page 30: object tables 0x0200-0x07FF, code 0x1600-, NIB16 0x1E00, TINK 0x1E20, flags 0x1F00 (bits
  0-2 shown, 3-5 buffer), pending 0x1F01, variables 0x1F02-, cache 0x1F10. Recolour rewrites banks
  13-15 and 16-31 (the shapes carry the painted colours).
- Visibility: shown[a] = frame != 0 at its last plot, cleared by the three screen clears (also the
  option / carrying windows: drawn after the 0xC5B1 clear); objects 1 and 2 both shown at one x, y,
  frame -> both hidden (the XOR cancel). Diamonds shown from their draw to the next clear.
- Speed (28 MHz T / 6): dc65565c (exit hook only, whole RZX) mean 1.1K T per 69,888-T frame, max 6.7K
  T; entry + exit, no mask (2000 frames) 1.8K / 7.6K; with the mask, first version (per-pixel codes
  through a 16-entry table, overrides always) 5.8K / 28.3K; per-object tables + fast empty columns
  (400d0d11, 2000 frames) 2.4K / 16.4K (the max: room entry, three tables built). The original never reaches its HALT in a third of the frames (busy:
  median 31K T): the worst frames may run up to ~10 % longer. First version (no cache, per-byte map
  always; 2000 frames): mean 6.4K, max 21.6K.

## Verification (2026-10-25, the stamping run of 400d0d11: selftest --game --verify --stamp)
Whole RZX IDENTICAL: 27883 plot entries + exits, 79 diamonds, 165 clears, 34.6M sprite pixels (mask
included) against the model, 5.1M transient pixels covered from plot entry to exit, 169038 attribute
reads, 19737 interrupt-safety points; no non-figure write under a visible sprite. Unit cases PASS,
7/7 negative controls detected. Details: docs/VERIFICATION.md. Comparison picture (specnext):
incredible_shrinking_fireman-add-OPUS_three_windows.png.

## Hardware checklist
- Boots to the title (alt ROM + IM 2 via ROM 0x39FF: the vector bytes stay FF FF).
- Fireman white with a black outline over the scenery, no flicker while walking / climbing / falling;
  the scenery round him keeps its colours (no clash).
- Room 2's bulb and room 6's enemy fireman: steady colour, no flicker (round 1 defect).
- Room figures in the room's bright ink; two identical overlapping figures stay invisible as before.
- Diamonds as sprites in their cell's ink; picked up -> gone after the option screen.
- GAME OPTION TABLE / YOU ARE CARRYING windows: no sprite over them; figures back after.
- Speed: busy rooms (several figures) no slower than the plain build; beeper sound unchanged.
- Recolour: python nexclash.py recolour incredible_shrinking_fireman-add-OPUS_sprites.nex PAINTED.png.

## Open
- Hardware test of 400d0d11 (mask colour black: confirm). Mask on the diamonds: not asked for. Painted sheet (Dean) -> recolour, then the map becomes the build default.
- A pair-hidden figure (objects 1 and 2 on one spot, XOR cancel) that starts to move: its old pixels
  are uncovered during that one plot (the verifier counts these plot entries).
- 21 graphics of the bank never drawn in the RZX (sheet group "From the code"): unit-tested (every frame
  0-255), not seen in play.
