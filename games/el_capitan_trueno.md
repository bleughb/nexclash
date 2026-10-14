# El Capitan Trueno (Dinamic, 1990) - engine: none yet (phase A in progress)

48K. Inputs (contributor's machine, not in this repo): `Capitan Trueno, El (1990)(Dinamic)(ES).z80`
(copied as Trueno.z80) + trueno1.rzx (Spectaculator 0.61, 53542 frames, ~17m50s). The .z80 is the
RZX's own start snapshot (same PC/SP/I/IM, 60 bytes differ).

| Output | Status |
|---|---|
| Trueno.nex (plain, `--tail 0xA6C9`) | boot sim OK; runs in MAME 0.289 (title menu, key 1 starts, played by the contributor) |

## Snapshot (inspect)
PC 0xEEEE = ISR entry (title menu; DI, IM 2, I=0xED, table 0xED00-0xEE00 all 0xEE -> 0xEEEE JP 0xA1CB).
SP 0xFFF6 (title); in game SP ~0xEECC. Printer buffer used (0x5B02-0x5B63 read first).

## Start-up tail
Default places failed: printer buffer used -> converter put the tail below SP (0xFF97; 0xEE6D for a
frame-300 snapshot), above 0xC000, where the stub's own bank 10 sits; the tail's OUT 0x7FFD maps bank 0
back and the tail vanishes (choose_tail_addr refuses >0xC000 only for 128K; nextboot.check catches it:
"boot did not reach PC 61166"). Fix: `--tail 0xA6C9` - scan of the whole RZX: 0xA6C9-0xAAA2 write-first
(986 bytes; init code later reused as a buffer).

## Render (from the RZX, frames 1-3000)
- Back buffer: pixels 0xF2E0-0xFFFF (3360 = 30 cols x 112 lines, the play window), attributes
  0xF13C-0xF2DF (30 x 14). Attr buffer reset each render from 0xEF98 (LDIR 420 at 0x88A7).
- Copy to screen: 0x8915 (unrolled LDI 0x896D-0x89A9 pixels, 0x891D.. attrs), every 2nd frame;
  pixels to 0x4721.., attrs to 0x5841...
- Scenery into the buffer: LDD loop 0x88DC-0x8910 (writes 0x88FE-0x8906), attrs 0x88B0.
- Figure plotter (candidate): 0x85FA-0x8628, masked: buffer byte (BC) saved to (DE), AND (HL),
  INC H, OR (HL), back to (BC); self-modifying (writes at 0x860A inside JP 0x8609). H = 0xEE set at 0x85EF.
- Figure attributes (candidate): 0x842C LD (HL),A into the attr buffer (skips if bit 7 of A set).
  Probable clash source.

- Figure entry: 0x82DF (IX = 8-byte descriptor: +0 frame, +1 x, +2 y, +3 flags: bit 0 visible,
  bits 4/5/7 used) -> 0x82E6 CALL 0x844D (plot: 0x8462 CALL 0x8254, 0x8514/0x85BB/0x85CD set-up,
  per-row loop 0x85E8/0x85EB/0x85F6, then attrs 0x83D8 -> 0x840F -> 0x841A -> 0x842C).
- Callers: 0x8A56 (IX 0xE728, 12 x 8 bytes) and 0x8A61 (IX 0xE6C8, 12 x 8) via 0x8A71; composite
  figure 0x8ABC (IY 0xE644; parts from a table at HL: frame, ?, dx, dy -> temp descriptor 0xE600)
  via 0x8AF4 - probably the hero in pieces. Also 0x8A7F (IY 0xE7C2, 6 x 40 bytes) -> 0x8AC0.

## Render order and depth (free run of an RZX frame-5000 snapshot)
- 4-frame cycle (12.5 fps): attrs reset 0x88B0 -> restore 0x8902-0x8906 (~210-260 bytes, under the
  figures) -> figures 0x8600.. with attrs 0x842C. Nothing writes the buffer after the figures.
- Foreground (bushes in front of figures) is done INSIDE the plotter: 0x872C builds the row code at
  0x85FA from a bit string at IX (per byte column: draw = AND/OR snippet from 0x87A4, skip = INC DE /
  INC L from 0x879B). Frame 2160: a monster is cut exactly at the byte column where a bush starts.
  IX = foreground cell map at 0xEF60 (set by 0x87A9: IX = 0xEF60 + ((y-68)&248)/2 + (x-16)/8,
  bit = 0x80 >> (x&7); x in byte columns from 16, y in lines from 68): 4 bytes per cell row, bit 7 of
  byte 0 = window column 0; set bit = foreground, the row code copies the save-under byte only
  (figure hidden in that cell). 0x872C emits 3 columns per row, IX += 4 per cell row. Checked on
  frames 2000/5000: bits = the bushes; rows 12-13 all set = the red grass strip. Rows 14+ = other data.
  Built once per screen at 0x6410 (end of the screen builder 0x63F8): 56 bytes (14 rows) packed from
  bit 7 of the per-cell bytes at 0xE940 (14 x 32), RET at 0x6424. Other references to 0xEF60: 0x87BD
  (the plotter), 0xA6A4 (init area). Not yet proven: nothing else writes the map during a screen.
- Mask/graphic rows are prepared in 0xEE40.. (mask, 0x86B0, source 0xAB6B self-modified) and 0xEFxx
  (graphic, 0x86FB, source 0xAB63) before each row; the plotter does AND (0xEExx), OR (0xEFxx).

## Sprite design (2026-10-13)
- Window buffer is 30 columns x 112 lines (14 cell rows), row-major, 30 bytes per line (the copy
  0x8915 does 30 LDI per line); attrs 30 x 14 = 420. (Earlier "28 x 120" was wrong.)
- ISR 0xA1CB runs a task table at 0xA142 (8 words; in game only 0x8865). 0x8865: if bit 0 of
  0xE608 is set, copy buffer -> screen (pixels 0x8915, attrs from 0xF13C), set bit 1, reset attrs
  0xF13C <- 0xEF98 (420), then restore scenery under the figures from the list at (0xE604)
  (restore loop 0x88BA; list starts at 0xA6C9 = our start-up tail place, write-first, fine).
  (0xE60B) = 34: clear mode, buffer zeroed by PUSH instead of the restore.
- Plan: leave the plotter untouched (game memory identical); at the copy use the clean attrs
  (0xEF98) instead of 0xF13C; figures as sprites whose opaque body = the game's own mask, so they
  cover the figure pixels the plotter left in the ULA exactly. Measured on f5000 (blank buffers
  0x00 / 0xFF): the mask is a ~1 px outline built in pixel pairs; a morphological body (demo:
  fill(close1(dilate1(ink)))) leaves 49 mask pixels uncovered -> masks must come from the game.

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

## Recipe for an AI session (fill in as the build is done; goal: repeat without the research)
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
6. (to do) differential
   verification of the hooks (registers + memory), hardware checklist, move the prototype into
   nexclash/trueno.py (graphics generated from the user's files, never stored in the repo).

## Heroes (contributor, 2026-10-13)
- Three heroes, the player switches: the Captain, Crispin (small, blond; the only one who climbs
  ropes), Goliath (big; too heavy to climb). Composite entry 0x8AC0 with IY = object (hero: IY
  0xE644, set at 0x8ABC; enemies 0xE7C2 + 40k from 0x8A8F); the plotter corrupts IY and the composite
  does not restore it between parts, so IY at 0x82DF says nothing after the first part. Hero frames
  in the RZX (build/hero_poses.py, 72 poses, snaps/hero_poses2.png): 0-3 (death explosion), 4,
  13-16 (Crispin walking), 73, 74 (Crispin climbing a rope - the contributor's correction), 44,
  53-56, 80-91, 93-98, 123, 124 (the Captain: torso + legs/arm pairs), 75, 76 (Goliath).
  gfx/heroes_clean.png labels 73/74 as Goliath by mistake (labels only; cells are read by layout).
- Hit flash: every figure blinks normal / red ink (see trueno/NOTES.md); the contributor redraws the
  heroes cleanly (1-pixel black outline, filled insides; gfx/heroes_clean.png), hit = inverted.

## Controls and modes (contributor's RZX + his notes, 2026-10-13)
- Keys (Teclado): O left, P right, Q up, M attack/throw, 2 Crispin, 3 Goliath, 1 back to the menu
  (contributor); the Captain's key not known yet.
- Menu "5 COLOR ON": removed from the title menu (contributor, 2026-10-13; recipe 5d).

## Contributor's decisions (2026-10-13)
- Sprites: the hero, all enemies, coins/items - everything that can be done without clash.
- Colours: as in the game for now (may change later).
- Depth: the game's own rule - bushes and other foreground stay in front of the figures.

## Open
- Plotter internals: gfx format, widths, what (DE) is (save-under?), frame -> gfx address.
- isr / scan for hook state; who reads the buffer bytes of figures (collision).
- Preview frames and the contributor's decisions (which figures, colours, depth).

## Maintainer check (2026-10-14)
- Archive received; reference files were in specnext/reference/el_capitan_trueno/ (contributor's
  project in its contributor/ folder, rebuild steps in contributor/REBUILD.md). Dean removed that
  folder from specnext main (2026-10-14 12:28); the files remain on specnext branch
  contrib-el-capitan-trueno (commit 309eabf) - restore from there to work on this game.
- Every sprite build rebuilds byte-identical, with tk 0.1.4 and with nexclash main.
- Plain: `--tail 0xA6C9` gives ca49e0f4 (boot sim OK); the earlier listed 4b415b4c was the
  default-tail build, which does not boot (docs/VERIFICATION.md).
- Still open: engine module + profile + record (recipe step 6), per-call differential verification,
  unit tests, negative control, hardware. nexpatch: maintainers' decision pending (private for now).

