# Rainbow Islands (Ocean, 128K) - engine `rainbow`
Date 2026-10-11. Engine `rainbow`. Status: RZX-verified identical; RUNS ON HARDWARE (Dean,
2026-09-28). 2026-09-29: boss-spider fix + pattern-upload optimisation (hardware: runs, better;
busy scenes slower than the original). 2026-09-30: pattern cache 78b9ed99 (hardware: no visible
gain, slow when moving with enemies). 2026-10-01: SPEED BUILD - direct conversion + 256K
pattern store + sprites per piece 7559f940 (hardware: still slower than the original, music
slows). 2026-10-01: FRAME LIMITER + TURBO cbb5a1d4 (hardware: very smooth; minor tearing /
ghosting; sprites stay on the death/continue screens). 2026-10-02: RENDER-END COMMIT + sprites
off on non-play screens bddea69e (hardware: smooth, runs). 2026-10-11: COLLECTABLES AS SPRITES
(below) - hardware test pending.

Reference: reference/rainbow.z80, rainbow.rzx, rainbownew.rzx (Dean's; to be uploaded).
Tools: nexclash/rainbow_catalogue.py (figure catalogue for colours; fixed 2026-10-11 to read the
profile's `plotters` table - it still read the removed `stream_len`); tools/rainbow_items_proto.py
(the collectables prototype, kept for reference).

## Deliverables
| File | MD5 |
|---|---|
| rainbow_sprites.nex (collectables as sprites + everything below) | eb9836fe60a70df02087920603c673b4 |
| (limiter + render-end commit + sprites off on non-play screens; runs on HW) | bddea69edaf6cf0a83dba8633c8f6618 |
| (limiter build, tearing) | cbb5a1d4ba4e84cec40191d3a3259f5a |
| (speed build without limiter) | 7559f940bb72211456b3ec53a0bdff60 |
| (pattern cache v1, 32 entries) | 78b9ed99ab714ef77024f84558987441 |
| (fix + optimisation, no cache: A/B for speed) | 4dce14afce8977fe39086923328a5e12 |
| (fix only, for hardware A/B: rainbow_sprites_fixonly.nex) | 4132ae00ce87b2e046859cd89344ecd3 |
| (previous, spider column missing) | 0c191d94d5c3291e96f282cc6b1e4984 |
| rainbow.nex (plain, tail 0x9F00) | 7ac543fb51c7a3c4137778eeb3cdc175 |

Rebuild (RELEASE, ~51 min): `python nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx --no-record`
Iterate (~15 min): `python nexclash.py auto rainbow.z80 --rzx rainbow_stripped.rzx --no-record --quick 2000`
(2008 frames, 4518 pieces, 1996 item sprites + unit tests; levels: docs/BRIEFING.md C3b)
Options: `--ink white|#RRGGBB`, `--outline black|blue|transparent|#RRGGBB`, `--class-colours map.json`
(class palette offsets 0-14; offset 15 is reserved for the item sprites).
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
  on top (guide r3 p.89). Items take the lowest numbers, figures follow: figures always in front.

## Next resources used
| Resource | Use |
|---|---|
| Alt ROM image 1, 0x386E-0x3903 | entry/exit stubs + register block (all $FF in the 48K ROM; game never reads it) |
| RAM page 24 (bank 12) | alt ROM copy source (stub fills alt ROM at boot) |
| RAM page 26 (bank 13), slot 0 during hooks | state 0x0000 (vars to 0x99; RFIRST 0x60 / RLAST 0x78 per char row), stack down from 0x0100, code 0x0100-0x0CAB, conversion buffers G 0x0D00 / MG 0x0E00 (row*6+col; EPAT 0x0D60 / ESTAMP 0x0E60 in their free tails), bit-reversal table 0x0F00, nibble table 0x1000, class table 0x1200, plotter info 0x1300-0x1AFF (8 pages by IXl), CLIST 0x1B00, ATTRB 0x1C80, item nibble expansion EXP 0x1F00 (32 bytes), second code block 0x1F20-0x1FF4 (item commit) |
| RAM page 27 (bank 13 upper, in the .nex), slot 1 | plotter layout tables 0x2000 (1812 bytes, from profile `plotters`); ITEM SHADOW MAP: CODES 0x3000 (704 cells), BATTR 0x3300, item list ILIST 0x3600 (80 x 16), item graphics copy GCOPY 0x3C00 (224), row counts RCNT 0x3D00 (22), pattern cache keys PKEYS 0x3E00 (128 x 4) |
| RAM page 28 (not in the .nex), slot 1 | item pattern cache, 128 x 64 bytes (entry e at 0x2000 + 64*e; written before read) |
| RAM page 29, slot 2 during the register run | canvas the original plotter draws into (discarded) |
| RAM page 30 (not in the .nex), slot 1 | overflow entries (this render only) |
| RAM pages 32-63 (256K, not in the .nex), slot 1 during lookup | pattern store: 256 sets x 4 ways x 256 bytes; garbage at boot is harmless (a hit needs IX + carry + the whole stream to match) |
| NextReg $07 | 3 (28 MHz) for the game frame (limiter), 0 on handler exit |
| NextReg $51 (MMU1) | store / layout / shadow / item page while a hook works, back to $FF (alt ROM) before returning |
| Sprites 0-127, pattern RAM 16K | per render: item sprites 0..NI-1 (one pattern per distinct cache entry, numbered from V_S), then figure sprites NI.. (patterns 0..V_S-1); figures limited to 128 - NI (V_FMAX), the rest passes through to the ULA |
| Sprite palette | offsets 0-14: figures (ink 1, outline 2); offset 15: item sprites (1 black, 2-8 ink 1-7, 9-15 bright ink 1-7, Next default ULA levels) |
| Setup (stub, 0xD000) | sprite palette, $4B=0, zero all 16K pattern RAM, hide all, clip Y 16-191, $15=1 |
| Z80N SWAPNIB (ED 23) | nibble swap in the pixel converter (simulated by rainbow._swapnib; exhaustive self-test) |

## Hardware status
- Runs on the Next (2026-09-28); limiter + commit build bddea69e runs smooth (Dean).

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
- Collectables are back-buffer CELL objects (detail below): masked items 60965 (codes 1-14, gfx +
  mask at 0xF600), opaque items 60839 (same codes, 0xF700 tiles), base tiles 60853. Per band the
  blit copies 8 pixel rows + the attribute row, then the walker runs and ends at 59547 with the
  band's screen address in (59522).

## Code (additive)
- nexclash/rainbow.py: Config (colours/tables), RainbowPatch, boot_check (128K), verify,
  unit_tests (+ item_unit_tests), auto, is_rainbow; item model: ItemShadow, items_list,
  items_fix, item_record, item_attrs, item_pattern.
- docs/profiles/rainbow_islands.json: signature (59504-59521), hook bytes + symbols.
- asm/rainbow_hooks.asm: source; `sjasmplus --zxnext --sym=rb.sym`, then regenerate the profile hex
  (rom/page/setup bins + the `syms` the Python uses, incl. the unit-test control labels).
- nexclash.py: dispatch in cmd_auto, flags --ink/--outline/--class-colours; convert --tail.
- z80tonex.py: 128K tail guard. 

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
1. Revisions/optimisations: wait for Dean's list; re-verify both RZX, compare MD5s.
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
6. Boss RZX wanted (Fuse "Record from snapshot", autosave off): would verify LEFT4 against real
   play and the boss's rows/piece count.
5. identify.py / signatures.json entry (auto detects via rainbow.is_rainbow; `identify` says unknown).
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
  are ITEMS drawn opaque (base tile's table bit 7 clear = plain background), >= 15 other overlays;
  masked item 60965 ((cell AND mask) OR gfx, (mask, gfx) pairs at 0xF600 + 16*(A-1), codes 1-14
  seen; the masks contain the gfx bits; 0xF700 tiles = the 0xF600 gfx). Object lists: pages
  0x71 (next) / 0x72 / 0x73 (code). No other writer of the back buffer in either RZX.
- Cell attribute (attr buffer 0xB500 + 32k + col): no objects -> (0xF200 + (tile|128)) & 127;
  composed with objects -> paper/bright of that entry + ink 6 (codes < 19) or table 50823 (>= 19),
  ink = paper -> 7; spawned object (60583) -> old paper + ink 0 (7 on black paper). Item inks seen:
  yellow / bright yellow, white, a few others.
- After a death (65076) routines at 23309 / 24678 / 23304 write the screen before the next render.
