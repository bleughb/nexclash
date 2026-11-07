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

## Rework (opt-in) v128: the 128K release (engine `magicland128`; Jon Attree, 2026-11-05)
Dean's builds (09eb1849 / bf137d41, slot1 d3b37c05) are untouched and stay his record's; `selftest --game magicland_dizzy`
rebuilds them and this rework = recorded.
- Why: TOSEC `Dizzy 4 - Magicland Dizzy (1990)(Code Masters)(128K).z80` (7ebfab28) is the same program as the 48K file
  (banks 5 / 2 / 0 byte-identical but for state); its ISR plays the AY music when 0x728E = 1 (CALL NZ,0x9CC9 pages
  bank 3 at 0xC000, OUT 0x7FFD = 0x13, and bank 0 back, 0x10, before the hide call 0xFF64). ROM 1 throughout.
- `nexclash/magicland128.py`: Dean's TidPatch (strategy altrom) on the 128K snapshot; whole alt ROM image (image 1 =
  Sinclair's ROM + hooks at 0x386E, image 0 = the 128K ROM 0); tail in the dead stack 0xA2BD (Dean's decision; the
  128K walks' low water 0xA2C1); the printer buffer (the game's bit-reverse table, read before written) put back after
  NEXLOAD for plain and sprites; the plot hook through a head (latch NR 7 into the dead stack, 28 MHz) and a tail
  (latched speed back, JP plotter); a 128K copy of verify.py + box, pixel tests, guards; clock matrix.
- Keys: SPACE starts at the title and jumps, Z / X walk, ENTER inventory. Probe 0x9DFD (the player plot site).
- Results (2026-11-05): plain 36e1a1c8, sprites 67808068, boot OK. walk1-3 (12,013 / 12,028 / 12,020 frames): every
  hook event identical (4,684 plots, 4,695 erases, 21,245 ISR, 135 wipes, 47 boxes; 4,713 plots pixel-perfect), but
  5 of 101,594 pixel tests (0xA134, callers 0xA10C) DIFFER: the original's eraser (0x9CA0) XOR-restores a stale undo
  after another routine (0x906F / 0x90DE) drew over Dizzy, leaving a hole in the background; the build keeps the pixel.
  Dean's 48K build has the same property (same code; dizzy4rzx never hit it). Status PARTIAL until a virtual read
  reproduces the holes or the owner accepts the difference. Negatives: 6, 5 by their own signal (the wipe hide alone
  is masked by the ISR hide). Clock matrix 20 cases PASS, forced 3.5 MHz exit detected. ROM paths pass, tail never
  read before written. JNext: pace ORIGINAL (10 trials a scene: quiet +0.00 %, busy -0.01 % mean, sound +0.03 %
  mean; interrupt losses in both runs), flicker clean, soak 15 min clean, AY 750 writes/s.
  Cheats: all 8 of the 128K .pok kept, each proved in the simulator.
- Enhanced: EASY. Dizzy's 39 frames are byte-identical to Treasure Island Dizzy's, all matched by Treasure Island
  Dizzy.256; no Magicland .256. Mock-up: pilot runs/dean_magicland_dizzy/out/ml_enhanced_mockup.png.
- Found: Dean's 48K build gets the ROM path check's printer-buffer warning (170 bytes read before written, PC 36799):
  on a real Next the mirrored-object table at 0x5B00 starts as NEXLOAD left it. Frozen; for the owner.
- Hardware: none.

## Lessons
- [deferred Open: reconsider when a third 128K rework needs it: z80tonex keep_printer_buffer for 128K snapshots]
  magicland128 restores 0x5B00-0x5BFF in its own set-up because keep_printer_buffer is 48K only.
- [deferred Open: reconsider when the owner rules on the 5 tests: a virtual read for the TID pixel test that reproduces the original's ghost
  holes] more recordings found 5 pixel tests that depend on them; Dean's single recording had none.

## Technique use
- patch.restore-speed: used (head / tail latch round Dean's plot hook)
- verify.update-locked-pace: helped (probe 0x9DFD, the player plot site)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path, tail and printer buffer checks found the NEXLOAD fault
- retries: [local: the stack low water (the eraser uses SP as a pointer), apply() run twice by the boot check]
- environment: [none: headless JNext with HOME in the run folder, the read-only card]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator; pace trials from Treasure Island Dizzy's script]
- scratch: [none: scripts stay in the pilot run folder runs/dean_magicland_dizzy/work]
