# Fantasy World Dizzy (Dizzy 3, Codemasters) - TID engine, generic builder

48K. Engine facts shared with Treasure Island / Magicland: games/tid_engine.md.
Builder: generic (nexclash/build.py, identify.py, templates.json; strategy altrom by default).
Profile: docs/profiles/dizzy3_fantasy_world_dizzy.json; signatures.json (`tid_engine`).
Reference files (private repo, specnext/reference/fantasy_world_dizzy/): the "(a)" keyboard
snapshot (md5 876f474b; selftest input fantasy_world_dizzy.z80) and dizzy3rzx.

| Output | MD5 | Status |
|---|---|---|
| fantasy_world_dizzy_sprites.nex (altrom) | 9182f2f8b4b0dc55b59a69728568b403 | verified; baselined 2026-10-11; hardware untested |
| fantasy_world_dizzy.nex (plain) | cd620010e2f61af0002e76718945716f | |
| `--strategy printer` (old build) | c09213beaec1572c0228985dae89bd77 | reproduced by selftest |

Verified: dizzy3rzx 8,761 frames - 1,613 plots, 1,591 erases, 3,319 ISR, 44 wipes, 40 boxes;
30,976 pixel tests unaffected: all identical (docs/VERIFICATION.md).

## Facts (addresses; engine routines described in tid_engine.md)
- Plotter 56705, eraser 57020; plot site JP at 63940; undo buffer 57083; frame table 57183.
- Room wipe 61865; box 62343; ISR hide call 63725; pixel test 64672.
- No game logic reads the player's pixels (no virtual read: boxes overwrite the player).
- Printer buffer free; ROM not used; stack SP 0x5FF2.
- Byte 62569 = 255 enables Kempston: use the keyboard snapshot ("(a)").
- Executes `LD R,A` (machine.py re-runs such frames with exact counting).

## Open
- Hardware test of the altrom build.

## Hardware checklist
1. Game starts with keyboard controls; music and timing unchanged.
2. Dizzy is sprites: animates, faces both ways, no clash, no leftovers on moves / room changes.
3. Inventory and dialogue boxes: Dizzy hidden behind them as in the original.
4. Lives lost / respawn: no stale sprite.
5. Faults: Fuse "Record from snapshot", autosave off, send the RZX (+ where).
