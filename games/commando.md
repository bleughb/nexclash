# Commando (Elite Systems, 1985; 128K) - engine `commando`

128K. Code: nexclash/commando.py, asm/commando_hooks.asm, docs/profiles/commando.json (regenerate
the profile hex after any .asm edit). Dispatch: nexclash.py cmd_auto, by signature at 39202.
Reference (specnext/reference/commando/): Commando_1985_Elite_Systems_t_128K.z80 (BASIC loader,
trainer version) + Commando_1985_Elite_Systems_t_128K.RZX (Dean, 2026-10-12; 8 autosave snapshots,
stripped by `auto`).

    python nexclash.py auto commando.z80 --rzx commando.rzx --no-record

| Output | MD5 | Status |
|---|---|---|
| commando.nex (plain, tail 0x6D00) | 5642e4b4d2a4b3f53cb7311eebeedecf | boot sim OK |
| commando_sprites.nex (altrom + bank-5 state) | f22a9452822b52163023de897f3358aa | RZX IDENTICAL, init + unit tests PASS; hardware untested |

## Dean's decisions (2026-10-12)
- Sprites: the player, the five enemy soldiers and the POW group. Everything else (scenery,
  bullets, grenades, explosions, score panel) stays on the ULA. Player black, soldiers blue (their
  original inks), POWs the ink painted under their centre if red/magenta, else red.
  (Dean's "Sprites:" line was left as the template placeholder: chosen by the agent from the
  template's example "the player and enemies" + the POWs, flagged to Dean - one line to change.)

## Patch design
- Alt ROM image 1 (hooks 0x386E-0x3C98, 1,067 bytes, all in the ROM's $FF area) + state in bank-5 RAM 0x5C00-0x5E1F (vars,
  12-entry table, hook stack, zero page 0x5D00, nibble table 0x5E00). No paging in the hooks:
  interrupts are ON at every site and the game's ISR writes 7FFD (always ROM 1).
- 12 entries x 4 sprites (16x16, 4-bit, 24 x up to 32 lines), double-buffered pattern banks; a
  converted object keeps one entry keyed (IX, column, y); POW instances share IX 64975 and get one
  entry each.
- e_init 25630 (`JP 27090` -> JP e_init): game entry from BASIC (USR 25088 ... JP 25630; the 48K
  path USR 25630 too; nothing else jumps there). Zeroes vars/table/zero page, copies the nibble
  table from the ROM, hides sprites 0-47, JP 27090. The build does NOT write 0x5C00-0x5E1F: the
  snapshot is the BASIC loader and that RAM is its system variables + program until the USR.
- e_ent 39120 (every plot): converted IX -> hide the entry at the old (column, y); JP 39202.
- e_main 39366 (main path, both columns < 30, inside the window): converted IX, table not full,
  page < 32, column step -1/0/+1 and row step |dy| < row pairs -> H := zero page (the new frame
  reads 0: the call only erases the old frame). Else passthrough. Replays LD A,D / SUB E /
  EX DE,HL / POP HL. (The steps the guard refuses make the original draw past its frame data;
  the game never makes them.)
- e_x 39529 / 40955 (main exit, normal / bottom clip): restore H (either set), upload the new
  frame as 4 patterns at 28 MHz, set the 4 sprites; replays LD SP,(64898) / RET. A frame starting
  below line 191 (y >= 96) keeps no entry: soldiers leaving at the bottom are reused without another
  plot, and such invisible entries were never freed (first build: table full in 239 plots).
- e_rect 27468 (rectangle clear): hide entries the rectangle overlaps; replays SLA C x2.
- e_cls 30597 (full clear): hide all entries; replays LD HL,16384.
- Setup (stub bank, 0xD000): sprite palette, transparency 0, hide 128, clip window 0-255 x 0-191
  (cuts bottom-clipped rows), sprites on.
- Tail 0x6D00 (0x6CB5-0x70F7 never read or written in the RZX nor after USR in the boot sim).

## Game facts
- Snapshot: BASIC loader at line 30 (PAUSE 0; "INFY LIVES(Y/N)?" -> POKE 27653,182; IF k=1
  RANDOMIZE USR 25088; RANDOMIZE USR 25630), PC 7997 (ROM PAUSE), IM 1, SP 25080, 7FFD 0x10,
  RAMTOP 25087, PROG 23755-24163. The RZX starts later (its own SZX: menu loop PC 64764, IM 2).
- Boot simulation (keys SPACE then N): USR 25088 at frame 41 (DI, pages bank 1 at C000 and back,
  JP 25630), IM 2 + first full clear 30597 at frame 52, menu loop 64764 at frame 53. After the USR
  nothing reads or writes 0x5B00-0x5E1F or the tail (300 frames).
- One plotter, 39120 (JP 39202), IX = descriptor: +0/+4 old/new column, +1/+5 old/new y (2-line
  units), +2/+6 old/new frame, +3/+7 old/new page (gfx (page+0xA0)*256 + byte at 0x98E2 + 2*frame
  (+1 if flags bit 2)), +8/+9 window (y 4..95), +10 row pairs (image 2*(+10) lines x 24 pixels,
  zig-zag stream: even rows c0 c1 c2, odd rows c2 c1 c0), +11 flags.
- One pass clears the old frame's bits and ORs in the new frame (no mask): a figure's pixels are
  exactly its OR'ed bits; no logic reads them (collision by coordinates).
- Main-path loops (39411 / 39534 / 39654: column step 0 / +1 / -1) put the new frame at the old
  column +-1 whatever +4 says; rows only in the old / new image (40600 / 40671) run |dy| times and
  the overlap loop (row pairs - |dy|) times, so |dy| >= row pairs wraps. The game does neither. Edge (column >= 30) and top
  clip (40926 / 40930) paths stay on the ULA.
- Converted descriptors: player 23514, soldiers 23313 + 20n (n < 5; 23393 unused in the RZX), POW
  group 64975 (one descriptor plotted once per POW). Not converted: explosions (63574...), bullets,
  grenades (other routines).
- Original inks under a figure's centre (RZX, every 10th frame): player black 86 %, soldiers blue
  80-90 %, POWs red 93 % (magenta otherwise); the rest is scenery ink = the clash itself.
- The RZX: area 1 from the menu, play, deaths (MEN 3 -> 1); POWs appear at the top edge.

## Verification (detail: docs/VERIFICATION.md)
RZX (3,279 frames, autosave stripped): 4,332 converted plots, 507 figure plots on the ULA
(edge/top clip; 0 for a full table), 887 other plots, 11 clears, max 6 figures, 570,425 sprite
pixels - IDENTICAL (all registers incl. AF', all memory outside the screen and the hook RAM; no
game access to hook RAM, tail, patch sites or the alt-ROM hook range; 7FFD always ROM 1; 25630
never re-entered). e_init: 16 random register sets from the loader's own RAM, negative control
16/16. Unit tests: 16,128 position cases (8 columns incl. edges 28-31/255 x column step -1/0/+1/+2 x 7 rows incl. 4/5/95/96 x 2 heights x row step -1/+1/= row pairs; 3,744 converted, 12,384 passthrough, 8,064 step-guard cases), 12 table-full, 12 other-descriptor (explosion slot), 12 page-guard (page 32), negative control (swapped nibble table, its own tables) 6/6 - every case: converted iff the guard says so, registers + memory as the original, sprite pixels = the original's new-frame bits. Boot sim: plain + sprites OK; patched snapshot differs from the original
only at the 7 sites (25 bytes); alt ROM only in its $FF area. Ghost metric: 18 of 10,139
sprite-frames mostly not on the original screen (bullets/explosions drawn over a figure).

## Known visual differences (by design)
- Figures in front of scenery (the original ORs them into it: the rock/tree clash is gone).
- A figure at a screen edge (column >= 30) or clipped at the top of the play window is drawn on the
  ULA in its cell colours, as the original.
- A bullet or explosion drawn over a figure on the original is behind the sprite here (18
  sprite-frames in the RZX).
- With 12 figures already shown a further one would stay on the ULA (never in the RZX: max 6).

## Hardware checklist (commando_sprites.nex)
1. Boots to the loading screen; SPACE -> "INFY LIVES(Y/N)?" -> Y or N -> game menu (BASIC runs
   intact: this is the step the build used to break).
2. Start a game: the player is a black sprite, soldiers blue; no colour clash against trees,
   rocks, sandbags, water.
3. Walk up the screen (scrolling): no sprite left behind where a figure was (ghosts), none missing.
4. Soldiers running in from the left/right edge appear on the ULA at the edge, then as sprites.
5. Bottom of the screen: figures entering from the bottom are cut at line 191 (no sprite in the
   border).
6. POWs (later in area 1): red/magenta sprites; rescue/ shoot them - they vanish cleanly.
7. Die / game over / new game / next area: all sprites cleared with the screen, none stuck.
8. Grenades, bullets, explosions unchanged (ULA).
9. Speed and sound as the plain build (commando.nex).

## Open
- Hardware untested.
- RZX covers area 1 (menu, play, deaths); later areas use the same plotter and descriptors.
