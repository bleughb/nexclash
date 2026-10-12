# Commando (Elite Systems, 1985; 128K) - engine `commando`

128K. Code: nexclash/commando.py, asm/commando_hooks.asm, docs/profiles/commando.json (regenerate
the profile hex after any .asm edit). Dispatch: nexclash.py cmd_auto, by signature at 39202.
Reference (specnext/reference/commando/): Commando_1985_Elite_Systems_t_128K.z80 (BASIC loader,
trainer version) + Commando_1985_Elite_Systems_t_128K.RZX (Dean, 2026-10-12; 8 autosave snapshots,
stripped by `auto`).

    python nexclash.py auto commando.z80 --rzx commando.rzx --no-record

| Output | MD5 | Status |
|---|---|---|
| commando.nex (plain, tail 0x6D00, starts in the front end) | a206f950c12f58a8e7f26b366f5a2480 | boot sim OK, front end PASS |
| commando_sprites.nex (altrom + bank-5 state) | 5c1081b73765978a7f3e055a66578542 | RZX IDENTICAL, front end + init + unit tests PASS; hardware untested |

Hardware 2026-10-12, first builds (5642e4b4 plain / f22a9452 sprites, started in the 128K BASIC
loader): a key at the loading screen -> plain: minor corruption, screen stays (no game); sprites:
crash. Cause: 128K BASIC pages ROM 0 (128K editor) on every statement - not on a Next, and alt
ROM image 0 is not filled. Fixed by the front end (below).

## Dean's decisions (2026-10-12)
- Depth (Dean's rule, from the game's own walk-blocking boxes): a figure that walks up into an
  object's box (from below) is in front of it; one that walks down into it (from above) is behind
  it. Every object with a box takes part, in every map section (not only area 1).
- Keep the loader's "INFY LIVES(Y/N)?" option (front end reproduces it; N = the recording).
- Sprites: the player, the five enemy soldiers and the POW group. Everything else (scenery,
  bullets, grenades, explosions, score panel) stays on the ULA. Player black, soldiers blue (their
  original inks), POWs the ink painted under their centre if red/magenta, else red.
  (Dean's "Sprites:" line was left as the template placeholder: chosen by the agent from the
  template's example "the player and enemies" + the POWs, flagged to Dean - one line to change.)

## Start-up (both builds): loader run in the toolkit + front end
- `auto` runs the loader snapshot in SkoolKit with the real 128K ROMs (SPACE for PAUSE 0, N) to
  the game entry 25089 (after the DI at 25088; frame 32, SP 25064, IM 1, DI, 7FFD 0x10) and writes
  <name>_entry.z80: the .nex files are built from it. The loader only changed the prompt cells on
  screen, BASIC variables and its stack.
- In that snapshot PC = 0x5D00 = front end (asm/commando_hooks.asm `front`, 94 bytes + prompt
  pixels 0x5D80 / attributes 0x5E00): row 0 shows the loading screen again; wait for a new key
  (PAUSE 0); copy in the prompt BASIC printed (INK 7, FLASH 1); wait for Y or N (Y: POKE 27653,182
  as line 30); restore every register; JP 25089. The game never touches 0x5C00-0x5E1F.
- front_tests: N and Y each reach 25089 with every register (R aside) and all RAM equal to the
  loader's own entry state (Y: plus 27653 = 182), except 0x5D00-0x5E1F; negative controls (a wrong
  register, the POKE broken) caught.
- Infinite lives (Y) is not covered by the RZX (Dean recorded N); 27653 is no patch site.

## Depth + scenery restore (alt ROM 0x3000-0x31F5, table DT 0x3400; RAM 0x5E20-0x5F5F)
- Per type (DT, 41 x 8, derived by Python from the game itself: its drawer 37302 + box builder
  60754 run on one object of each type): has a walk box, pixel extent (columns / lines relative to
  the object's x and 2y), middle of its walk boxes (2-line units). 18 types have walk boxes.
- occl (called by show, i.e. at every converted plot): for each list object with a walk box whose
  extent overlaps the figure, the figure is BEHIND if its walk-test point y + 6 (the point the
  game's own test 57139 checks, 5-7 below the top in the RZX) is at or above the box middle: the
  game stops that point at the box top when walking down and just below the box bottom when walking
  up, so this matches Dean's rule for every box height. (The first depth draft compared the feet,
  y + row pairs: a figure stopped above a tree's 5-unit box came out in front - fixed.)
- Behind: the sprite pattern loses the pixels where that object's ink is on the ULA inside the
  overlap (MASK, 32 rows x 3 bytes); the ULA scenery shows through.
- svsave / svrest: the plotter's erase clears the OLD frame's bits from the screen - for a converted
  figure those bits were never on the ULA, so the erase cuts holes in the scenery, which the game
  redraws only in some frames (RZX: ~900 of 2,000 frames redraw no scenery). e_ent saves the 3 x
  lines bytes under the old frame when the old image was a sprite; e_x ORs them back before occl.
  A converted plot then leaves the ULA exactly as it was: no bitten scenery, exact depth mask.
- Box kinds in the collision list 0xF900 (x, w, y, h; hit when x-E <= L < x+w+E and y-h < H <= y):
  plain (solid); bit 7 + bit 1 (types 35/37, water/trench pieces: passable for a figure with
  IX+11 bit 4 - Dean's "inner boxes" enemies move in); 0x81 entries (crates 15/16/17: pickup
  zones, not walls; ignored for depth). Huts (20) and type 30 spawn soldiers out of their doorway
  on a random countdown (58445).

## Patch design
- Alt ROM image 1 (hooks 0x386E-0x3C98, 1,067 bytes, all in the ROM's $FF area) + state in bank-5 RAM 0x5C00-0x5E1F (vars,
  12-entry table, hook stack, zero page 0x5D00, nibble table 0x5E00). No paging in the hooks:
  interrupts are ON at every site and the game's ISR writes 7FFD (always ROM 1).
- 12 entries x 4 sprites (16x16, 4-bit, 24 x up to 32 lines), double-buffered pattern banks; a
  converted object keeps one entry keyed (IX, column, y); POW instances share IX 64975 and get one
  entry each.
- e_init 25630 (`JP 27090` -> JP e_init): game entry from BASIC (USR 25088 ... JP 25630; the 48K
  path USR 25630 too; nothing else jumps there). Zeroes vars/table/zero page, copies the nibble
  table from the ROM, hides sprites 0-47, JP 27090. The patch itself does not write 0x5C00-0x5E1F
  (the front end lives there until the game starts).
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
- Scenery: object list 0xFF00 (8-byte entries: +0 next, +1 prev, +2 type 1-40, +3 x (bits 0-4
  column, high bits = variant), +4 y (grows as the screen scrolls); 64904 = LAST entry), drawn by
  37302 via the jump table 0x8012. Level map: (type, x) pairs from 37430 (pointer 64906): type 0 =
  wait N scroll steps, 34 = section end, 127 = loop to the start; 29 sections, 39 types (area 1 =
  RZX shows 13). Catalogue of all types with their boxes: specnext docs/review/commando/.
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
Depth + restore (5c1081b7): same RZX IDENTICAL; 4,287 converted plots restored the scenery their
erase cut (ULA unchanged, checked per call); 66,170 scenery pixels drawn in front of figures;
depth unit 315 cases (150 behind), negative control (no walk boxes) 150/150; restore negative
control 6/6; depth table re-derived from the game = the profile.

## Known visual differences (by design)
- Figures keep their own colour (the original ORs them into the scenery and they take its ink);
  behind an object only the object's INK pixels hide the figure - its paper (e.g. the white cliff
  under the big bush) does not.
- Converted figures no longer bite holes in the scenery (the original's erase does until the next
  scenery redraw).
- A figure at a screen edge (column >= 30) or clipped at the top of the play window is drawn on the
  ULA in its cell colours, as the original.
- A bullet or explosion drawn over a figure on the original is behind the sprite here (18
  sprite-frames in the RZX).
- With 12 figures already shown a further one would stay on the ULA (never in the RZX: max 6).

## Hardware checklist (commando_sprites.nex)
1. Boots to the loading screen; any key -> flashing "INFY LIVES(Y/N)?" top left -> Y or N -> game
   menu (the first builds crashed here). Try both commando.nex and commando_sprites.nex; Y should
   give infinite lives.
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
10. Depth: walk down onto a palm tree from above - you stop at the trunk base and most of you is
    behind the canopy/trunk; walk up into it from below - you stop below the base, in front.
    Same with rocks, sandbags, walls, huts, the big bush (later areas too).
11. Moving figures no longer leave holes in trees / rocks behind them.

## Open
- Hardware untested.
- RZX covers area 1 (menu, play, deaths); later areas use the same plotter and descriptors, and
  the depth table covers every type in the map, but only unit tests cover types not in area 1:
  an RZX of later areas (INFY LIVES = Y makes it easy; autosave off) would verify them.
- Paper-coloured parts of objects (white cliff) do not hide a figure behind them (ink only).
