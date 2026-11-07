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

## Rework (opt-in) v128: the 128K release (engine `fwd128`; Jon Attree, 2026-11-05)
Dean's builds (cd620010 / 9182f2f8, and the printer repro c09213be) are untouched and stay his record's;
`selftest --game fantasy_world_dizzy` rebuilds them and this rework = recorded.
- Why: the 128K release plays AY music from bank 3 (0x6176 pages it in, CALL 0xC003). The 48K-128K program is one
  program: identify() finds the same profile in banks 5 / 2 / 0 as in Dean's 48K snapshot, every patch site the same.
- Input: TOSEC `Dizzy 3 - Fantasy World Dizzy (1989)(Code Masters)(128K)[a2][a2].z80` (2f84d85c): the 128K release
  saved at the title (PC 0xF419, SP 0x5FF2, EI), like Dean's 48K snapshot. The main dump (128K).z80 (c7d3e567) has the
  same code but was saved in play, mid-plot (DI, SP 0xDFC3 inside the plotter's graphics: no place for the tail).
  Byte 62569 = 255 in every 128K dump: Kempston is read as well as the keys (0xF449); the keyboard always works.
- `nexclash/fwd128.py` (Dean's build.TidPatch, templates.json slot1 hooks: used, not copied): 128K detector / apply;
  tail at 0x5B00 and a speed latch at 0x5BFF in the printer buffer (128K ROM 0's paging routines, which this game
  never calls; the verifier fails any read or write of it by the game); whole alt ROM image as the build's own complete
  image 1 in bank 12 (Sinclair's ROM + the hook bytes, as tid128 / Cauldron: no bank 47, so a loading screen's stub
  fits in bank 13); a 128K copy of nexclash/verify.py that ends the ISR event where the hook hands over to 0x6176,
  fails bank paging inside an event and alt ROM hook bytes read by the game; the plot site goes to a wrapper that
  latches NR 7, runs Dean's plot hook at 28 MHz and restores the speed before JP plotter (the other four hooks are
  1-3 NEXTREGs each, shorter than a speed switch, and never touch NR 7); the every-site clock matrix.
- Keys: SPACE starts at the title and jumps, Z / X walk, ENTER the inventory (a tap: held, it reopens), Q quits.
- Game loop: 0xA705 waits for 3 frames on the ISR counter 0xF931; 0xA711 runs once per update (the pace probe).
  Dialogue / death boxes and the title poll 0xF42E with no update: the pace trials tap SPACE after 400 polls.
- R: no LD A,R executed in any recording (the two ED 5F / ED 4F byte pairs are graphics), so R needs no preserving.
- Results (2026-11-05): plain 9efc6a20, sprites 4dc1f8c6, boot OK; walk1-3 (12,010 / 12,007 / 12,004 frames)
  IDENTICAL: 5,983 plots pixel-perfect, 5,935 erases, 12,122 ISR (104 on the hide path, 2 hiding a shown Dizzy),
  100 wipes, 96 boxes, every hook; 4 negatives detected (nibbles, frame table, ISR never hides: on walk2 only, wipe
  never hides); clock matrix 5 sites x 4 clocks PASS, forced 3.5 MHz exit detected; ROM paths pass; tail never read
  before written. JNext: pace ORIGINAL (probe 0xA711, 10 trials a scene, lockstep throughout: quiet +0.00 %, busy mean
  +0.02 % (max +0.09 %), sound +0.00 %; AY 540-550 writes a second as the original), flicker: 3 out-of-step frames,
  all Dizzy standing in the animated fire (its ULA redraw under the sprite on its own cycle; Dizzy whole), 0 vanished,
  0 transients; soak 15 min clean. Pace was measured on 80735319 (the bank-47 fill), whose booted ROM view, RAM,
  registers (all but the stub's T), alt images and paging equal 4dc1f8c6's (work/equiv_b0_b2.log).
  Cheats (.pok of the dump): Infinite lives, Immune to flame (play, the start room's fire); Immune to rat, dragon's
  fire, armorog, gator, sharp daggers (their rooms not reached: unit run at each POKE site with the collision flag set);
  Lives dropped (asks for a value). Loading screen: the tape's (fe04d9, the all2 batch's DIZZY3), stub in bank 13.
- Enhanced: EASY for Dizzy. No Fantasy World .256, but FWD's 39 frames (4,556 bytes from 0xDFAD) are byte-identical to
  Treasure Island Dizzy's, whose .256 (Spec256-256-all38) colours all of them. The scenery stays 2-colour (bitmap
  rooms, no .256). Mock-up: pilot runs/dean_fantasy_world_dizzy/out/fwd_enhanced_mockup.png.
- Seen: Dizzy shows light grey (Dean's palette entry), the original's cell bright white (as Treasure Island).
- Hardware: none.

## Lessons
- [local: a 128K dump saved mid-routine (SP inside the plotter's data) leaves no tail place; an alternate dump of the
  same release saved at the title is the clean target]
- [local: the whole fill's Sinclair ROM bank 47 blocks the loading-screen tool's stub bank (it needs the top bank);
  a rework that wants a loading screen uses the build's own complete image 1 instead]
- [local: pace trials keyed to updates need a way past screens with no update (boxes, title): key it to the game's
  own input poll, release held keys first, never press a key that opens a menu]
- [deferred Open: reconsider when another TID-family 128K rework needs it: fold verify.py's 128K paths into the shared
  verifier] fwd128 and tid128 each carry a 128K copy.

## Technique use
- patch.restore-speed: used (the plot wrapper's latch / restore, as hlib_speed)
- verify.update-locked-pace: helped (probe 0xA711)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path and tail checks; the boot check, pace, flicker and soak ran on the 128K build unchanged
- retries: [local: the pace trials' box / title unstick (an ENTER tap opened the inventory)]
- environment: [none: headless JNext with HOME in the run folder, the read-only card]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator; pace trials from TID's script]
- scratch: [none: scripts stay in the pilot run folder runs/dean_fantasy_world_dizzy/work]
