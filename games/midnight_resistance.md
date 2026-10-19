# Midnight Resistance (Ocean 1990, 128K) - engine `midres`
Updated 2026-10-13. Engine `midres` (nexclash/midres.py, asm/midres_hooks.asm,
docs/profiles/midnight_resistance.json; after any .asm edit `python tools/asm2profile.py
midnight_resistance`). Tool-chain canary stage 2 (`selftest.py --canary`; record "canary": 2,
quick verify 300 frames): keep it building and passing on the latest tools. Status: RZX
IDENTICAL, unit + interrupt checks PASS; e8f0ece9 RUNS ON A REAL NEXT (Dean, 2026-10-13; detailed
checklist not yet reported).

Reference (private repo, specnext/reference/midnight_resistance/):
Midnight_Resistance_1990_Ocean_128K.z80 (67bf05d356d51b2b402d88c5f0cdfb21),
Midnight_Resistance_1990_Ocean_128K.rzx (b75ecd5f60c3ec67fe463a0aa606f6a1; Dean 2026-10-13, Fuse,
8 autosave snapshots, 4,690 frames: title, level 1 to the end-of-level tank, game over, name entry).
Midnight_Resistance_1990_Ocean_128K_V2RZX.rzx (3e0fa52ae2fbf9fbae62cebb70b83190; Dean 2026-10-13,
Fuse, 47 autosave snapshots, 11,756 frames: more of level 1, the shop, weapons, more player poses).
Selftest names them midnight_resistance.z80 / .rzx / _v2.rzx (docs/records/midnight_resistance.json).

    python nexclash.py auto midnight_resistance.z80 --rzx midnight_resistance.rzx --no-record   (~20 min)
    iterate: --quick 300 (~1 min)

| Output | MD5 | Status |
|---|---|---|
| midnight_resistance.nex (plain, tail 0x7B7E) | 17239acaaf67b0f8011478053e17829d | built; hardware untested |
| midnight_resistance_sprites.nex (altrom + pages 26 / 27, every figure, shop, Dean's painted colours) | 670f94034af175ed56df97f8cdb1ef29 | 2 RZX IDENTICAL; tests OK on hardware (Dean, 2026-10-14; a4fb69a2 before it also OK) |

## Snapshot (0b)
128K, 7FFD=0x10 (ROM 1, bank 0, normal screen), PC 0x739E (RAM, title/attract), IM 2 I=0xFE ->
vector 0xFFFF (JR via 0x0000, reads ROM byte 0), SP 0x7BDE, EI. No BASIC loader running (the
BASIC area holds the loader line only). The RZX starts from a different moment (its own SZX, PC
0xFFFF): bank 5/0/2/7 differ from the .z80, banks 1/3/4/6 identical.
- Paging: only 7FFD 0x10 and 0x17 seen (ISR pages bank 7 for the AY music at 0xE000-; ports at
  32713/32731/58689/58694). Banks 1, 3, 4, 6 never paged in the RZX (later levels' data: not covered).
- ROM reads: 0x0000 (IM 2 vector JR) and the font 0x3D00-0x3FFF only -> altrom is possible
  (hooks outside 0x3D00-0x3FFF as always).
- Plain tail: 80 bytes 0x7B7E-0x7BCD below SP; write-first in the RZX and untouched in a 600-frame
  free run of the .z80 (scan) -> safe.

## Engine (2-3): back-buffer composer, full redraw every game frame
- Game frame = one blit, every 4-9 TV frames (mostly 5; ~10 fps).
- Back buffer pixels 0x5B00-0x6AFF: 128 lines x 32 bytes, linear (line y at 0x5B00+y*32); attrs
  0x6B00-0x6CFF (16 rows x 32). Columns 0-2 and 29-31 are off-screen margins (figures enter there).
- Background renderer writes pixels at 0x883E / attrs at 0x884E; ALL background writes come
  before the first figure plot of the frame (checked over the whole RZX).
- Blit 0x8797 (CALL per char row from 0x8740.., unrolled LDI x26 pixels 0x879A-0x87CC, attrs
  0x87DD-0x880F, EXX between): screen columns 3-28 (x 24-231), rows 0-15 (y 0-127). HUD below
  (rows 16-23) drawn directly to the screen (0x8111, 0x8241, 0x825D).
- Buffer address: 0x7EC1 (D = line, E = x pixel, column = E/8; byte-aligned plots); attr
  address 0x7EA9.
- Nothing but the plotters and the blit reads the back buffer -> no virtual read needed.
- Interrupts are ON at every plot entry (IFF=1 x 7,992); the ISR keeps IX (saved), uses 20 bytes
  of stack, pages 7FFD -> hooks: SP with >= 22 free bytes, never IX/IY/I/IFF, no 7FFD.

### Figure plotters (byte-aligned, masked: (buf AND mask) OR gfx unless noted)
| Entry | Kind | Notes |
|---|---|---|
| 0x9E3F | 32-px wide masked, A = frame (table 0x9B36, bit 7 = mirror; 5-byte entries 0x9BA5: size, offsets), DE = pos | inner 0x9EF7 (normal) / 0x9F50 (mirrored via bit-reverse table 0xFDxx); self-modifies row count 0x9EF6/0x9F4E and the OR opcodes (0x9E0C sets 0xB6; 0x9E2C writes the mirrored slots) |
| 0x97E1 | masked, B bytes x 2C rows, zig-zag rows; 0x97A7 = vertical flip variant | |
| 0x9813 | horizontally mirrored masked (table 0xFDxx) ; 0x97C4 = flip variant | |
| 0x7DC5 | OVERWRITE (no mask) ; 0x7DA8 flip variant | |
| 0x7D6C | paints non-zero attr bytes into the attr buffer (figure colours) | caller 0x9A74 only |

### Figures (callers -> what; RZX counts, game frames 758)
| Figure | Calls | Count |
|---|---|---|
| Player (2 parts: legs 9E04, body 9E0C; pos self-mod 0x9E05) | 0x9E3F from 0x9DFC.. (89CF) | 758 each |
| Enemy soldiers and gun turrets (2 parts) | 0x9E3F from 0xA4EF/0xA501 (89CC, IX = object) | 632 |
| Jeep (top masked, body OVERWRITE with own attrs, wheels masked) | E395 / E3A1 / E3AE (DD18) | 275 |
| End-of-level tank (several masked + overwrite parts, mirrored part; turret via 9EEF from DEAF) | DEDF..DF34 (DD15/DF02/DF0D), DEB2 | 153 |
| Explosions (overwrite + masked, own attrs red/white) | A059 / A065 / A072 (89DB) | ~110 |
| Bullets / shots (8x8 overwrite + attr paint 0x7D6C) | 7D7B, 9A36, 9A74 (89D5) | ~600 |
| Keys (rotating collectables; 4 frames 0xAB88/ABC8/AC08/AC48, 2 bytes x 16 lines) | 97E1 from 97A4 (974D) | 897 |
| (not in the RZX) other shots, player add-on, collectable 0xB650, 0xAC88 object, shop figures | 9AC7 9AD7 9AF1 9D67 A142 9FE1 B9AA BA68; 7E06 via 7DFC | 0 |
Max 32 plots in one game frame. Original figure colours: player and soldiers take the cell
attribute (clash); explosions, bullets and the tank (0x7D84 after its turret) paint their own
attrs; the jeep's colours are tile-map attributes (0x7A00 map: written by the scroller 0x8D06 /
new column 0x8DB8, copied to 0x6B00 by 0x884E before any plot).

## Preview (3b)
work tool: run each captured plot twice on a 0x00 / 0xFF buffer -> ink / opaque / transparent
pixels per figure; composed over the clean (pre-plot) buffer. Sheet mr_preview.png (game
graphics: private repo only): original | player green + soldiers white, black outline, others
ink of their cell | everything in the ink of its cell.

## Dean's decisions (2026-10-13)
- Round 3: "make everything possible a sprite". Every plot through the six hooked plotters
  converts, whatever its caller (unknown callers: cell colours), in the game loop. Stays on the ULA:
  scenery, the HUD and text (0xBC55 8x8 characters).
- Round 4 (Dean's level 2 video and photo): the shop's figures are sprites too (item icons, name
  plates, the purchase animation, the player); level 2's big round shots (0xADF3, 3 x 16, from
  0x9AD9) and the other weapon shots go through callers no recording reached: converted, and on the
  sheet from the code (STATIC) until a recording draws them.
- Vertically flipped draws (97A7 / 97C4 / 7DE9 / 7DF2 set both strides to -32, D = the bottom line;
  0x9A96 / 0x9AA4 draw a missile-like shot's halves through 0x97AC): sprites with the Y-mirror bit;
  FIG flags bit 7; V_Y = the top line; tiles placed bottom-up (y = Y + R - 16 * (TY + 1)); a
  flipped loop ends one line above the top (FIX 0x9F / 0x3F -> 0x5A). Not in either RZX: unit
  states derived from the recorded plots (strides -32 in memory, D on the bottom line).
- Round 2 (hardware photos): the three rotating figures in front of the player are the KEYS:
  sprites with their own colour, not the background's. Proposed: bright yellow (14, like the HUD
  key icon), black outline - Dean to confirm or repaint on the colour sheet.
- Colours per pixel: Dean paints a sheet; the PNG comes back and becomes the colour map. Sheet
  rules (Dean): 1:1 pixels, multi-part figures joined, 8x8 palette swatches.
- Painted (Dean, 2026-10-14; specnext mr_colours_painted.png): 1,196 pixels changed in 25 figures
  (soldiers, keys, shots, the tank and turret, the jeep, shop items, figures from the code) ->
  docs/profiles/midnight_resistance_colours.json, 444 graphics bytes. The tank is on the sheet
  three times (same graphics): the cyan Dean added on the second copy's dome applies to all three
  (one colour per graphics byte; painted beats unpainted). Keys: as painted (proposal superseded).
- Sprites: player, enemy soldiers + gun turrets, vehicles (jeep, end-of-level tank).
  Explosions, bullets and small objects stay on the ULA (they keep their own painted colours).
- Colours: "keep the colours the game defines" (explosions are excellent). The player and soldiers
  define none (they take the cell's attribute), so Dean chose fixed colours: player green,
  soldiers white, black outline. Vehicles keep their own colours.
- Depth: the original draws every figure after the background -> sprites in front of the
  scenery; between figures the game's draw order (no question needed).
- Note: the jeep's green/cyan cells come from the TILE MAP attrs (0x7A00 map, writers 0x8D06
  scroll / 0x8DB8 new column), not from a figure painter: as a sprite those cells stay on the ULA.

## Patch (phase B)
Hooks in alt ROM image 1 (tables 0x2000-0x24FF: NIBTAB, FIX, INKI, PAPI; code 0x2500-0x2EA1; the
game reads only ROM 0x0000 and the font 0x3D00-0x3FFF). State: Next RAM page 26 mapped at MMU slot
5 (0xA000) only while a hook runs - the ISR (and its 7FFD writes, which reset slots 0/1/6/7) never
touches slots 2, 4, 5 (full-RZX isr slot scan). Interrupts stay ON in every hook.
- CALL 0x7EC1 sites (operand replaced, same return address and stack bytes): 0x97E5 (97E1 masked),
  0x981E (9813 mirrored), 0x7DC6 (7DC5 overwrite), 0x9EF0 (9E3F/9EEF 32-px), 0x9F45 (mirrored).
  The hook decides (guards below); converted: the figure is RECORDED (FIG table), the buffer bytes
  under it are copied to the scratch copy of the buffer (page 26 = buffer + 0x4500) and the hook
  returns the scratch address, so the game's own loop runs unchanged into the scratch.
- Loop exits (JP to ROM; JP NZ / DJNZ redone there): 0x980F, 0x9861, 0x7DE5, 0x9F3D, 0x9FB7: FIX
  table maps D back (identity outside 0xA0-0xB1, so passthrough plots are untouched), unmap, 3.5
  MHz. The 32-px loops end with ADD HL,BC on the address: its flags (H, C, bits 3/5) are redone
  on the real address (FIXDEF).
- 0x8988 (JP Z,0xB7E0: the loop's end-of-level exit -> shop -> next level): hide every sprite, loop
  no longer live. Missing until 2026-10-13: the last frame's player sprite stayed on through the
  shop / level 2 ("stuck enemy", Dean's photo). The shop code (0xB890) calls the frame routine
  0x8F48 but never the commit.
- Shop loop (0xB879-0xB8B3, entered by the end-of-level exit): it runs the frame routine 0x8F48
  (screen copy) but not the game loop's commit. 0xB893 (after it; XOR A / LD (0x93D8),A redone):
  the same commit (shared body `commit`); 0xB89B (LD A,(0xFF70) / OR A / RET NZ) and 0xB8A5
  (LD A,(0x9DFD) / CP 200 / RET Z: the player walks out): hide everything when they leave.
- 0x8950 (after the screen copy): commit - builds the recorded figures' sprites, writes the
  attributes, hides the rest. 0x8993 (loop exit test): game over -> all sprites hidden.
- Sprites: 16x16 4-bit, one palette (0 transparent, 1-7 colours, 8 black, 9-15 bright); each
  figure = its W x R box cut into tiles, mirror by the sprite X-mirror bit; clip window = play
  area (x 24-231, y 0-127). Pattern-slot cache (16 entries; key gfx, W, R, flags, colour, and for
  cells figures Y&7 + the attribute signature under the image); slots on show or used by the
  current commit are never overwritten (no tearing between pattern and attribute).
- Guards (pass = the plot stays on the ULA): in the game loop (a commit seen, no game over), <= 32
  figures and <= 64 sprites per frame, line < 128, 1-8 bytes x 2-48 lines, box inside the buffer
  and wrapping only into the margins, graphics outside 0xA000-0xBFFF, strides +32 and OR opcodes
  as expected (9E3F: OR or NOP), caller in the lists (player 9E04/9E0C, soldiers A4F2/A504, tank
  turret DEB2; vehicles E395/E3AE/E3A1, DEDF/DEEA/DEF9/DF28/DF34).
- Colours: player bright green (12), soldiers / turrets bright white (15), keys bright yellow (14),
  black outline; vehicles and the tank turret: per byte the ink / paper of the attribute cell at
  commit time. Then the colour map (below) per pixel.
- Graphics under the page (keys, shots, explosions, 0xAB88-0xB2C0; up to 880 bytes per frame - too
  much to copy per plot): the plot runs into a second scratch, page 27 mapped at SLOT 2 (buffer -
  0x1B00 -> 0x4000-0x4FFF), with slot 5 back on page 5 so the loop reads the graphics in place. The
  buffer box is copied into page 27 through slot 4 first; FIX maps D 0x40-0x51 back (+0x1B) and every
  loop exit restores slot 2 (page 10). ISR: never touches 0x4000-0x5FFF; the ULA shows bank 5
  whatever slot 2 holds. The commit copies such graphics (< 256 bytes) through slot 4 = page 5 into
  TMPG (0xBF00). FIG flags: bit 3 player set, bit 6 graphics under the page. (Replaces the first
  key-only relocation.)
- Sixth plotter 0x7E06 (overwrite, mirrored through the bit-reverse table 0xFDxx): CALL site 0x7E0E,
  exit 0x7E39, strides 0x7E23 / 0x7E34 must be 32. Not in the RZX: unit cases from states derived
  from the recorded 7DC5 plots (same stack at the CALL, E on the right-hand byte).
- The player's add-on piece (97E1 from 0x9DFC, 9813 from 0x9DEF; graphics 0xC109, 1 x 24) takes the
  player's colour and colour set (acall list), like the legs and body.
- Commit bug found by the extra sprites (fixed): SPR + N * 5 was computed in 8 bits, so from the
  52nd sprite (5 x 52 = 260) entries wrapped onto the first ones; level 1 peaked at 38 sprites
  before shots / explosions became sprites, 57 after. Unit: "full table" commit (64 sprites).
- Static scan (every CALL to the plotters; the first RZX shows 19 callers): also 9AC7 / 9AD7 / 9AF1
  (other weapons' shots), 9D67 (a player add-on, graphics 0xAF00), A142 (a 4-frame rotating
  collectable, 0xB650), 9FE1 (2 x 48 overwrite, 0xAC88), B9AA / BA68 (shop), 7DFC (7E06). All but
  the shop convert now; none is on the sheet until a recording draws them.
- Colour map (docs/profiles/midnight_resistance_colours.json; none yet = default colours). All five
  plotters read the graphics the same way: lines of W entries, even lines left to right, odd lines
  right to left; an entry is (mask, graphic), or one graphic byte (7DC5). So colours belong to a
  graphics byte: per key address p (mask byte / overwrite byte) an 8-byte entry in Next pages 28..
  (4 bytes of colour nibbles, 0 = default; check byte mask XOR rotl(graphic); kind 1 / 2). Two sets:
  1 = the player, 0 = the rest (the soldiers share the player's leg graphics). PT0 / PT1 (page 26
  at 0xB580 / 0xB5C0) give the page per 1K of addresses. The commit maps the page at slot 4 (the
  ISR never touches 0x8000-0x9FFF) and overlays non-zero nibbles on opaque pixels (ovl); a check
  byte that does not match (other graphics at that address in a later level) leaves the defaults.
  The mask-only (flashing) image is never mapped.
- Two sheets (Dean, 2026-10-14): `python -m nexclash.midres sheet RZX RZX --z80 Z80 -o
  midnight_resistance` (autosave snapshots in the recordings are stripped first, as auto
  does; until 2026-10-14 the command desynced at RZX frame ~250 on both recordings) ->
  midnight_resistance_PAINTING_SPRITES.png (+ _layout.json; every graphic once) and midnight_resistance_REFERENCE_ALL_SPRITES.png (every figure whole); `colours
  midnight_resistance_PAINTING_SPRITES.png` reads the painting back. Both drawn with the current
  colours file, so the next painting continues from Dean's first.
- Sheet sources: every recording given (`sheet RZX RZX ...`, plots only inside the game loop / shop
  loop, as the patch converts them) and, with `--z80`, the STATIC list: figures the code can draw
  that no recording has (shown white with a black outline; unpainted they keep their cell colours).
- Sheet (the first game with the colour-sheet process; sheet side shared: nexclash/coloursheet.py,
  this engine's parts: sheet_part / capture): `python -m nexclash.midres sheet RZX -o mr_colours.png` (1:1, figures assembled from the
  parts drawn together in one frame, fewest figures that show every part at its longest drawing,
  8x8 swatches 1-15 at the top; layout in mr_colours_layout.json) and `python -m nexclash.midres
  colours painted.png` -> the colour map. Today's colours = no entry. A part shown twice: a painted
  colour beats an unpainted one; two different paints -> the first, reported. Both files hold game
  graphics: private repo (specnext/reference/midnight_resistance/).
- 9E3F's OR opcode is NOP while the player flashes (re-spawn): the sprite then shows the mask only
  (black silhouette), as the original.
- Speed (simulated T at 3.5 MHz; hooks run at 28 MHz): plot hooks + shadow loop ~87K per game frame
  vs the original plots' 41K (at 28 MHz: faster than the original); commit ~15-60K without
  vehicles, 76-200K with the jeep, 340-410K with the tank (cache thrash: 16 entries).

## Verification (2026-10-13)
RZX (4,709 frames, autosave stripped): 4,463 converted plots (97E1 1,138, 9813 143, 7DC5 870, 9E3F
1,799 + mirrored 513), 3,065 passed through, 758 commits (max 36 sprites), 1,656,090 sprite pixels,
1 loop exit - IDENTICAL: per plot all registers (AF' included) and all memory except the buffer
bytes the original drew; per commit registers + memory, and the sprite layer = the original plots'
pixels (truth: each plot run on a 0x00 and a 0xFF buffer) in plot order with the expected colours;
patched interiors never executed (DJNZ fall-throughs checked, interrupts allowed for); MMU5 and
speed restored. Unit: 2,103 guard cases (converted iff model_decide), 15 commit cases; negative
control (ink/outline swapped) 12/12 informative cases; interrupt safety checked after every hook
instruction (IX, IY, I, IFF, stack room, 0x3D00 fetches), negative control (LD IY in each CALL hook)
15/15. Static: no DD/FD/DI/EI/LD I/IM in the hook code.

## Verification (2026-10-13, rounds 2-4)
VERIFICATION.md: both RZX IDENTICAL (25,527 converted plots, 5.9M sprite pixels, shop included),
also with a repainted colour map; unit + interrupt + exits + full table + flipped + map PASS.

## Known differences
- Sprites are always in front of the ULA (scenery, HUD); between figures the game's own order.
- The jeep's green / cyan cells are tile-map attributes: they stay on the ULA under the jeep sprite.
- Converted figures appear when the commit runs (after the screen copy), not as the copy passes.

## Open
- The second RZX covers the shop and more of level 1 (0x89AB object, player add-on, more poses)
  but not every weapon / collectable / level 2: still unseen callers 9AC7 / 9AD7 / 9AF1 / A142 /
  9D67 and 7E06 (static scan; converted, proven by derived states only). A level 2 RZX (Dean)
  puts level 2's figures on the sheet.
- MAXF 32: one RZX frame has 33 plots (the 33rd stays on the ULA that frame); raising it needs the
  FIG table (0xB100, 8 bytes each) to grow past the hook stack at 0xB200.
- Speed: more figures per commit (shots, explosions); no hardware timing yet.
- Level exit 0x8988 is proven by unit tests only: the shop and level 2 need a recording (Dean).
  Level 2's figures (callers, graphics) are unknown: the sheet covers level 1 only.
- Hardware: a4fb69a2 and 670f9403 (painted colours) test OK (Dean, 2026-10-14; overall verdict, items not reported one by one).
- Later levels (banks 1/3/4/6) not in the RZX: need a later-levels recording; their figures may
  use other callers (stay on the ULA) or graphics in 0xA000-0xBFFF (guard: stay on the ULA).
- Tank scenes: cache thrash (16 entries); 32 entries need more page room (SIG area).
- The player's extra part (9DEC/9DF9, drawn when (0x9E08)&7 >= 5: weapon?) never ran in the RZX:
  stays on the ULA.
- `convert --rzx` / analyse() fails on this 128K RZX (STATUS open work 6).

## Hardware checklist
1. Boots to the title; '5' toggles the AY music; fire starts.
2. Player: green with a black outline, animates, no colour clash; mirrored when facing left;
   flashes as a black silhouette after re-spawn.
3. Soldiers and gun turrets: white with a black outline; jeep at the start and the end-of-level
   tank: their own colours.
4. Nothing drawn outside the play area (columns 3-28, top 16 rows); no stale sprites after scrolling.
5. Shots and explosions are sprites now: no clash, drawn in the game's order with the figures
   (no longer behind them). Keys: yellow sprites with a black outline, rotating, no clash.
5c. Level 2 figures: sprites (cell colours until painted); report any figure still clashing.
5b. End of level 1 -> shop -> level 2: no sprite left behind (the stuck green figure is gone).
5d. Shop: the player green, item icons / name plates / the purchase animation as sprites, no clash;
    walking out: nothing left behind. Level 2: the 3-way gun's shots as sprites.
6. Speed vs the plain build: normal play, the jeep at the start, the tank at the end of level 1.
7. Game over: sprites gone from the game-over / high-score screens.
8. Faults: Fuse "Record from snapshot" on the .z80, autosave off, send the RZX.
