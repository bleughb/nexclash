# El Capitan Trueno - build notes (graphics table, recipe, system map)

Moved out of el_capitan_trueno.md (size budget, tools/doccheck.py). The game file keeps the facts, the open
work, the lessons and the next session; this file keeps what a session needs to rebuild or extend the hooks.

## Graphics (frame table)
- Table at 0xE290, 4 bytes per frame: [flags | width in bytes (bits 0-4), height, gfx address]; 0x8254
  looks it up (frame * 4 + 0xE290). Bit 7 of the flags = the side the graphic faces now: when a figure
  turns, the game mirrors the graphic IN PLACE (0x8280/0x8295/0x82A1).
- Gfx: 1 header byte, then height rows of width bytes (1 bpp, no mask stored), then a few extra bytes
  (likely the column draw/skip bits for the 0x872C code generator). Same table in all levels: 126
  frames, then a second block after a gap (e.g. 161/162 = rope links).
- Composite figures (0x8ABC, IY 0xE644 for the hero): part list [frame, dx, dx mirrored, dy] -> temp
  descriptor 0xE600 -> 0x82DF.
- Heroes: Captain = torso 98 (+ poses 80-91) over legs 95 (+ 93-97); Crispin (small, blond) = frame 4
  (+ 9-16?) with part 33; Goliath (big) = frame 75 (+ 76-79?), one piece 24x38. Portrait at the bottom:
  col 0 Captain, col 9 Goliath, col 23 Crispin (hidden ones are black on black).
- Others: rats 57-62, coins/items 24-31, knives, explosions, monsters (sheet: snaps/frames.png).

- Graphics catalogue over the whole RZX (C simulator, gfx hashed at each frame end, 7.6 s): one
  real graphic per frame (+ its exact bit mirror: in-place mirroring is bit-exact); other variants
  occur 1-6 times = caught mid-mirror, never plotted. Exception: frame 32 = the thrown knife (red
  hilt, yellow blade), two hand-drawn graphics swapped in by the game (2802 / 831 frames), not a
  mirror. Total 167 shapes, ~680 16x16 patterns (~84 KB at 4 bpp): does not fit pattern RAM,
  so keep converted patterns in spare RAM banks and upload the ones on screen (3-6 figures).
- Unknown graphic at run time (not in the catalogue): leave that figure on the ULA as the original.
- The mask is NOT computed from the graphic alone: it comes from the graphic's trailing bytes, which
  the in-place mirroring flips too. Shapes must be captured from one consistent state (graphic + its
  own trailing bytes as the base state holds them); writing the catalogue's graphic over a state where
  the frame was mirrored paired it with a mirrored mask (frame 98: 55 mask pixels on the wrong side ->
  ULA figure pixels left uncovered = the "white flashes"). Fixed in build/shapes.py 2026-10-13.
- Frame table has up to 212 entries (0xE290-0xE5DF; 0xE600 = temp descriptor): catalogue with
  220 -> 210 shapes, 535 patterns, 9 pages (72 KB). Every extra variant is transient (mid-mirror).
- Plotted in the RZX (Python hook on 0x82DF, build/plotstats.py, ~7 min): frames 0-124 (not 77-79,
  105), 156, 157, 161, 162, 192, 209; callers 0x8AF7 (composite, 40845) and 0x8A74 (tables, 7015).
  Flags seen: 0x05/0x15 (+0x80 mirror), 0x55 (frame 33 only: bit 6), bit 1 set ~330 times.
- Descriptor: +0 frame, +1 x in 4-pixel units, +2 y, +3 flags: bit 0 visible, bit 7 mirror x,
  bit 6 mirror y (exact, same box), bit 1 hit flash (the whole silhouette = mask in the ink colour),
  bit 3 mask = whole box (not seen in the RZX), bits 2/4 always set in play (meaning not needed).
- Colours: per cell. Table flags bit 6 = multi-colour graphic: the painter 0x83A6 copies
  attributes per column from the graphic data (self-modified NOP/INC HL), e.g. the knife: blade
  0x46, hilt 0x42. Shapes are captured cell-aligned (descriptor x 40, y 76) and each ink pixel takes
  the attribute painted in its cell (13 multi-colour frames).
- Clean attributes: only the figure painter, the post-copy reset and 0x89C9 (cycle start: saves
  0xF13C -> 0xEF98) touch the attr buffer, so 0xEF98 at copy time = scenery only. Patch: the
  copy's attr source operand at 0x889C (3C F1 -> 98 EF). Screen position of the mask box: x = 4*(+1) - 120,
  y = (+2) - 52 (buffer: x = 4*(+1) - 128, y = (+2) - 68; buffer -> screen +8, +16).

## Recipe for an AI session
### The current build chain (2026-11-04; contributor's folder trueno/build/, run from there)
Inputs: the title .z80, trueno1.rzx and the contributor's sheets gfx/*.png (hand-drawn from the game's
graphics, so they are not in the toolkit). `python build_all.py --release` runs everything once and
writes the four release files (Trueno.nex, _immortal, _sword, _immortal_sword); `--multi --fast
[--immortal] [--sword]` builds one. The steps, each reading the previous one's output:
1. gfxcat.py RZX -> gfx_catalog.json: every graphic of every frame (hash at each frame end; groups
   a graphic with its exact mirror and keeps the real ones: 167 real shapes). SkoolKit C simulator,
   the whole recording in seconds.
2. shapes.py: ink + mask per shape through the game's OWN plotter (state after 5000 frames).
3. patterns.py [--both]: 4-bit patterns (64 a page) from the shapes and the sheets, shape directory,
   flash, palette; --both also writes the COLOR ON set (only the 75 + 38 hit shapes that differ).
4. title.py (start-up title), portraits_l2.py (three portraits), bush_walls.py (Layer 2 table: bushes
   + fix cells + the castle wall's edited cells; fix_cells.py / wall_cells.py make the sheets).
5. sjasmplus -DMULTI=1 -DGAME_MHZ=3 asm/trueno_hooks.asm (version 1.24.0) -> tr_rom.bin, tr_page.bin,
   tr_setup.bin + .sym. make_nex.py refuses a hooks assembly that does not match its switches.
6. make_nex.py [--multi] [--fast] [--immortal] [--sword]: the patched snapshot + hooks + tables ->
   .nex, then nextboot.check (the title is skipped in the boot check: machine ID 0).
Checks kept as scripts (all over the whole recording): check_patterns, check_cover (figure pixels the
game changes lie under an opaque sprite pixel), check_order, check_nodraw, check_screen_reads,
check_buffer_reads, check_prerestore, check_mirror. A changed asm without the switches must assemble
byte for byte as before (the default build is the base of any proof).
Test builds from the recording: `rzxplay --stop N trueno1.rzx OUT.z80` (frame 46351 = screen 35
before the dragon, 46501 = at the dragon), then make_nex.py --snap OUT.z80 with hooks assembled
-DTITLE_MHZ=0 (the title ends at 3.5 MHz, so the game goes on and not the menu).
Benchmark (MAME, frames per render): screen 0 plain 5.65, hooks 5.15, fast 4.52; dragon plain 12.19,
hooks 12.12, fast 4.41: the hooks do not slow the game, the boss slowdown is the original's.
MAME note: after a start or reset the nextfaststart plugin may run the emulation unthrottled, so a
wait counted in frames passes in a blink; set normal speed (video.throttled = true, or write 0 to
port 0x2F3B) before a person watches.

### Steps behind the prototype (2026-10-13 and 14)
1. Plain build: `zt.convert('Trueno.z80', out, 0xA6C9, True)` (tail in the RZX-proven write-first area).
2. Facts above are verified; do not re-derive them. Masks/ink per shape: call 0x82DF in the
   simulator with a descriptor at 0xE600 (IX), foreground map 0xEF60-0xEF97 zeroed, (0xE60B) != 34,
   buffer 0xF2E0 filled with 0x00 (ink) and 0xFF (mask = cleared | ink); state taken just after the
   ISR restore (stop at 0xA1F1 after 0x886F).
3. Catalogue (C simulator, seconds): `trueno/build/gfxcat.py RZX gfx_catalog.json` -> `shapes.py`
   (ink, mask, per-cell attributes per frame via the game's plotter) -> `patterns.py` (4-bit
   patterns, 64 per page, shapedir/flash/palette) -> `check_patterns.py` (round trip, 0 mismatches).
4. Hooks: asm/trueno_hooks.asm (sjasmplus 1.24.0), builder prototype `trueno/build/make_nex.py`
   (TruenoPatch: alt ROM page 24 = bank 12, hook page 26 = bank 13, patterns from page 28 = bank 14,
   Layer 2 banks 20-22 filled 0xE3, tail 0xA6C9) -> Trueno_sprites.nex; nextboot.check OK.
5. MAME 0.289 (2026-10-13, `trueno/build/run_nex.py`): menu, game starts, hero and goblins as
   sprites, a goblin passes behind a bush (Layer 2 priority). Host's look still to come.
   Render order (build/check_order.py, whole RZX): no 0x82DF call while a render waits for the
   copy (298,965 plots, 10,755 copies), no interrupt accepted at 0x82DF.
   Screen reads (build/check_screen_reads.py, whole RZX; only window attributes differ from the
   original): CLS fills 0xA21F/0xA230 (read what they wrote), effects 0x5E1E-0x5E41 (pixel shift,
   attribute fade), 0x984B (game end: LDIR all attrs -> 0xFC1C, a screen save), 0x980B / 0xA659 /
   0xA67F / 0xA27F (panel and status rows), 0xEF2E (pixels). No logic reads window attributes;
   exact address ranges per PC still to list for the record.
   Cover (build/check_cover.py, whole RZX, hooks' model incl. pattern memory and flushes): every
   figure pixel the game changes lies under an opaque sprite pixel - 10,508 renders, 17 flushes,
   0 uncovered (2026-10-13, after the consistent-state shapes; before: 5,769 renders uncovered).
   Buffer reads (build/check_buffer_reads.py, whole RZX, 0xF2E0-0xFFFF): the plotter 0x85FA-0x862C,
   the copy 0x896D-0x89A7, the stack (menu SP 0xFFF6: 0x8869, 0xA19C-0xA204), the block swap
   0xEF23 (screen <-> memory store for menus / transitions), start-up 0x5FFC-0x6086 and
   0x9837-0x986C. No logic reads figure pixels (no pixel collision): not drawing figures is safe.
   No-draw patch (check_nodraw.py over 4 states): RAM differs only in the generated row code
   0x85FC-0x8610, restore-list saved bytes (overlapping figures save scenery, never read except by
   the restore, which leaves the same buffer) and dead stack.
5a. Pause menu (key during play): 0xA36C polls the keys and tail-jumps 0xA375 JP 0xA501; the menu
   draws its window in the ULA (0xA5DA), loops at 0xA50B-0xA54A and returns with RET NC (fire, 0xA540)
   or C. Layer 2 and the sprites covered the window -> 0xA375 -> e_mnu: NEXTREG 0x15,0 / 0x69,0,
   CALL 0xA501, NEXTREG 0x69,0x80 / 0x15,1, RET (no register or flag change); e_scr turns Layer 2
   on too, in case the menu is left without its RET. Checked in MAME by the contributor (2026-10-13).
   Any game: look for menus and windows over the play area before relying on Layer 2 foreground.
5b. Dragon (screen 34, clear mode 0xE60B = 34): its energy bar (frame 0x69 x (0xE858), then 0x7D)
   is drawn by 0x8A0C through 0x82E4, past the figure hook, so it stays in the ULA; its colours
   (3 red cells, then green) are in 0xF13C. Hook e_att (0x889B, was the data patch 0x889C): the
   copy takes attributes from 0xEF98, on screen 34 from 0xF13C. s_cm clears Layer 2 (ZMAP) on
   screen 34 instead of deferring the rebuild (the old screen's foreground stayed there).
5c. End of part 1 (screen 60): 0x65CD JP Z 0x5DCD draws the access code screen without a screen
   build. Hook e_end (0x5DCD CALL 0x5E0E): sprites and Layer 2 off; the next game's e_scr (NEXTREG
   $69,$80) and first commit turn them on.
5d. Title menu: no '5 COLOR ON' (the original's colour off only greys the figures). Data patch
   0x5FF1 05 -> 04: LD B,5 at 0x5FF0 is the item count for drawing and for the key poll (items
   0x5ED1: pos, key 0x1B-0x1F, text letters 0x00 = A ... 0x26 = space, 0xFF end; handlers 0x5F98).
   The snapshot shows the menu already drawn: make_nex also wipes item 5's pixels (y 112-119, x
   88-175).
5e. Scenery clash, fix cells (build/fix_cells.py -> gfx/fix_tiles.png + .json, merged by
   bush_walls.py into bushwall.bin, Layer 2 WITHOUT priority, marked in OLDROPE so a screen change
   clears them). Places (screens, frames): barrels 45-47 (0xCB; 0xCC = the wall's cut edge) - the
   wall built without the barrels moved to them (right 1 px, each row's leftmost top-left
   shoulder); bell 17 (rim cells, ring 0x2E); hanging skeletons 39-41, 50-52 (0x52/0x53, 10 cells
   each, 6 looks); well arch 18 (0x32-0x34); cypresses over the red roof (0xAA-0xAD) 18-24, 58,
   59. The sheet holds each distinct look once; the build gives the drawing to every object that
   looks the same and leaves out cells drawn as the original. The contributor drew all of them.
5f. Explosions = frames 0-3 (attr 0x42): gfx/explosions.png (clean_sheet.py --raw
   Explosions=0-3), read by patterns.py; the contributor redrew them. Coins 25-31: gfx/coins.png.
5g. Test cheat CHEAT_IMMORTAL (0x7A1F LD (HL),A -> NOP) was on for the rounds; off since
   2026-10-13 evening: no-cheat run and game over checked (the original has no game over screen:
   straight back to the title menu).
   Checked in MAME by the contributor, 2026-10-13 (the last cypress tweak: at a later stage).
5h. English texts (contributor, 2026-10-14): build/texts_en.py, make_nex.py --en. Letter codes 0x00-0x19
   A-Z, 0x1A-0x23 0-9, 0x25 copyright, 0x26 space, 0xFF end; an item = x, y (pixels), codes. Lists
   (access code 0x5DF3, credits 0x5E58, menu 0x5ED1) are read from their head only and rebuilt whole;
   key labels (pointers in 0x5F13, 4 bytes each) and CONTINUAR (0xE904) in place. The snapshot's title
   is redrawn by the game's print routines 0x5FE9 / 0x5FFD in the simulator (IY = 0x60F8: 0x5FF2 tests
   (IY+0x13) bit 0 for a 5th menu item). make_nex.py --immortal = the test cheat as a player option.
6. nexclash/trueno.py (2026-11-04): detector + plain build + boot check only. Still to do:
   differential verification of the hooks (registers + memory; games/el_capitan_trueno.md,
   Verification plan), unit tests with a negative control, hardware checklist, and the sprite
   build inside the toolkit (graphics generated from the user's files, never stored in the repo).

## System map (2026-10-17, updated 2026-11-04; walk every new feature through it and every state:
title, menu, game start, hero change, shake, pause, access-code screen, game over -> menu, new screen)
- Layer 2 (banks 27-29 = pages 54-59, palette 0: 16-31 with priority, 32-47 without): play window cells
  y 16-127 (14 x 30; l2map), frame line y 14, panel y 136-191 (portrait cells), the rest transparent
  (0xE3). On/off NextReg 0x69 and port 0x123B; clip 0x18 full every commit; Y scroll 0x17 only by the
  copper. clist bytes: 0 WAIT 15, 2 shake/pause slot, 4 WAIT 23, 6 and 8 shake slots, 10 WAIT 135,
  12 MOVE 0x17,0, 14 pause slot, 16 HALT. The title has its own Layer 2 (banks 34-36, second palette).
- Sprites: clip = the play window (x 8-247, y 16-127); off (0x15) in the pause, the access-code screen
  and from the fade on; on again by the next commit.
- MMU in hooks: slot 0 = hook page (26) in the ISR hooks (saved and restored: V_SLOT0), main hooks back to
  0xFF; slot 1 = Layer 2 pages (back to 0xFF at the ISR exit); slot 3 borrowed by the title and the
  portraits (back to page 11); slots 2 and 3 together for a fix-cell block that crosses a page edge.
- Pages: 24 alt ROM, 26 hooks, 28-53 patterns, 54-59 Layer 2, 60-67 fix-cell table (full), 68-73 title
  Layer 2, 74-75 title data, 76 portraits, 77 colour store, 78-82 colour patterns; 83-95 free (95 pages on
  an unexpanded Next).
- NextRegs: 0x07 CPU speed (menu 7 MHz, game 28 MHz, sound effects and delays 3.5 MHz); 0x7F requests
  (bit 0 rebuild, 6 shaken, 7 clear); 0x60-0x63 copper; port 0x2F3B write 0 = MAME normal speed.
- Hook page variables 0x0000-0x0037 (V_*), language V_LANG 0x3A, colour V_COL 0x3B, state word V_STW
  0x3C; stacks STK1 0x0040-0x00FF (main hooks), STK2 0x1D00-0x1FFF (ISR).
- Alt ROM is almost full: bodies of the menu print, colour and language switches, the end screen live in
  the hook page behind 6-7 byte stubs; the plotter's all-0xFF map sits at the ROM top (data site 0x87BE).

## Game map (what the original code does where; disassembled with sna2skool, one search per fact)
- Title menu: 0x5FA2 entry (saves SP in 0x60FB, IY = 0x60F8), 0x5FC4 CALL NZ 0xA207 (screen clear),
  0x5FC7 credits (0x5FE9), 0x5FCA items (0x5FFD; item count LD B,5 at 0x5FF0), loop 0x5FCD (0xA195
  wait, 0x6019 keys, 0x604B dispatch via table 0x5F98: 0x6070 keyboard, 0x6069 Kempston, 0xA690
  Sinclair -> 0x6070, 0x6087 redefine, 0x618D colour). 0x6075 controls into 0xA154, 0x607F CALL
  0x981F = the game; back at 0x6082 LD SP,(0x60FB) / RET. A snapshot taken at the title resumes INSIDE
  the loop (0x5FCA is not run), so the screen memory has to be patched too.
- Game: 0x981F; the loop calls 0x95A1 (panel) from 0x89FF after SET 0,(0xE608) (render ready), then
  waits for the ISR copy (0x8A05, bit 1). Pace = 50 Hz frames per render, set by the CPU, no limiter:
  most screens 3-5, screens 36-38 about 7, the dragon (screen 34) 10.7 on average, up to 19 - the boss
  fight is slow in the original itself.
- Panel portraits: 0x95C3 runs 0x97E1 for each hero (IX = 0x96E9 Captain, 0x96F1 Crispin, 0x96F9 Goliath:
  +0 id, +1 bit 0 hidden, +2 width 9/9/14, +3 height 7, +6 attribute address). 0xE623 = the hero in
  play (3 = none). The pixels of all three stay in the ULA; 0x9805 swaps the ATTRIBUTES (hidden =
  black). Cell rows 17-23.
- Default keys (no redefine): Q up, A down, O left, P right, SPACE attack, 5/6/7 Captain/Crispin/Goliath,
  0 pause, 1 abort. Tables: heroes 0x6230, main 0x6239 (8 x 3: row, mask, code -> bits 0-7 of 0xE67F,
  read by 0xA32D; Kempston via port 0x1F when 0xA154 bit 0 = 0; bit 7 -> 0x5DEA, bit 6 -> pause 0xA501).
  trueno1.rzx was recorded with redefined keys (M attack, 1/2/3 heroes). A key held by a script must
  last more than 3 frames (the loop takes 4-5).
- Sword: pickup objects at IX 0xE7A4 / 0xE7AC (0x8FDF), 0x9078 box test then 0xE634 = 1 and message 8 (0xA429,
  table 0xA4B4). Sword level 0xE634 (cleared at start by 0x73CD; the pause sells +1 while < 3). Readers
  0x9A12, 0x9A2C, 0x9A73, 0x9A9B (the sword cheat patches exactly these four).
- Lives 0xE63F (DEC at 0x9BA0, 0 -> JP Z,0x5DEA). Energy: 0x95A1 (CALLed from 0x89FF), 0 -> SET 7,(0xE64B) death flag.
- Font: 0x5C65 + code * 8, 45 glyphs 0x00-0x2C (A-Z, 0-9, ?, copyright, space, N-tilde 0x27, ...); lookup
  0xA2C2 (LD DE,0x5C65 at 0xA2C8); print 0xA30C (x, y, codes, 0xFF end); key names via table 0xA3F5.
- Hero poses: composite table 0x8B22 (count, then 4 bytes per part: frame, dx, dx mirrored in 4-pixel
  units, dy; count bit 7 = one frame); hero objects 0xE644 / 0xE640 (+1 x, +2 y, +3 flags, bit 7 direction).
  Captain 03 stand, 01 02 17 00 walk, 26/27 sword; Crispin 10 stand, 0F 0E 0D 0C walk, 12/13 rope;
  Goliath 14 stand (75), 16 jump (76), 15 punch (79 body + 78 fist, dx +6), 18 crouch (77); 1B-21 death.
- Sound: one beeper routine, tone 0xA473 (pitch and gaps timed by the CPU), called only from 0xA460 in the
  note loop 0xA454-0xA470; every effect enters 0xA43D and leaves by the RET at 0xA472.
- Screen clear 0xA207 (menu, game over). Pause menu: 0xA36C -> 0xA375 -> 0xA501 (window in the ULA, RET NC/C).
- End of part 1 (screen 60): 0x5DCD CALL 0x5E0E (the picture shifted out pixel by pixel, CPU-timed), window
  0xA3BD, two text lines (0x6000), 0x5DE3 waits for ANY key (0xA378, no wait for the release), then 0x983A
  (E623 = 3, portraits hidden, attributes saved to 0xFC1C, fade 0x5E33 with 0xA18F delays), SP 0xEEEE, JP 0x61C1.
- CPU-timed code found so far: delays 0xA18F / 0xA195, the beeper 0xA473, the shift 0x5E0E.

