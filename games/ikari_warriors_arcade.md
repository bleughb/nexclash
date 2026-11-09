# Ikari Warriors: Enhanced scenery (split from ikari_warriors.md, size budget)

## Design (2026-11-08; v1.3, published as .nxc 1.3, nxc d622047)
Enhanced gets the scenery's colours on the tilemap, under the ULA's own ink; the default build is unchanged (8777f2c4). Enhanced 82ada11a = `nxc.py --bare --colours Enhanced` of the published patch; auto builds both with no input beyond the snapshot.
- The game's scenery is 8x8 chars, one attribute each, drawn by 0x9733 one cell at a time into its 256-line circular buffer, row = line / 8. The tilemap wraps at 256 lines too, so a cell written once stays right, and one register follows the scroll: NR 0x31 (below) = window's first buffer line - 48 (origin + 56 lines).
- The ULA keeps every pixel: black ink shows on top, paper and blue ink are clear. A tile only holds paper colours (and the blue of water cells, from the game's own char at build time), so outlines are per pixel and the attribute jump (8 lines against 2) no longer shows.
- Map and tiles: bank 7's first 8K, the only part the tilemap can read there (BRAM, JNext as the core): map 1,280 bytes one byte a cell, then up to 216 tiles. Carried in bank 24 (SET3, the set's own bank; NXC refuses an added bank below 8), copied once before the first tile: table page 48 (map byte IY - 0x8000 -> tile, 0xFF = char default; defaults at 0x1F00), tile graphics page 49.
- Sites: 0x97E4 a_tc (a cell's tile); e_bl.nw's call -> a_bl (registers, then the scroll); 0xF019 a_st (the stipple patch over a destroyed object: ground and rock tiles in its 8 x 10 cells back to ground); the four exits run SCENERY_OFF first (registers only, no flags, no stack).
- The scroll and the blit: the blit starts at any moment (the game has no frame sync), so with the beam in the window the ULA's new ink reaches the lines below the beam only after the beam has gone. The tile scroll is armed on the copper for the line where the blit, 3.4 lines to the beam's one, overtakes the beam: lines above it show old ink and old tile, lines below new ink and new tile. Measured against the same build without it (JNext, 200 frames in a walled stretch): grey against ground where the map says otherwise, 8 frames over 20 pixels, worst 170; with it 1 frame, worst 32. A first version held the blit for the blank: cured it too, but cost +1% (busy +4.3%). T_BLIT 6130 -> 6115 pays for a_tc.
- Black ink stays palette black: the HUD has black-on-black cells that would show with any other ink colour (found in the loader sheet).

## Data
docs/profiles/ikari_warriors_scenery.json, from a JNext trace of 4,200 updates (2,281 map bytes, 212 chars, 480 rows). Rocks and bunkers are found on the stitched map: the ground is what a flood from open paper reaches with ink as the wall, enclosed paper of large objects (opened by 3 pixels, 150 pixels up) is grey, shoreline dither excepted. Colours: dirt 73 73 0, rock 109 109 109, wood 146 109 36, foliage, light foliage, water 0 0 219.
Tile list: ground and rock first (A_RK) so the stipple hook leaves foliage, water and wood alone.

## Hardware checklist
The tilemap in bank 7 shows (a core with NR 0x6E/0x6F bit 7); scenery colours scroll with the ink; no grey on ground at rock and wall edges (the copper's tile-scroll line).

## Checks
scenery_compare in verify: the tile scroll (V_TS) against the origin at every commit; the copper's write itself is only seen in JNext; every map cell changed holds a tile its char can have; none written is a failure. Negatives: tile-writes-off, tile-row-off, tile-scroll-off.
