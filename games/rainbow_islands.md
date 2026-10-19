# Rainbow Islands (Ocean, 128K) - engine `rainbow`
EXCLUDED from automatic selftest checks (Dean, 2026-10-13: too slow, being reworked): run it with `selftest.py --game rainbow [--verify]`.
Updated 2026-10-19. Engine `rainbow`. Status: RZX-verified identical; RUNS ON HARDWARE (Dean,
2026-09-28). 2026-09-29: boss-spider fix + pattern-upload optimisation (hardware: runs, better;
busy scenes slower than the original). 2026-09-30: pattern cache 78b9ed99 (hardware: no visible
gain, slow when moving with enemies). 2026-10-01: SPEED BUILD - direct conversion + 256K
pattern store + sprites per piece 7559f940 (hardware: still slower than the original, music
slows). 2026-10-01: FRAME LIMITER + TURBO cbb5a1d4 (hardware: very smooth; minor tearing /
ghosting; sprites stay on the death/continue screens). 2026-10-02: RENDER-END COMMIT + sprites
off on non-play screens bddea69e (hardware: smooth, runs). 2026-10-11: COLLECTABLES AS SPRITES
(below) eb9836fe (hardware 2026-10-11: enemy tearing; item squares on opaque items; rainbows
partly black; dark-blue squares on partial tiles). 2026-10-11: OPAQUE-ITEM BASE TILE + RASTER-SYNCED
COMMIT ab97c76a (hardware 2026-10-11: rainbows with black edges/blocks, fruit and flowers on full
squares - analysis: codes 1-14 are RAINBOW pieces, the collectables are codes >= 15). 2026-10-11:
OBJECTS ON THE TILEMAP bffd9357 (below; hardware 2026-10-12: black lines around collectables not
wanted; sprite corruption and slowdowns seemingly at random). 2026-10-12: COLLECTABLES WITHOUT
BORDER + DIAGNOSTIC BUILD e50733b2 / diagnostic 8f25bc61 - not hardware-tested (superseded).
2026-10-19: NO RASTER WAIT + MUSIC QUEUE + FASTER TILES AND COMMIT (below) c5e1823d / diagnostic 71222105 (Dean:
"this seems better"). 2026-10-19: NO RAINBOW BORDER + COLLECTABLE INSIDES + PLAYTHROUGH SHEETS (below)
cf017271 / diagnostic c16751b0 - hardware test pending. Needs a core with the tilemap in bank 7 (Dean: most recent core).

Reference: rainbow.z80 (4c98b980), rainbow.rzx (55046d18), rainbownew.rzx (47bb2b16) in the
private repo. Whole-game playthrough rainbowislands_LeeBee.rzx (92bbaa0a, 195,356 frames, all 7 islands
and bosses, same game version; Dean 2026-10-19: "should not be referred to in full") -> BOOKMARKS:
reference/rainbow_islands/leebee/ = one RZX per round (leebee_rNN_islandI_roundR.rzx, 4.5k-11k frames,
starting at the frame the round variable 0x636F changes) + leebee_ending.rzx + leebee_bookmarks.json
(frame numbers). Use those, never the full file (`rzx.cut` rebuilds them in ~5 min). 2026-10-12: the repo rebuilds e50733b2 / 8f25bc61 / plain 7ac543fb byte-identical (boot OK);
bffd9357 was rebuilt by `selftest.py` with both RZX IDENTICAL. Review images from the sessions (mask
contact sheet rainbow_B_mask_sheet.png, objects.png) belong in the private repo too (they show game
graphics). Tools: nexclash/rainbow_objects.py (object/tile catalogue -> profile `objects`),
nexclash/rainbow_catalogue.py (figure catalogue for colours; fixed 2026-10-11 to read `plotters`),
tools/rainbow_items_proto.py (the collectables prototype, superseded).

## Dean's decisions (current)
Player white with black outline; stars as now (ULA); fruit / collectables keep their own colours;
black 1-pixel border on rainbows (and on player / creature sprites) only - collectables (codes
15+: fruit, cakes, flowers, stars) have NO border and are see-through (background shows around them
and through their gaps; filling enclosed gaps black is the alternative, not chosen); objects in front
of the scenery and behind all figures;
background never removed; steady speed (frame limiter); object handling automatic with manual
overrides (profile `objects`). Dean has the most recent core (tilemap in bank 7).
2026-10-19 (Dean asked for speed + "sound slowdowns"; plan agreed in chat): the commit never waits
for the beam (at the next interrupt instead); music = one AY tick per interrupt; faster tile
composer; Next techniques from his research (OUT/OUTI sprite writes). No copper (CPU/copper
NextReg-pair conflict, LEARNINGS 1.5). Tile-build cap per render ((b): items briefly on the ULA)
offered, not chosen.
2026-10-19 (after c5e1823d): rainbows WITHOUT border - all of them (tile pieces codes 1-14 and the
thrown rainbow sprite, class C3 outline transparent); collectables' INSIDE pixels (enclosed paper)
a fixed colour: white inside dark-ink items (black, blue, red, magenta), black inside the others
(automatic; per-code override `"fill": "white" | "black" | "none"` in the profile's objects, preview
collectables_inside_preview.png sent, no flips named yet). Colour SHEETS for every figure, split per
island + player + collectables, whole figures, default colours, collectables once per colour
(PLAYBOOK 3b); his painting becomes the per-pixel colours (not built yet).

## Deliverables
| File | MD5 |
|---|---|
| rainbow_sprites.nex (no rainbow border, collectable insides black / white, thrown rainbow without outline) | cf017271dfc01bdd0c7cf2f599b03628 |
| rainbow_sprites_diag.nex (same + diagnostic border) | c16751b0255ee3d83a4e342bf9a8c411 |
| (the same as c5e1823d; diagnostic code moved to the alt ROM; diagnostic 60bda664: blue = deferred commit, red = tile built, yellow = overrun, magenta = flag unreliable) | fe34236c476290cfec10183ef90d6141 |
| (no raster wait, music queue, faster tiles + commit; diagnostic 712221059d9351bece24629e3ae7a77d - its yellow was unreliable) | c5e1823de3a66b3c468961ebb72d383d |
| (collectables without border; diagnostic 8f25bc6146b9d7f7ae1f12a1d227447e) | e50733b2b7e2db32f004c1436a2e0461 |
| (objects on the tilemap, black border on every object) | bffd9357d772e2df975ec5f40dc9e4cb |
| (opaque-item base tile + raster-synced commit; rainbows as sprites) | ab97c76ae0edd3937e3149b0dac5e52f |
| (collectables as sprites; HW: tearing, item squares, black in rainbows) | eb9836fe60a70df02087920603c673b4 |
| (limiter + render-end commit + sprites off on non-play screens; runs on HW) | bddea69edaf6cf0a83dba8633c8f6618 |
| (limiter build, tearing) | cbb5a1d4ba4e84cec40191d3a3259f5a |
| (speed build without limiter) | 7559f940bb72211456b3ec53a0bdff60 |
| (pattern cache v1, 32 entries) | 78b9ed99ab714ef77024f84558987441 |
| (fix + optimisation, no cache: A/B for speed) | 4dce14afce8977fe39086923328a5e12 |
| (fix only, for hardware A/B: rainbow_sprites_fixonly.nex) | 4132ae00ce87b2e046859cd89344ecd3 |
| (previous, spider column missing) | 0c191d94d5c3291e96f282cc6b1e4984 |
| rainbow.nex (plain, tail 0x9F00) | 7ac543fb51c7a3c4137778eeb3cdc175 |

Rebuild (RELEASE, ~52 min): `python nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record`
Iterate (~15 min): `python nexclash.py auto rainbow.z80 --rzx rainbow_stripped.rzx --no-record --quick 2000`
(levels: docs/BRIEFING.md C3b; --quick 2900 on rainbow.rzx covers the bonus scene, ~15 min)
Options: `--ink white|#RRGGBB`, `--outline black|blue|transparent|#RRGGBB`, `--class-colours map.json`
(class palette offsets 0-14; offset 15 is reserved).
Objects catalogue (tilemap settings): `python -m nexclash.rainbow_objects rainbow.z80 rainbow_stripped.rzx
rainbownew_stripped.rzx -o objects.png` -> every object code seen (game graphic | tile shown) and the
map tiles under them, + objects.json: an "objects" section with every code and its settings, to
edit and paste into rainbow_islands.json (see "Objects on the tilemap").
Catalogue (colours): `python -m nexclash.rainbow_catalogue rainbow.z80 rainbow_stripped.rzx
rainbownew_stripped.rzx -o catalogue.png` -> every figure seen, grouped by graphics page set, +
catalogue.json. Page keys go into the class-colours map.

# MACHINE / HARDWARE

## Machine facts relied on
- 128K Spectrum paging: game pages bank 1 at C000 every frame (7FFD 17 then 16); ROM select bit
  always 1 (48K ROM = Next ROM3 = alt image 1); screen bit (7FFD b3) never set.
- 128K start-up tail must end below 0xC000 (its 7FFD write remaps C000-FFFF). Tail at 0x9F00.
- Next: ULA reads bank 5 directly, so pages mapped over 0x4000-0x7FFF (slot 2/3) are invisible.
- Next: code in slot 0 cannot unmap slot 0 -> entry/exit stubs live in the alt ROM.
- Next sprites: 4-bit anchors, attr4 0x80/0xC0 = slot half 0-127/128-255; 0x303B + port 0x5B
  pattern upload; $34-$39 attributes; $4B=0; palette via $43/$40/$41; clip via $1C/$19.
- Sprite priority: NextReg $15 bit 6 = 0 (reset value, never set): the HIGHER sprite number is drawn
  on top (guide r3 p.89).
- Next tilemap (layer 3): 40x32 entries over 320x256 (ULA at +32,+32: screen char row R, column c =
  entry (R+4)*40 + c+4); 2-byte entries (tile, attribute: palette offset bits 7-4, bit 0 = 0 tile
  over the ULA); $6E/$6F bit 7 = bank 7 (first 8K only, Next page 14; core 3.1.x+); $6B bit 7 on, bit 0 tilemap over the ULA,
  bit 5 = 1-byte entries; $4C transparent index; $43 0x30 = tilemap palette; clip $1C bit 3 + $1B
  (x in 2-pixel units). Sprites are drawn over it (SLU), so figures stay in front of objects.

## Next resources used
| Resource | Use |
|---|---|
| Alt ROM image 1, 0x386E-0x3B05 (+ register block) | entry/exit stubs; since 2026-10-19 also code that never remaps slot 1: render-end control s_re / rsafe, interrupt work s_int / dcom, the AY queue (s_ay, s_ps, aywr, ayopen, aytick, ayplay, ayslot), x8bld (all $FF in the 48K ROM; game never reads it) |
| Bank 1 sites (music) | 0xD4DE `21 59 5C` -> JP e_ps (AY player entry = a tick starts); 0xD6D4 `01 FD FF` -> JP e_ay (the one AY register-write routine: A = register, D = value) |
| RAM page 24 (bank 12) | alt ROM copy source (stub fills alt ROM at boot) |
| RAM page 26 (bank 13), slot 0 during hooks | state 0x0000 (vars to 0x7F, PBUF 0x78), stack down from 0x0100, code 0x0100-0x0CF5, conversion buffers G 0x0D00 / MG 0x0E00 (row*6+col; code blocks in their free tails: 0x0D60-0x0DAF ocls/ocell/ocrow/oinkx, 0x0E60-0x0EDD raster wait + tilemap commit), bit-reversal table 0x0F00, nibble table 0x1000, class table 0x1200, plotter info 0x1300-0x1AFF (8 pages by IXl), CLIST 0x1B00, ATTRB 0x1C80, X2 0x1F00 (2 bits -> 2 nibbles), BITS 0x1F08, code block 0x1F10-0x1FBA (tile drawing odraw/cpix) |
| RAM page 27 (bank 13 upper, in the .nex), slot 1 | plotter layout tables 0x2000 (1812 bytes, from profile `plotters`); OCCM 0x27A0 (occupied cells per cell row, 22 x 32-bit masks); per back-buffer cell (704 each): TILES 0x2800 (map tile), OBJO 0x2B00 (opaque object code, FF = cell left as drawn), OBJM1/OBJM2 0x2E00/0x3100 (masked object codes as nibbles in draw order), FLAGS 0x3400 (bit 7 map tile known, 6 fixed ink, 5 item group, 4 rainbow group, 0-3 remembered item ink), CTILE 0x3700 (tile assigned this render); tile cache KEYS 0x3A00 (176 x 4), STAMP 0x3D00 (176); RCNT 0x3DC0 (22); classes MCLASS 0x3DE0 (16) / OCLASS 0x3E00 (256) and background override BGOVR 0x3F00 (256), all from the profile `objects` section |
| RAM page 14 (bank 7 first 8K) | TILEMAP: map 0x0000 (40x32 x 2 bytes), tile definitions 0x0A00 (176 x 32 bytes, tile 0 = transparent); zero in the snapshot (checked); slot 3 while hooks write it |
| RAM page 28 (not in the .nex), slot 2 during hooks | shadow map built at render start (20 rows x 64 bytes at 0x0000, copied into the tilemap at the commit) + LASTT 0x0600 (tile number of each cell last render, 704) |
| RAM page 29, slot 2 during the register run | canvas the original plotter draws into (discarded) |
| RAM page 30 (not in the .nex), slot 1 | overflow entries (this render only) |
| RAM pages 32-63 (256K, not in the .nex), slot 1 during lookup | pattern store: 256 sets x 4 ways x 256 bytes; garbage at boot is harmless (a hit needs IX + carry + the whole stream to match) |
| NextReg $1E/$1F (via ports 0x243B / 0x253B) | active video line, read once at the render end (rsafe): commit at once or at the next interrupt |
| Page 26 0x0080-0x0088, 0x0EF0-0x0EF9, 0x1FC0-0x1FFF | V_PEND (commit pending), V_N58 ((58850) at the render end), AY queue state V_AYR/N/O/W, V_AYSP, V_X8; PBUF (object rows +1..+8, +0/+9 zero); AYQ (4 ticks x 16: R0-R13, mask) |
| Page 28 0x0C00-0x0FFF (slot 2 at render start) | X8T: nibble-expansion tables for the tile composer (4 x 256), built at the first render (page 28 is not in the .nex) |
| Ports 0x303B / 0x5B / 0x57 | commit: 0x303B = pattern slot, 64 pattern bytes by OUTI to 0x5B; 0x303B = sprite, 5 attribute bytes by OUTI to 0x57 (low-byte decoded ports: B is free). No NextReg $09 lockstep |
| AY ports 0xFFFD / 0xBFFD | queued player ticks sent one per interrupt (s_int); registers >= 14 straight through |
| NextReg $07 | 3 (28 MHz) for the game frame (limiter), 0 on handler exit |
| NextReg $51/$52/$53 (MMU1-3) | store / layout / object pages while a hook works ($51 page 27, $52 page 28, $53 page 14), back to $FF / 10 / 11 before returning |
| NextReg $6B/$6C/$6E/$6F, $1B/$1C, $4C, $2F-$31 | tilemap: on ($6B = 0x81) at each render-end commit, off (0) on non-play screens and when a render's scroll is not a multiple of 8; clip x 16-143, y 48 .. 47 + (58850) |
| NextReg $7F (user register) | cache flush request: set to 1 by the sprites-off hooks (graphics may change between rounds), cleared by the next render start |
| Tilemap palette | bank 0: 0 transparent, 1 black, 2-8 inks 1-7, 9-15 bright inks 1-7 (Next default ULA levels); bank n (1-15) = bank 0 with pixel 2 = ink index n (one-ink tiles: the map entry's palette offset is the ink) |
| Sprites 0-127, pattern RAM 16K | figures only (patterns 0..V_S-1), up to 128 (V_FMAX) |
| Sprite palette | offsets 0-14: figures (ink 1, outline 2); offset 15 unused |
| Setup (stub, 0xD000) | sprite palette, $4B=0, zero all 16K pattern RAM, hide all, clip Y 16-191, $15=1, tilemap palette (16 banks), $4C=0, $6C=0, $6B=0, tilemap offsets 0 |
| Z80N SWAPNIB (ED 23) | nibble swap in the pixel converter (simulated by rainbow._swapnib; exhaustive self-test) |

## Hardware status
- Runs on the Next (2026-09-28); limiter + commit build bddea69e runs smooth (Dean).

## Hardware checklist - no rainbow border + collectable insides cf017271 (2026-10-19)
1. Rainbows (standing and while thrown): no black edge anywhere; fruit and items still in front of
   the scenery, behind every figure.
2. Collectables: the enclosed inside pixels white (dark items) or black (light items), not the sky;
   name any item that should flip, or stay see-through.
3. Thrown rainbow: drawn where it is thrown (a bug drew it 256 px to the right in an unreleased build:
   check the left half of the screen).
4. Speed and music as in c5e1823d; the diagnostic's colours as before.

## Hardware checklist - no raster wait + music queue c5e1823d (2026-10-19)
1. Speed: game pace steady everywhere incl. the bonus scene (60+ items) and busy rounds; compare
   with the plain rainbow.nex at the start of round 1 (same pace).
2. Music: steady tempo, notes and effects smooth (no bursts / stutter), also while scrolling with
   many enemies; sound effects (jump, rainbow, pickups) still play. Death / round end silence as
   the original.
3. Tearing: none on figures or objects (the commit now happens at the interrupt, bottom border).
   Watch the top play rows in very busy scenes (80+ sprites: the commit then runs into line 16).
4. Objects / collectables / rainbows as in e50733b2 (no border on collectables, border on rainbows);
   objects move with the scenery, no lag of a frame against the background while scrolling.
5. Death / continue / round end / game over / title: no sprites or objects left over.
6. DIAGNOSTIC build (rainbow_sprites_diag.nex): border BLUE band = the deferred commit at the
   interrupt (expected most game frames, short, at the TOP of the border); RED = tiles being built;
   YELLOW = the frame overran; MAGENTA = the frame-start clear of the overrun flag did not take (the
   reading proves nothing that frame). Yellow / magenta stay until the next frame start. Film it if
   slowdowns remain.
7. The earlier random corruption (bffd9357): still there? Where, which border colour.
8. Faults: Fuse "Record from snapshot" on rainbow.z80, autosave off, send the RZX (+ where).

## Hardware checklist - collectables without border + diagnostic build e50733b2 / 8f25bc61 (2026-10-12)
1. Collectables (fruit, cakes, flowers, stars): own colour, NO black line; the background shows around
   them and through their gaps. Rainbows keep the thin black border; player / creatures keep theirs.
2. DIAGNOSTIC build (rainbow_sprites_diag.nex), for the random corruption / slowdowns - film the TV
   (border visible) when it happens:
   - BLUE border band: the commit was waiting for the beam to leave the play area (raster wait);
   - RED band: a new object tile was being built;
   - YELLOW: the last game frame overran (an interrupt came during it: that frame took 4 interrupts
     instead of 3 = a slowdown), until the next frame starts;
   - black: nothing special. The bands show where in the frame it happens (top / bottom border).
   Note per glitch: which colour was showing, and where on screen the corruption was.
3. Compare: does the normal build show the same corruption / slowdowns as the diagnostic one (the
   diagnostic build adds only the border writes)?
4. Everything else as in the bffd9357 checklist below.

## Hardware checklist - objects on the tilemap bffd9357 (2026-10-11)
1. RAINBOWS: yellow with a thin black border, NO black blocks under the arch; the sky / bricks show
   around and under them. Two crossing rainbows: one picture, no square.
2. FRUIT and COLLECTABLES (cakes, flowers, fruit from crushed enemies): in their own colour with a
   black border, on the real background - the four flowers in the castle show the red bricks
   behind them (as after collecting them); no square anywhere.
3. Fruit inside a rainbow: the fruit in front of the rainbow, both visible, no square.
4. Enemies and player in front of everything; stars as before.
5. Pickups: the object disappears, the background stays.
6. Bonus scene (colours cycle): objects change colour with the game, no flicker.
7. Scrolling: objects move with the scenery; nothing over the HUD or below the play area (also while
   the water rises); top and bottom rows clean.
8. Death / continue / round end / game over / title: no objects left over from the play screen;
   they come back when play resumes. A new round / island: objects correct (cache flushed).
9. Enemy tearing: still gone (raster-synced commit as in ab97c76a).
10. Smoothness and music: as in ab97c76a (simulation: 8 long frames in the bonus scene of
    rainbow.rzx, fewer than before).
11. Still open: dark-blue squares on partial tiles (layer B - mask sheet), unchanged here.
12. Faults: Fuse "Record from snapshot" on rainbow.z80, autosave off, send the RZX (+ where).

## Hardware checklist - opaque-item / raster build ab97c76a (2026-10-11)
1. ENEMY TEARING (Dean's three "bugs" photos): enemies and player moving fast left/right, turning,
   jumping: no split or sheared sprites. Watch the busy bonus scene too.
2. Items on SKY / plain background (the red cakes, the four flowers on the castle): no black or
   coloured square - the background of that cell (green curve, castle pattern, sky) shows around
   the item.
3. Items on bricks / on a rainbow: as in eb9836fe (no square; bricks / rainbow pixels kept).
4. Pickups: item disappears, the cell shows its background, no leftover square or sprite.
5. Smoothness and music: as in eb9836fe. In the busiest bonus scenes (60+ items) an occasional
   frame may run long (see timing below) - report if the music or game visibly stutters there.
6. Still OPEN in this build (next build): rainbows partly black; dark-blue squares on partial
   tiles (needs layer B - see the mask contact sheet). Please say whether the black in rainbows
   was also in bddea69e (the build before items).
7. Faults: Fuse "Record from snapshot" on rainbow.z80, autosave off, send the RZX (+ where).

## Hardware checklist - collectables build eb9836fe (2026-10-11)
1. Items on CASTLE BRICKS / platforms: item as a sprite in its own colour with a black outline;
   the bricks of that cell keep their own colour (no yellow square around the item); no gap or
   ghost of the item on the ULA.
2. Items on a RAINBOW (rainbow over or under an item): item in front of the rainbow, the rainbow
   pixels of that cell keep the rainbow colour.
3. Items on SKY / plain background (drawn opaque by the game): item sprite, cell otherwise blank in
   the background colour.
4. PICKUPS: collect several items (walk over them, rainbow-crush enemies so fruit drops and is
   collected): sprite disappears in the same frame as the original item; no leftover sprite.
5. Figures (player, enemies) pass IN FRONT of items; stars stay on the ULA.
6. Scrolling up/down with items on screen: items move with the scenery, no flicker of the cell
   square, nothing at the top/bottom edges or over the HUD.
7. DEATH / CONTINUE / round end / game over screens: no item sprites; items come back when play
   resumes. Title / attract mode.
8. Smoothness and music as in bddea69e (busy scenes with many items).
9. Faults: Fuse "Record from snapshot" on rainbow.z80, autosave off, send the RZX (+ where).

## Hardware checklist - commit build (2026-10-02)
1. No tearing or ghosting when figures move, turn, jump, get hit (watch fast horizontal moves).
2. Death: continue screen, round-end and game-over screens show NO sprites; sprites return when
   play resumes; title/attract mode.
3. Smoothness and music as in the limiter build.
4. Boss spider and busy scenes: all figures complete (a figure staying on the ULA for one frame
   would show clash colours: report where).

## Hardware checklist - limiter build (2026-10-01)
1. Game speed and music tempo steady and the same as the original when NOT busy (compare with
   the plain rainbow.nex at the start of round 1).
2. Busy scenes (moving, many enemies, collectables): no slowdown, music steady.
3. Title, round start/end messages, game over, high-score entry, pause: same timing as original.
4. Controls responsive; no missed or doubled key presses.
5. The NMI-menu speed setting now has no effect on the game (the hooks set it): expected.
6. Items 2-4 of the speed-build list below still hold.

## Hardware checklist - speed build (2026-10-01)
1. Same busy spots as before, MOVING with enemies on screen: compare with 78b9ed99 / 4dce14af
   and the plain rainbow.nex. Expect much less slowdown.
2. Every figure complete and current (no wrong/old frame for even one frame): walking, turning,
   jumping, enemies hit/dying, island change; boss spider facing left and right.
3. No sprite garbage below/right of figures; no stale sprites at edges, top, deaths, game over.
4. Rainbows, stars, collectables, HUD exactly as before; music tempo unchanged.
5. Faults: which build, where, and a video or Fuse RZX.

## Hardware checklist (2026-09-29 build 4dce14af...)
Normal level (Insect Island rounds 1-3):
1. Title + music; game starts; music tempo unchanged.
2. Player and enemies white with black outline, no clash, no garbage below any figure (pattern
   bottom halves: setup zeroes them - garbage there = setup/0x303B problem).
3. Figures facing LEFT and RIGHT both complete (same width) while walking and jumping.
4. No stale sprites at edges, top (below HUD), deaths, HURRY, game over.
5. Rainbows, stars, HUD unchanged; heavy scenes (many enemies + rainbows) no slowdown vs before.
Boss (round 4 spider):
6. Arrival: spider complete while descending.
7. Moving RIGHT and moving LEFT: no missing column (left edge and face half were missing before).
8. Being hit (rainbows on it): no torn/stale blocks; health bar unchanged.
9. Death / gems: sprites removed cleanly, next island loads.
10. If anything differs: rainbow_sprites_fixonly.nex (4132ae00...) isolates fix vs optimisation.
Faults: Fuse "Record from snapshot" on rainbow.z80, autosave off, send the RZX (or a video + which
build).

# GAME / SOFTWARE

## Game facts relied on (full list: "Game facts (detail)" below)
- Renderer 58851..59087 (~1 render per 3-4 frames, DI) blits the play area from back buffer
  0x9F00, then the walker 59504 (called per 8-line band) dispatches each piece at 59539
  JP (IX); every plotter ends JP 59543. Erase = next blit.
- Plotter row control lives in AF'. Stars 60176/60180 overwrite a cell and set its attribute.
- No game logic reads screen pixels (collision uses the attr buffer): no virtual read needed.
- Rainbows and collectables are back-buffer CELL objects (detail below): masked objects 60965
  (codes 1-14 = rainbow pieces, gfx + mask at 0xF600), opaque objects 60839 (codes 1-14 = the same
  rainbow pictures at 0xF700, codes 15-190 = fruit / cakes / flowers), base tiles 60853. Per band the
  blit copies 8 pixel rows + the attribute row, then the walker runs and ends at 59547 with the
  band's screen address in (59522).

## Code (additive)
- nexclash/rainbow.py: Config (colours/tables), RainbowPatch (bank-0 sites + bank-1 music sites
  `sites1`), boot_check (128K), verify (beam model, deferred commits, AYModel), unit_tests (+
  obj_unit_tests, ay_unit_tests), auto, is_rainbow; object model: ObjShadow, object_tables,
  obj_build, obj_compose, obj_fix, obj_truth, tile_row, drop_tile, commit_errors.
- nexclash/rainbow_objects.py: object/tile catalogue for the profile `objects` section.
- docs/profiles/rainbow_islands.json: signature (59504-59521), hook bytes (rom, page, page2-4,
  setup) + symbols, plotter layouts, `objects` classes.
- asm/rainbow_hooks.asm: source; `sjasmplus --zxnext --sym=rb.sym`, then regenerate the profile hex
  (rom/page/page2/page3/page4/setup bins + the `syms` the Python uses, incl. the unit-test control
  labels). 2026-10-12: reassembled = profile hex for all six blocks and 56 symbols.
- nexclash.py: dispatch in cmd_auto, flags --ink/--outline/--class-colours; convert --tail.
- z80tonex.py: 128K tail guard.

## No rainbow border + collectable insides + playthrough sheets (2026-10-19, cf017271)
- BORDER: profile objects "1-14" (rainbow pieces, opaque and masked) and "15-255" border false.
  Thrown rainbow (graphics page 0xC3, OR-only plotters 60105-60130): class colours default
  {"pages": {"C3": 1}, "palettes": {"1": {"outline": "transparent"}}}; CLASSTAB bit 0 = class without
  outline -> store key bit 1 (V_KEY) and nooutl turns the entry's outline pixels (2) into 0. BUG found
  by the verifier's pixel check (sprite pixels vs the original plot; registers and memory passed):
  attr2 was CLASSTAB's byte, so bit 0 (the new flag) became X8 and every thrown-rainbow sprite sat
  256 px to the right. Fix: AND 0xF0 (LEARNINGS 1.4).
- INSIDES: page 25 (in the .nex as bank 12's upper half): FILLM = per opaque code 15-190 the enclosed
  paper (8 rows; profile `fills`, from the game's island graphics, identical on all 7 islands: the 2x2
  groups c..c+3 from 23 joined before the flood), FILLC = per-code override. ocomp's opaque path
  calls ofill: V_FPIX = the fill pixel pair (0x33 = palette pixel 3 of the tile's bank: the contrast
  colour of that ink, Config.tile_palette; 0x11 black / 0xFF white for overrides); odraw ORs it
  under the mask. Unit control: odraw.fc NOP -> inside not drawn, detected.
- Unit control 'no black border' runs on a profile copy with every border on (no object has one
  now; a control that cannot fail proves nothing); its base must pass first.
- SHEETS (PLAYBOOK 3b, Dean 2026-10-19): `python -m nexclash.rainbow sheet RZX... -o PREFIX` ->
  PREFIX_{PLAYER, ISLAND1-7, COLLECTABLES}_{PAINTING_SPRITES, REFERENCE_ALL_SPRITES}.png + layouts.
  Capture by `rzx.trace` (C simulator, the 28 bookmarks + both RZX in ~12 min). Game facts used:
  - objects: 54533 (creature / player record IX, builder D4A8; allocates codes at 54574), 50614
    (the thrown rainbow, C5A8; codes at 50635), 53318 (single pieces); the band lists at 0x6D3C
    are linked through the descriptors (0xB800 + code - 6: gfx, screen offset, next code + plotter);
    the walker reads the code at 59513. Pieces of one object = one figure; a boss's objects
    (graphics in 0x7800-0x7EFF) = one figure.
  - graphics buffers per island: creatures 0x9400-0x9EFF, boss 0x7800-0x7EFF (constant within an
    island) -> colour keys 'I<island>:<addr>'. Fixed: player 0xD662 + 144 k (k 0-7, 24 rows x 6 bytes:
    mask / gfx interleaved, 3 bytes wide), items 0xDB-0xDE, thrown rainbow 0xC3xx.
  - The PLAYER's graphics are SHIFTED IN PLACE (60300: rotate mask + gfx right/left to x & 6; the
    shift now at 0xC676 + n): an address holds other pixels after a move - the old sheet keyed them
    by address and showed corrupted players. Keys 'G<start>.<row>.<byte>' of the unshifted pixel
    (shifted_key); the engine must do the same when it applies painted colours.
  - Coverage (graphics bytes drawn / non-zero bytes of the island's buffer): creatures 53-88%, boss
    14-29%; the rest is either never drawn in the playthrough or not figure graphics (not resolved).
- Not done: read-back of the painted sheets -> rainbow_colours.json, per-pixel colours in the
  piece conversion (keys per island, shifted player keys, per collectable colour in the tile
  composer), `recolour`; verify of islands 3-7 (bookmark verify of the boss rounds running).

## No raster wait + music queue + faster tiles and commit (2026-10-19, c5e1823d)
Profile first (rainbow.rzx 2900 frames, 838 game frames, simulated at 28 MHz, beam modelled from the
frame start at the interrupt, line 248): game itself 1.2 ms avg / 2.4 max per game frame; hooks:
pieces 2.0 / 9.8, render start 2.3 / 10.1, band ends 1.4 / 4.9, render-end commit 2.0 / 4.7, and the
RASTER WAIT 3.4 avg / 10.2 max (in 439 of 838 frames: renders mostly end with the beam in the play
area) - typical frame ~17 ms of the 20 ms budget before real-hardware wait states. Hardware
scrolling would not help (the blit is inside the game's 1.2 ms).
- COMMIT (s_re, alt ROM): never waits. rsafe reads the line L once: commit at once only when L >=
  240 (the frame will miss the interrupt at 248, or the render ended in the first ~4 ms after it) AND
  L + sprites <= 307 (311-line 128K frame: the commit fits before line 16; one line per sprite + 17 for
  the map + margin); otherwise V_PEND = 1 and s_int commits at the next interrupt (line 248, bottom
  border) at 28 MHz - the same displayed frame as a commit at line 176, outside the game frame.
  dcom drops a pending commit when a non-play screen came after the render ($7F set by the
  sprites-off stubs). (58850) is captured at the render end (V_N58) for the clip. Pieces are
  committed top to bottom, so a commit the beam catches up with has done the top rows first.
- COMMIT I/O: patterns by OUTI x 64 (8 x 8 unrolled; 0x5B decodes the low byte, so B is free) instead
  of OTIR; attributes by 0x303B = sprite (bits 6:0; the pattern upload is done) + 5 x OUTI to 0x57
  instead of $34 + 5 NEXTREGs. No $09 lockstep (it would also be needed only for $34 -> 0x57).
- MUSIC: the game ticks its AY player (bank 1 0xD4DE via trampoline 0x5C70) up to 3 times per game
  frame (65225, 65249 via 5C61, 65255): about 50 Hz at 3.5 MHz, but bunched into a few ms at 28 MHz
  then ~50 ms of nothing. All its register writes go through 0xD6D4 (LD BC,FFFD / OUT / LD BC,BFFD /
  OUT / RET; also the silence routine 0xD6F7). Hooks: 0xD4DE opens a tick slot, 0xD6D4 stores the
  write in the slot (registers >= 14 straight out); s_int sends the oldest tick each interrupt (a
  second one when 3+ are queued); a full queue (4) sends its oldest at once. The player still runs
  exactly where it did - game logic and memory untouched; the player has no IN / alternate
  registers / IY (checked by disassembly). In the verifier only one interrupt per game frame
  exists (the RZX's), so most ticks go out early there - the unit test covers the 3-per-frame case.
- TILE COMPOSER (odraw): nibble-expansion tables X8T (page 28, built at the first render) replace the
  bit loop: out = old & ~(m|b) | b & 0x11 | ink & m per byte, empty rows skipped. Same tiles,
  11.4k -> 7.0k T for a dense one-object tile (3.4k fixed cost per tile remains: clear + passes).
- Verifier: beam model (frame start = line 248, then patched T); commits checked where they happen
  (render end or the next 65172 event), dropped commits checked; AYModel = the queue + the
  original's chip state (after each tick sent the chip = the original's registers at that tick's
  close); bank-1 sites with entry-point proofs. Failure keys now always END with '!' (four unit
  checks had 'FAIL! detail' keys that the '!' suffix test could never see).
- Dean's video of diagnostic 71222105 (2026-10-19): blue band short, at the top of the border
  (deferred commit at the interrupt, done well before line 16). YELLOW in long stretches - solid on
  the ROUND 1 READY screen (frames that do almost nothing) and in calm play mostly where no blue
  band shows: taken as a FALSE overrun signal - probably the frame-start clear of $C8 bit 0 ran while
  the ULA INT was still asserted (frames without a deferred commit reach dfst within microseconds of
  the interrupt), so the flag set itself again. Hypothesis, not confirmed. Diagnostic since then:
  dfst (now in the alt ROM, with dfend) waits up to 255 polls for $22 bit 7 = 0, clears $C8, reads it
  back (V_CLRF); dfend shows yellow only when that clear took, magenta otherwise; a deferred commit
  restores the frame's colour (V_BCOL) instead of black. The collected-diamond row below the play
  area in the video is the game's own HUD.
- Not done: tile-build cap per render (offered); DMA (pattern / map copies; must stay clear of the
  interrupt); copper (no); render start fixed cost per tile.
- Approximation: the verifier's beam model runs 1792 T (224 x 8) per line and wraps at 312 lines
  (48K timing); 128K timing is 228 T x 311 lines. It only picks which commit path each render takes
  in the replay (both are checked); the asm's room test uses 311 lines.

## Collectables without border + diagnostic build (2026-10-12, e50733b2 / 8f25bc61)
- Dean: black border on rainbow pieces, characters and creatures only. Profile `objects`: opaque
  15-255 {"border": false} (codes 1-14 stay "rainbow" with border). Collectables: their pixels in
  their ink, everything else in the cell transparent (the map tile shows, also through gaps inside
  the object - Dean chose see-through for now; filling enclosed gaps black is the alternative).
- Dean's report on bffd9357: sprite corruption and slowdowns seemingly at random, not tied to the
  amount on screen; Fuse cannot record the Next build. Suspects: (1) the raster wait (0-10 ms per
  render depending only on where the beam is when the render ends; can push a frame past the next
  interrupt = 4 interrupts instead of 3); (2) bursts of tile composition (up to ~12 ms per render);
  (3) a render ending at lines 0-15 commits at once and can tear the top play rows. Not simulated.
- DIAGNOSTIC BUILD (same code, V_DIAG = 1 set by Python; auto builds rainbow_sprites_diag.nex and
  verifies it on the first 1500 frames): OUT (0xFE) border colour: blue (1) in the raster-wait loop,
  black after it; red (2) around each tile composition (ocompd); frame start (s_lim run -> dfst):
  NextReg $C8 bit 0 cleared, black; frame end (e_hx -> dfend): $C8 bit 0 set = an interrupt came
  during the frame = overrun -> yellow (6) until the next frame start. dfst / dfend are jumped to
  from the ROM stubs and jump back (x_lrun / x_hx): no stack use. Normal build: V_DIAG = 0, no port
  writes (unit-tested).
- Next steps depending on what the video shows: smarter raster wait (wait only when the commit could
  meet the beam; treat a late end at lines 0-15 as "wait"), and/or a limit on new tiles per render.

## Objects on the tilemap (2026-10-11, bffd9357)
Dean's report on ab97c76a: rainbows with black edges and black blocks, fruit / flowers on full
squares; he likes the rainbow border. Survey (both RZX, every cell-drawer call): the object codes
1-14 (masked 60965 AND opaque 60839) are the RAINBOW pieces (arc segments; the 0xF600 masked set
and 0xF700 opaque tiles 1-14 are the same pictures); fruit, cakes, flowers, big 2x2 objects are
OPAQUE overlay codes 15-190 (0xF700 + 8*(code-1)); the previous builds turned the rainbows into
sprites (black outline = the mask-cleared pixels painted black) and never touched the collectables.
Up to 114 object cells (137 objects) on screen at once: too many for sprites next to up to 84
figure sprites -> the Next TILEMAP (cell-aligned 8x8 tiles, in front of the ULA, behind sprites).
Composition order in the game (60633): the first object with code >= 15 opaque (or, if all are
rainbow pieces, the first one opaque when the tile's table bit 7 is clear, else the base tile),
then every further object masked; up to 4 objects in a cell seen (crossing rainbows).
- CELL HOOKS (60853 / 60839 / 60965, own stack): per cell TILES (60853: A; 60839: the map byte at
  BC' - the base tile the game draws after a pickup; verified at every same-map redraw: 0
  different), OBJO (60839 code; codes 0 / 255 or a 'leave as drawn' class -> FF), OBJM1/2 (60965
  codes appended, 4 max, else FF), FLAGS group bits from the class tables, RCNT + OCCM (occupancy),
  CTILE cleared on any change (with the cell's entry in the shadow map and the map on screen).
- RENDER START (obuild): shadow map cleared; every occupied visible cell (OCCM bits; rows 8*kk <
  (58850)) with a known map tile and no FF gets a tile number: KEY = (O, M1, M2, inks). One-ink
  tiles (one group, no fixed ink): pixels 2 = ink, 1 = border, key ink byte 0, the map entry's
  palette offset = the cell's ink index (so the bonus scene's ink cycling (51914) costs no tile
  rebuild). Two groups (rainbow + item): inks in the pixels (rainbow group = the cell's ink, item
  group = the ink remembered while the item was alone in the cell, else the cell's). Tile cache:
  176 entries (KEYS / STAMP, stamps = render counter | 0x80); first the cell's tile of last time
  (LASTT), else 16 probes from 1 + (hash & 127); a miss rebuilds the first probed entry not used
  this render or the previous one (that map is on screen until the commit); none -> CTILE 0, the
  cell stays as drawn. Cells not on screen get CTILE 0.
- TILE (ocomp / odraw / cpix): rainbow-group objects first (opaque, then masked in draw order),
  item-group objects on top; each object: border = 8-neighbours of its pixels inside the cell minus
  its pixels -> 1 (black), pixels -> its ink; earlier objects stay where it draws nothing.
- BAND END (s_bend): the band's object cells with CTILE: the map tile's rows (BGOVR applied; tiles
  >= 128 mirrored through 0xF5xx as 60853) on rows inside the play area, the tile's colour
  (0xF200 + (t|128)) & 127 while the screen attribute = the attribute buffer (a star keeps its ink).
- RENDER END (tcommit, after the raster wait): shadow rows copied into the map (rows 6-25, columns
  4-35), $6E/$6F, clip y 48 .. 47 + N, $6B = 0x81; tilemap off when the scroll was not a multiple
  of 8 (never seen). Sprites-off hooks: $6B = 0 and $7F = 1 (cache flush at the next render start).
- PROFILE `objects` (rainbow_islands.json; tables built by RainbowPatch): per code or range under
  "opaque" / "masked": "group": "rainbow" | "item" (default item), "ula": true (cell left as the game
  draws it), "border": false, "ink": 0-7 + "bright": true (fixed colour); "background": {"tile":
  tile} draws another map tile under objects. Default: opaque 1-14 and masked 1-14 = rainbow.
  New islands: run the objects catalogue on a recording; codes that look wrong get an entry.
- Visual approximations (logic exact): a border pixel is drawn only inside the object's own cell
  (an object touching the cell edge has no border on the neighbouring cell's side); an object
  cell already in the back buffer when the snapshot starts stays as drawn until the game redraws
  it; the item ink in a mixed cell is the one last seen while the item was alone.
- Speed (simulated, 28 MHz): render start avg 2.3 ms (rainbow.rzx 2900 frames), band ends avg 1.4 ms
  per render, commit avg 2.0 ms (incl. the 1280-byte map copy); first attempt (one map per render,
  inks in the tiles) took up to 23 ms per render start - see docs/LEARNINGS.md (hook cost).

## Opaque-item base tile + raster-synced commit (2026-10-11, ab97c76a)
NOTE (later the same day): the "opaque items" here were rainbow pieces; superseded by the tilemap
build above. The raster wait stays.
Dean's hardware report on eb9836fe -> fixes for (1) enemy tearing and (2)/(3) item squares.
- SQUARES: items the game draws OPAQUE (60839, codes 1-14) have no base tile under them - the game
  draws the item tile over a blank cell. Clearing the item's pixels left the blank square. Survey
  (both RZX, 1701 opaque draws): the cell's map tile is the byte at BC' at 60839 for both callers
  (60577: L = tile|128, 60696: C = tile|128), its table bit 7 is always clear; when the game later
  redraws that cell with 60853 at the same scroll the tile is that byte (verifier: 179 / 179 on
  rainbow.rzx, 376 / 376 on rainbownew.rzx; the "other scroll" redraws are cells reused for another map
  row). Now: TILES[cell] = tile at every 60853 / 60839; an opaque item gets CODES = code | 0x40 and
  BATTR = its tile's colour (as 60853 would); the band fix writes the tile's rows (0x8000 + 8*tile,
  tiles >= 128 mirrored through 0xF5xx, exactly as 60853) instead of clearing pixels (ifixo, third
  code block). Record +3 = gfx | 1 for opaque. A masked draw of the same code over an opaque item
  keeps it opaque; anything else -> FF (ULA) as before.
- TEARING: the commit (item + figure sprite writes) ran while the beam was in the play area
  because the hooks lengthen the frame (original handler -> render end: median 0.5-0.9 ms, max 2.4
  ms at 28 MHz; with hooks the commit starts later). Now rwait before the commit reads the active
  video line ($1E/$1F): lines 16-175 (the play area) -> wait until line 176; otherwise commit at
  once. Interrupts stay off. Cost: up to one play-area scan (~10 ms) per render when the render ends
  mid-screen; the commit (avg 1.0 ms, max 5.4 ms) starting at line 176 can run past the interrupt
  (~line 248) in the busiest bonus scenes -> that frame waits one more interrupt (the music keeps
  time from the interrupt; hardware to judge).
- Also: ESTAMP removed (EPAT filled with FF per commit) to free 0x0E60-0x0EFF for the third code
  block; page 27 layout tables now limited to 0x2800 (1812 bytes used).

## Collectables as sprites (2026-10-11)
Dean's decisions: masked sprites with the game's own graphic + mask, the item's own ink, black
outline; no cell square (clear only the item's pixels, keep bricks / rainbow / sky, cell gets its
base tile's colour); items in front of rainbows and scenery, behind all figures; otherwise last
drawn on top.
- The prototype's 58 mismatches (rainbow.rzx 2500 frames, replicated exactly: 485 ok / 58): 36 =
  figures the original plotted over the item at render time (expected); 16 = stale records - the
  item had been overwritten by the full-tile drawer 60839, which the prototype did not track;
  6 = rows below the play area (the prototype checked 8 rows down to y=168, but the play area is
  (58850) = 160 rows). With 60839 tracked and the 160-row limit: 446 ok / 36 figure / 0 other.
- SHADOW MAP (page 27): hooks at the three cell drawers (interrupts off at all three in both RZX;
  no stack; every register incl. F as the original at the resume address):
  - 60853 `87 6F 26 00` -> JP e_bt (resume 60857): base tile A -> CODES = 0, BATTR =
    (0xF200 + (A|128)) & 127 | 128 (the colour the game gives the cell without objects).
  - 60839 `3D 6F 26 00` -> JP e_ov (resume 60843, carry kept for the replaced DEC A): full tile from
    0xF700 + 8*(A-1). A = 1-14 is an item drawn OPAQUE (its base tile has F2 bit 7 clear: plain
    background); A >= 15 another overlay (CODES = 0). Colour: a spawned item (IY != 60699) keeps
    the attribute buffer (the cell's colour before it); a composed one is unknown (BATTR = 0 - the
    cell is blank once the item is removed, so its ink does not matter).
  - 60965 `3D 87 87 87` -> JP e_it (resume 60969; HL kept): masked item A. Codes 1-14 only; first
    item in the cell -> CODES = A (spawned, IY != 60720: BATTR = attribute buffer); the same code
    again keeps it; anything else -> FF = left on the ULA.
  - RCNT = occupied cells per cell row (kept by the hooks) so render start scans only those rows.
- RENDER START (58851, s_rs; every register kept): item list ILIST (<= 80; more stay on the ULA)
  in cell-row order: per visible item cell its column, screen row Y0 = 16 + ((8k - (48782)) mod 176,
  minus 176 when >= 168: lower rows wrap to the top), visible rows (screen row < (58850),
  contiguous j0..j0+n-1), screen address of row j0, gfx, attribute char row + base colour,
  first/last char row, ink index (attribute-buffer ink: 0 -> 1 black, else ink+1, bright +7) and
  a PATTERN CACHE entry: key (gfx, ink, rows) -> hash, 8 probes, else the first entry not used this
  render is rebuilt (page 28; items with the same key share it; invalidated when 0xF600-0xF6DF
  change - GCOPY). Then RFIRST/RLAST: first/last item touching each screen char row. Figures get
  128 - NI sprites. LIST REUSE: no cell hook touched an occupied cell (V_IDIRTY), same (48782) and
  (58850), same graphics -> the list is kept; its cache entries are re-stamped and each item's ink
  is re-read (the game cycles item inks in the bonus scene through 51914, a third attribute-buffer
  writer) - a changed ink re-keys the pattern.
- BAND END (59547 `2A 82 E8` -> JP e_bend, resume 59550): the band's char row R from (59522); items
  RFIRST[R]..RLAST[R]: their rows on R -> screen AND mask AND NOT gfx (the item's masks INCLUDE its
  gfx bits, so AND mask alone would leave the item's ink pixels), their attribute on R -> base
  colour while the screen still shows the attribute-buffer value (a star may have set its own ink).
  Right after the band's blit + attribute copy, so the square never shows on screen (a render-end
  fix would leave it visible for part of a frame on every render).
- RENDER END (59087): item sprites first (sprites 0..NI-1, each distinct cache entry uploaded once
  to the next pattern after the figures', palette offset 15; code block 0x1F20), then the figures
  as before with sprite numbers + NI, then hide total..prev.
- Visual approximations (logic exact): a star drawn into an item cell loses the pixels under the
  item silhouette (the sprite covers them); a cell holding two different objects (or anything but an
  item code from the masked drawer) stays on the ULA as drawn; item cells already in the back
  buffer when the snapshot starts stay on the ULA until the game redraws those cells.
- Counts and cost: see Verification below (max 67 / 72 item sprites per render, up to 116 sprites in all; item hooks avg
  1.2 / 2.7 ms per game frame).
- History of this build: render-end fix -> band-end fix (flicker); per-slot patterns -> keyed cache
  (slot shifts rebuilt every pattern); full list per render -> reuse + ink refresh; whole list per
  band -> RFIRST/RLAST; 64 -> 80 items (67 seen in the bonus scene of rainbow.rzx).

## Commit at render end + sprites off on non-play screens (2026-10-02)
- Tearing/ghosting cause: sprites were changed piece by piece during the render while the beam
  was drawing them; a slot's new pattern also showed at the old position until its attributes
  followed. Now each piece is STAGED (attributes in ATTRB 0x1C80, 5 bytes per sprite; entry in
  CLIST 0x1B00: store page, entry high byte, nspr) and s_re COMMITS all of them in one burst,
  sprite by sprite (pattern OTIR, then its 6 NextRegs), then hides the rest. ~1.6k T (28 MHz) per
  sprite, 84 sprites ~5 ms.
- Store now 4-way (256 sets x 4 x 256 bytes); a miss never evicts an entry used this render (its
  patterns are read at commit); if all 4 are in use (2 pieces in rainbownew.rzx) the piece is
  converted into an OVERFLOW entry (RAM page 30, one 256-byte slot per piece, up to 32 per render,
  never looked up). ULA only after 32 overflows in one render (never expected).
- Non-play screens: sites 65029 (main loop start: CALL 23698) and 65076 (play state ended:
  death / continue / round end / game over: CALL 23643) -> alt-ROM stubs NextReg $15 = 0 (sprites
  off), then the original call. The next commit sets $15 = 1. Interrupts may be on there (main
  loop); the stubs touch no RAM.
- Verify: pixel checks at the piece use the STAGED sprites (rainbow.staged); at render end the
  committed patterns + attributes must equal the staged ones, bottoms zero, $15 = 1, MMU1 back.
  Unit test control: commit writing attribute 4 to the wrong register -> detected.

## Pacing: frame limiter + turbo (2026-10-01, Dean chose steady speed over original slowdowns)
- The WHOLE game frame runs inside the IM2 handler (I=0xB8, vector 0xFDFD -> 65171: PUSH AF;
  LD A,(48768); CP 3; JR NC,65274 (main loop behind: skip); ... CALL 58851 (render) ...;
  65274 POP AF; EI; RET). Interrupts stay disabled during the frame, so the original runs one
  frame per 3 interrupts (95%) or 4 when busy (5%) (rainbow.rzx, 2500 frames). No limiter in the
  game: at 7 MHz the original runs too fast (Dean). Music is updated per game frame, so it slows
  with the game.
- Sites 65172 (3A 80 BE -> JP e_lim) and 65274 (F1 FB C9 -> JP e_hx). s_lim counts interrupts in
  V_TICK: below LIMIT-1 -> return at once (the exit stub); at LIMIT-1 -> tick 0, NextReg $07 = 3
  (28 MHz), continue at 65175 with A = (48768) (F differs: dead, CP 3 follows). e_hx: $07 = 0,
  POP AF, EI, RET. So: game frame every 3rd interrupt at 28 MHz; the main loop (keyboard, HUD,
  queue at 48768) keeps 3.5 MHz and its original timing. The piece hook no longer touches $07.
- Renderer 58851 is called only from the handler (65252), checked.
- Effect: constant original pace (3 interrupts per frame), no slowdowns - including the original's
  own busy-scene slowdowns (agreed). The verifier now measures the whole game frame (original T +
  every hook's extra T, at 28 MHz without wait states): max 23.4 ms (rainbow.rzx) / 25.2 ms (rainbownew.rzx); 8 / 13 game frames over
  20 ms, all with a full item-list rebuild in item-heavy scenes (0 without the item hooks): each
  such frame takes 4 interrupts instead of 3 (one 1/50 s hitch). Real hardware adds 28 MHz wait
  states on top of these simulated times.
- Not reached: interrupts while a bank other than 0 is paged at 0xC000 (the handler code would
  come from that bank, unpatched); neither RZX pages another bank.

## Patch design (speed build, 2026-10-01)
- Sites (bank 0): 58851 render start (sprite counter 0, render stamp +1; item list), 59539 piece
  dispatch, 59543 plotter return, 59087 render end (commit), 59547 band end (item fix), 60853 /
  60839 / 60965 cell drawers (item shadow map), 65172 / 65274 limiter, 65029 / 65076 sprites off.
- Plotter info (profile `plotters`, derived by rainbow.plotter_layouts from the game's own
  plotters): per entry IX: off (= -leftmost column), nspr (= columns/2 rounded up: 2-wide 1,
  3/4-wide 2, OR-only 5/6-wide 3), stream length and a LAYOUT per AF' carry: one byte per
  stream byte = target row*6+column (bits 5-0), bit 6 mirrored (table page 245 = bit reversal,
  checked), bit 7 mask byte. Derived with single-bit streams on 00/FF screens.
- Per piece: stars / unknown IX / no sprites left (V_FMAX) -> original on the ULA. Else hash (IXl,
  carry, first <= 16 stream bytes) -> store set; compare both ways in FULL (IX, carry, whole
  stream). HIT: stamp. MISS: G=0/MG=FF buffers, apply the layout to the stream (G = ink, MG =
  mask|ink), NIBTAB -> patterns into the older way, store key + stream. Both: run the ORIGINAL
  plotter once over canvas 29 for the exact register state, then stage the sprite attributes:
  X = (E&31)*8 - 8*off + 32, Y = cell top + (D&7) + 32 (patterns hold rows from the piece's own
  start row, so D&7 is not in the key).
- Pixel: G=1 ink (index 1); MG=0 outline (index 2, or 0 when transparent); else transparent.
- AF' after the run may hold a canvas byte: verify proves it dies (converged counts).
- Rows >= 8 below the start cell (carry case of the 8-row entries) are dropped, as before; never
  seen in either RZX (the pixel check would fail).
- Measured (28 MHz hook T per piece, 32 cases incl. widest and LEFT4): hit avg 9.2k (worst 10.2k),
  miss avg 35.9k (worst 40.0k); store hits 91% on rainbow.rzx 2000 frames -> ~11.6k average,
  vs 28.1k every piece in 4dce14af and ~22k average in 78b9ed99. Max 38 sprites per render seen.
- History: spider fix (LEFT4 = 59906/59951/59996/60041 write E-3; now off = 3 from the table);
  4dce14af optimisation (pre-zeroed pattern bottoms, SWAPNIB); 78b9ed99 32-entry pattern-RAM
  cache (hits 48-67%: vertical scrolling changes every piece's band split -> misses).

## Verification (software)
- No raster wait + music queue + faster tiles / commit c5e1823d / diagnostic 71222105 (2026-10-19,
  RELEASE): rainbow.rzx 7178 frames, 11865 pieces, 2212 commits (716 at once / 1499 deferred / 3
  dropped on a non-play screen), 34673 AY writes, 6681 ticks queued, 36119 object tiles -> IDENTICAL;
  rainbownew.rzx 11799 frames, 29314 pieces, 3525 commits (170 / 3360 / 4), 16473 AY writes, 10757
  ticks, 139988 object tiles, overflow entries 2 -> IDENTICAL; chip = original after every tick sent;
  diagnostic build IDENTICAL on the first 1506 frames; unit tests PASS (19 object controls + AY queue
  1040 ticks + its control + commit at once / deferred + its control); boot OK all three .nex. Whole
  game frame max 18.1 / 22.9 ms, frames over 20 ms 0 / 2 (e50733b2: max 21.4 / 24.8, 9 / 16 - and
  those figures did not yet include the raster wait, avg 3.4 ms).
- No-border + diagnostic build e50733b2 / 8f25bc61 (2026-10-12, RELEASE): rainbow.rzx 7178 frames, 11865 pieces,
  26528 cell hooks, 36119 object tiles -> IDENTICAL; rainbownew.rzx 11799 frames, 29314 pieces, 49707
  cell hooks, 139988 object tiles -> IDENTICAL; diagnostic build IDENTICAL on the first 1506 frames of
  each; unit tests PASS (18 negative controls detected); boot OK all three .nex. Frames over 20 ms
  9 / 16, max 21.4 / 24.8 ms.
- Objects-on-tilemap build bffd9357 (2026-10-11, RELEASE): rainbow.rzx 7178 frames, 11865 pieces,
  26528 cell hooks, 36119 object tiles (max 114 per render), 43621 band ends, opaque objects 717
  (same-map redraws 300 = stored tile / 0 different) -> IDENTICAL; rainbownew.rzx 11799 frames, 29314
  pieces, 49707 cell hooks, 139988 object tiles (max 110), 70579 band ends, opaque objects 3152
  (677 / 0) -> IDENTICAL; object model = the game's back buffer for 36773 / 149087 object cells;
  unit tests PASS (17 negative controls detected); boot OK both .nex. Timing: whole game frame max
  21.5 / 24.8 ms, frames over 20 ms 9 / 17 (ab97c76a: 9 / 15).
- Opaque-item / raster build ab97c76a (2026-10-11, RELEASE): rainbow.rzx 7178 frames, 11865 pieces,
  26528 cell hooks, 13558 item sprites, 289 opaque items, same-scroll redraws 179 = stored tile /
  0 different -> IDENTICAL; rainbownew.rzx 11799 frames, 29314 pieces, 49707 cell hooks, 67570
  item sprites, 1412 opaque items, same-scroll redraws 376 / 0 -> IDENTICAL; unit tests PASS incl.
  opaque render paths, raster wait (6 start lines) and 10/10 item controls; boot OK both .nex.
  Timing: commit avg 1.0 / 2.0 ms, max 5.4 / 6.2 ms; game frames over 20 ms 9 / 15 (0 without the
  item hooks) - the raster wait adds to these on hardware (not simulated).
- Collectables build eb9836fe (2026-10-11, RELEASE): rainbow.rzx 7178 frames, 11865 pieces,
  26528 cell hooks, 43621 band ends, 13558 item sprites (max 67 per render, 104 sprites in all) ->
  IDENTICAL; rainbownew.rzx 11799 frames, 29314 pieces, 49707 cell hooks, 70579 band ends, 67570
  item sprites (max 72 per render, 116 sprites in all), overflow entries 2 -> IDENTICAL; item rows
  as modelled on the original screen 105453 / 528330, under a figure 3011 / 12178, other 0; unit
  tests PASS: 216 cell-hook cases, 4 render paths (start, 22 bands, end), list reuse + ink
  refresh, 8 item controls detected (overlay not clearing, carry not restored, mask not applied,
  ink as outline, pattern never built, rows of other bands fixed, inks never refreshed, figures
  over the item sprite numbers); the two repaired figure controls detected 39/40 each; boot OK
  both .nex.
- Commit build bddea69e (2026-10-02, RELEASE): rainbow.rzx 11865 pieces, 2215 commits = staged,
  sprites-off 3 -> IDENTICAL; rainbownew.rzx 29314 pieces, max 84 sprites, 3530 commits,
  sprites-off 5, overflow entries 2 -> IDENTICAL; unit tests PASS incl. commit control (attr 4 to
  the wrong register detected); boot OK both .nex. (Found 2026-10-11: since this build the figure
  "negative control" and "store stale-pattern control" were n/a on every state - they read the
  committed attributes, which are only staged at piece time. Now read from the staged state.)
- Limiter build cbb5a1d4 (2026-10-01, RELEASE): rainbow.rzx 11865 pieces, 2216 game frames
  (limiter entry + handler exit checked each) -> IDENTICAL; rainbownew.rzx 29314 pieces, 3530
  game frames -> IDENTICAL; unit tests PASS incl. limiter (skipped interrupt = original exit,
  running frame = original at 65175 + 28 MHz, control 'skip removed' detected); boot OK.
- Speed build 7559f940 (2026-10-01, RELEASE): rainbow.rzx 11865 pieces, max 62 sprites/render,
  store hits 93% -> IDENTICAL; rainbownew.rzx 29314 pieces, max 84 sprites/render, hits 94% ->
  IDENTICAL; unit tests PASS (layout vs plotter 66 cases + corrupted-layout control; store hit /
  changed-stream miss / garbage store; controls: compare removed 28 detected, stale patterns 39
  detected; LEFT4 96; edges 200; last sprites / passthrough 40 each); boot OK both .nex.
- rainbow.rzx: 7178 frames, 11865 pieces, max 27/render -> IDENTICAL
- rainbownew.rzx: 11799 frames, 29314 pieces, max 30/render -> IDENTICAL
- --outline transparent on rainbow.rzx -> IDENTICAL (outline drops counted)
- Unit tests (40 states): edge columns, last slot, 32-piece passthrough, negative control,
  class colour; window vs all 35 plotter extents (control: old window misses exactly LEFT4);
  96 synthetic LEFT4 pieces on real gfx at columns 3/16/28 (control: old window detected on every piece with pixels in E-3: 76/76 on rainbownew states);
  SWAPNIB self-test + SWAPNIB-as-NOP control; setup zeroes pattern RAM (control: zero loop
  without OUT detected); pattern cache: stream-length table = simulation, 40 repeat pieces hit
  (no upload, registers, pixels), 40 changed-stream pieces miss; controls: stream compare
  patched out -> stale image detected 39/39 where the changed byte draws differently (1 n/a),
  stale pattern data on a hit detected 39/39 with pixels (1 n/a) -> PASS
- Cache build 78b9ed99 (2026-09-30): rainbow.rzx 11865 pieces, cache hits 67% -> IDENTICAL;
  rainbownew.rzx 29314 pieces, max 30/render, hits 48% -> IDENTICAL; boot OK both .nex
- Boot sim both .nex OK. Known non-game case: 6-wide piece at column >= 27 wraps on the ULA,
  sprite clips.
- What the item verification checks (rainbow.verify, every event of the replay): each cell hook =
  original (all registers incl. F, memory) and the page-27 shadow map = the Python model
  (ItemShadow); render start = original, item list + page-28 patterns + count + figure limit =
  model; every band end = original (registers, memory) and its screen writes = the model's for that
  char row; render end: no screen writes, every item row / attribute was on a band this render,
  item sprites 0..NI-1 = model (attributes, committed pattern = item graphics), figures at NI.. =
  staged; and the model itself against the ORIGINAL screen: every item row shows the item's
  pixels unless the original plotted a figure there during that render.

## Open - game / software
0. NEXT (Dean's eb9836fe report item 5): (a) rainbows partly black: done in bffd9357 (rainbow pieces
   were the codes 1-14; now tiles with a 1-pixel border). (b) dark-blue squares on partial tiles = tiles with NON-bright blue paper (colours 0x0A red,
   0x0C green, 0x0F white ink; 31 distinct tiles in both RZX) next to bright-blue sky (0x4F):
   layer B = a tilemap (or sprites) behind the ULA showing the sky, ULA paper made transparent
   on those cells, paper INSIDE the object black. Proposed inside masks: rainbow_B_mask_sheet.png
   (rule: paper between ink pixels in its row or column) - waiting for Dean's review. The tilemap
   now exists: B tiles can go into the same map with attribute bit 0 = 1 (ULA over the tile) and
   ULA paper made transparent there - needs a free tile budget (176 shared) and a palette plan.
   Guide r3 review 2026-10-19 (LEARNINGS 1.5): per-tile "ULA over" (attribute bit 0) is ignored
   while $6B bit 0 = 1, and tcommit writes $6B = $81 - layer B needs $6B = $80 (the current tiles
   all have bit 0 = 0, so the picture is otherwise unchanged). Alternative for "paper made
   transparent": ULA paper palette entries (16-31) are separate from inks, so the one paper colour
   to see through can be set equal to the global transparency $14 without touching inks.
1. Revisions/optimisations: 2026-10-19 build done: no raster wait (instead of (d)), OUT/OUTI commit
   ((a) without lockstep), faster tile composer, music queue. Remaining candidates from the 2026-10-19 research (LEARNINGS 1.5; all documented, untested; each needs the
   simulator taught first and a hardware A/B):
   (a) piece loop: 5 NEXTREGs + $34 per sprite (~180 T) -> simplest: NextReg $09 bit 4 (lockstep)
       in setup, keep the loop, replace the 5 NEXTREGs by OUT (C),r to port $57 (~77 T per sprite;
       LEARNINGS 1.5); or two passes + one OTIR of all attributes (~105 T). Pattern OTIR -> unrolled
       OUTINB (16 vs 21 T/byte, 64 bytes per piece).
   (b) hide loop (.hide): NEXTREG $34 once, then NEXTREG $78,0 per sprite.
   (c) tcommit's 20 x 64-byte LDIR (~27,000 T): keep full 80-byte rows in the shadow and copy the
       1,600 bytes with one zxnDMA transfer (~6,400 cycles); place it away from the ULA interrupt
       (~line 248) because a DMA hides the interrupt pulse.
   (d) rwait busy-polls up to 160 lines: double-buffer the map in bank 7 and let a copper list
       (WAIT 176 / MOVE $6E / HALT, mode 11) flip the base each frame; the CPU only rewrites the
       MOVE's value byte. COST: bank 7 holds only 8K, so a second 2,560-byte map takes 80 of the 176
       tile definitions (96 left) - only worth it with (f) or if fewer tiles suffice.
   (e) tilemap switched off when the scroll is not a multiple of 8: follow it with $31 (pixel
       scroll) instead; (f) dedupe tile definitions by mirror / rotation (attribute bits 3:1);
       512-tile mode does NOT help (the limit is bank 7's 8K, not the 256 index range).
2. Later islands: banks 3/4/6 never paged in either RZX; need a recording past island 1 (item
   graphics change there: GCOPY invalidation is unit-proven only through the model).
3. Colours - Dean's decisions (2026-09-30): player stays WHITE (black outline); stars stay as
   now; fruit and collectables keep their own individual colours exactly as now (the ink the
   cell plotter sets) - done 2026-10-11 (palette offset 15). Per-class colours: map empty.
   Catalogue (2026-09-30, rainbow.rzx 600 frames): player = pages D6-D9, stars = DC, enemies =
   runtime buffer 95-98 (the same page holds a different enemy per island) -> trace the routine
   that copies enemy graphics into 0x9500 and key the colour on its source.
4. Headroom: 84 figure sprites, 67 items, 104 sprites in all seen; figures beyond 128 - items fall
   back to the ULA, items beyond 80 stay on the ULA as drawn.
5. identify.py / signatures.json entry (auto detects via rainbow.is_rainbow; `identify` says unknown).
6. Boss RZX wanted (Fuse "Record from snapshot", autosave off): would verify LEFT4 against real
   play and the boss's rows/piece count.
7. A pickups RZX (castle bricks, rainbow, sky; enemies turned to fruit and collected) would put
   the spawn paths (60543 -> 60839 / 60965) through more cases; both RZX already reach them.


## Game facts (detail)
- Code in bank 0 at C000; bank 1 = music (0xD4DE-0xD86A) via trampoline 0x5C70 (7FFD 17 then 16
  every frame, DI, SP=0). ROM bit always 1, bit 3 never. Banks 3/4/6/7 never paged in either RZX
  (probably later islands).
- IM2 I=0xB8, vector 0xFDFD -> JP 65171. Main stack top 0xFDF9, low-water 0xFDB7. Printer buffer
  0x5B07+ = code. ROM reads only 0x0000, 0x0506-050F, 0x0708+, font; never 0x386E-0x3CFF.
- Back buffer 0x9F00 (176x32, circular, offset 48782) + attrs 0xB500; blit 59210 by stack POPs.
  Write-first in both RZX -> tail site.
- Renderer 58851..59087, ~1 render per 3-4 frames, DI throughout.
- Walker 59504 per 8-line band from the blit; list IY=0x6D3C (continues across calls); code ->
  descriptor 0xB800+code-6; POP IX from 0xF3xx; 59539 LD H,245 / JP (IX); all plotters end JP 59543.
  Walker entered with SP=59567 (the CALL writes the operand of JP at 59564).
- Plotters: masked AND/OR, zig-zag, table page 245. Rightwards 59699/59741/59783/59825 (heights
  8/6/4/2); leftwards 59717/59759/59801/59843; OR-only 60105-60130 (1-6 bytes wide, 8 rows, saves
  D in C); stars 60176/60180 overwrite 8x7 and set cell ink (L=70/66), code ends 60218.
- Self-modified operands: 59522, 59565, 59085 (keep out of signatures/patch sites).
- No logic reads screen pixels; tile collision reads the attr buffer (51909, 60603).
- Figures take the cell ink (mostly attr 79); 23% of figure pixels are mask-only.
- 59111 = rising-water attribute fill; 24669 = HUD bold text (~22 chars/render).
- Player 24 rows (gfx 0xD6-0xDA); enemies 16-18 rows (0xDC-0xDE static, 0x9500-0x98FF runtime
  buffer); worst 30 pieces per render.
- Dispatch table 0xF300 (35 plotter targets). Zig-zag plotters 2/3/4 bytes wide (rightward rows
  AND/OR, leftward rows mirrored through table page 245); entries per height 8/6/4/2; the
  leftward-row entries run E..E-(w-1): 2-wide E-1, 3-wide E-2, 4-wide (59906/59951/59996/60041)
  E-3. OR-only 60105-60130 write E..E+5. Leftward entries = figure facing left. The 4-wide
  leftward entries are used by the boss spider (Insect Island round 4) only.
- Play area = (58850) rows (160; less while water rises: 59087+ paints the rows below), screen
  rows 16..; screen row y shows back-buffer row ((48782) + y) mod 176, so 16 buffer rows are off
  screen. (48782) was a multiple of 8 at every render of both RZX. Screen char row 2+kk takes its
  attributes from buffer row ((48782)/8 + kk) mod 22.
- Per band the blit writes 8 rows, copies the attribute row (59338), runs the walker; the walker's
  list end 59547 advances (59522) = the band's screen address (0x4040 = char row 2) to the next.
- Cell drawer 60633 (composition, DI) and 60543 (spawn into a drawn cell), both end JP (IY):
  a back-buffer cell = 0x9F00 + 256*k + col (k = 0-21), 8 rows at +32. Base tile 60853 (A = tile;
  gfx 0x80xx, codes >= 128 mirrored via 245); full tile 60839 (0xF700 + 8*(A-1)): codes 1-14 there
  are RAINBOW pieces drawn opaque (base tile's table bit 7 clear = plain background), >= 15 the
  collectables (see CELL OBJECT CODES below); masked object 60965 ((cell AND mask) OR gfx, (mask, gfx) pairs at 0xF600 + 16*(A-1), codes 1-14
  seen; the masks contain the gfx bits; 0xF700 tiles = the 0xF600 gfx). Object lists: pages
  0x71 (next) / 0x72 / 0x73 (code). No other writer of the back buffer in either RZX.
- Cell attribute (attr buffer 0xB500 + 32k + col): no objects -> (0xF200 + (tile|128)) & 127;
  composed with objects -> paper/bright of that entry + ink 6 (codes < 19) or table 50823 (>= 19),
  ink = paper -> 7; spawned object (60583) -> old paper + ink 0 (7 on black paper). Item inks seen:
  yellow / bright yellow, white, a few others.
- CELL OBJECT CODES: 1-14 (masked 60965 = 0xF600 pairs, and opaque 60839 = 0xF700 tiles 1-14, the
  same pictures) are RAINBOW pieces; collectables (fruit, cakes, flowers, 2x2 objects) are opaque
  60839 codes 15-190 (0xF700 + 8*(code-1)). Look at the graphics before naming a code range - two
  builds turned the rainbows into sprites and left the collectables alone.
- Composition (60633): the first object with code >= 15 drawn opaque (or, all rainbow pieces: the
  first opaque on a plain tile (F2 bit 7 clear), else the base tile), then every further object
  masked; up to 4 objects per cell seen. Cell attribute: from the LAST object (ink 6 for codes < 19,
  else table 50823 by object slot). Spawn (60543) draws one object into a drawn cell (60583 colour).
- Opaque objects are drawn over a BLANK cell: no base tile under them. The cell's map tile is the
  byte at BC' at that moment (all callers 60550 / 60577 / 60696); 60853 redraws the cell with that
  tile from the same map byte (BC' address + scroll; a new round can reuse the scroll value with a
  new map address). Keep a tile per cell to restore the background under an object.
- Up to 114 object cells (137 objects) on screen at once (rainbow.rzx bonus scene / rainbownew):
  too many for sprites next to the figures; the cell-aligned tilemap layer fits.
- Map tile colours (both RZX): sky 0x4F (bright blue paper); full bricks 0x42 (bright red on
  black); PARTIAL tiles 0x0A / 0x0C / 0x0F have NON-bright blue paper -> the dark-blue squares
  next to the bright sky (original behaviour). Red/yellow-paper tiles (0x16, 0x56) are scenery.
- After a death (65076) routines at 23309 / 24678 / 23304 write the screen before the next render.
