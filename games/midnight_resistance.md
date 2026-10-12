# Midnight Resistance (Ocean 1990, 128K) - engine `midres`
Updated 2026-10-13. Engine `midres` (nexclash/midres.py, asm/midres_hooks.asm,
docs/profiles/midnight_resistance.json; after any .asm edit `python tools/asm2profile.py
midnight_resistance`). Status: RZX IDENTICAL, unit + interrupt checks PASS; e8f0ece9 RUNS ON A REAL NEXT (Dean,
2026-10-13; detailed checklist not yet reported).

Reference (private repo, specnext/reference/midnight_resistance/):
Midnight_Resistance_1990_Ocean_128K.z80 (67bf05d356d51b2b402d88c5f0cdfb21),
Midnight_Resistance_1990_Ocean_128K.rzx (b75ecd5f60c3ec67fe463a0aa606f6a1; Dean 2026-10-13, Fuse,
8 autosave snapshots, 4,690 frames: title, level 1 to the end-of-level tank, game over, name entry).
Selftest names them midnight_resistance.z80 / .rzx (docs/records/midnight_resistance.json).

    python nexclash.py auto midnight_resistance.z80 --rzx midnight_resistance.rzx --no-record   (~20 min)
    iterate: --quick 300 (~1 min)

| Output | MD5 | Status |
|---|---|---|
| midnight_resistance.nex (plain, tail 0x7B7E) | 17239acaaf67b0f8011478053e17829d | built; hardware untested |
| midnight_resistance_sprites.nex (altrom + page 26 at slot 5, pattern-slot cache) | e8f0ece9e41c314d76471c96f4595854 | RZX IDENTICAL; runs on hardware (Dean, 2026-10-13) |

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
| Small masked objects | 97A4 (974D) | 886 |
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
- Colours: player bright green (12), soldiers / turrets bright white (15), black outline; vehicles
  and the tank turret: per byte the ink / paper of the attribute cell at commit time.
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

## Known differences
- Sprites are always in front of the ULA: bullets, explosions and small objects (ULA) are drawn
  behind converted figures (the original draws by call order).
- The jeep's green / cyan cells are tile-map attributes: they stay on the ULA under the jeep sprite.
- Converted figures appear when the commit runs (after the screen copy), not as the copy passes.

## Open
- Hardware: runs (2026-10-13); checklist items 2-7 not yet reported item by item.
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
5. Bullets / explosions still visible (on the ULA, behind figures).
6. Speed vs the plain build: normal play, the jeep at the start, the tank at the end of level 1.
7. Game over: sprites gone from the game-over / high-score screens.
8. Faults: Fuse "Record from snapshot" on the .z80, autosave off, send the RZX.
