# Magicland Dizzy (Dizzy 4, Codemasters) - TID engine, generic builder

48K. Engine facts shared with Treasure Island / Fantasy World: games/tid_engine.md.
Builder: generic (nexclash/build.py, identify.py, templates.json; strategy altrom by default).
Profile: docs/profiles/dizzy4_magicland_dizzy.json; signatures.json (`tid_engine`).
Reference files (private repo, specnext/reference/magicland_dizzy/): snapshot (md5 53078ac6;
selftest input magicland_dizzy.z80) and dizzy4rzx.

| Output | MD5 | Status |
|---|---|---|
| magicland_dizzy_sprites.nex (altrom) | bf137d41d3cc08221bf6fdda153c9de2 | verified; baselined 2026-10-11; hardware untested |
| magicland_dizzy.nex (plain) | 09eb18496cff334ea17bfc0b0c94585d | |
| `--strategy slot1` (old build) | d3b37c05d4c47ada07294fa2d7c1ae76 | reproduced by selftest |

Verified: dizzy4rzx 10,074 frames - 1,690 plots, 1,670 erases, 3,486 ISR, 51 wipes, 44 boxes;
33,294 pixel tests unaffected: identical except 4 undo-buffer-only differences (the original's
ghost pixels; nothing else reads that buffer) (docs/VERIFICATION.md).

## Facts (addresses; engine routines described in tid_engine.md)
- Plotter 39744, eraser 40059; plot site JP at 40445; undo buffer 23552 (system-variables area);
  frame table 24644.
- Room wipe 37091; box 37690; ISR hide call 65380; pixel test 41268.
- No game logic reads the player's pixels.
- Printer buffer USED (bit-reverse table for mirrored objects); ROM not used; stack SP 0xA2F9,
  low-water 0xA2BD, code directly below it (the default "below SP" tail would hit code).
- The object plotter self-modifies: 36775 (NOP / XOR (HL)) and 36772 (JP 36795 = mirrored path via
  the 0x5B00 table) - model the op in force.

## Open
- Hardware test of the altrom build.

## Hardware checklist
1. Game starts; music and timing unchanged.
2. Dizzy is sprites: animates, faces both ways, no clash, no leftovers on moves / room changes.
3. Mirrored objects still drawn correctly (the printer-buffer table is the game's own).
4. Inventory and dialogue boxes: Dizzy hidden behind them as in the original.
5. Faults: Fuse "Record from snapshot", autosave off, send the RZX (+ where).
