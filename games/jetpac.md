# Jetpac (Ultimate Play The Game, 1983) - engine `jetpac`

## Next session
Stage: 4 (hardware round 2)  State: rocket / fuel / flames fix verified + stamped 2026-11-03
Inputs: specnext/reference/jetpac/ (snapshot, both .nex)    Branch: claude/adoring-albattani-50f4p8
Start with: the user's hardware report against ## Hardware checklist (round 2)
Read: PLAYBOOK stage 4, ## Rocket (round 2), ## Patch design
Open: no RZX yet (rocket build, take-off, levels 2+ proven by unit tests on the game's own
routines); colour sheets not rebuilt (the game's own colours, no recolour); no PR yet

48K (16K game). Code: nexclash/jetpac.py, asm/jetpac_hooks.asm, asm/jetpac_tables.asm (GENERATED:
`python -m nexclash.jetpac tables GAME.z80`, then `python tools/asm2profile.py jetpac`),
docs/profiles/jetpac.json. Dispatch: nexclash/engines.py, by signature at 30522 (the plotter).
Reference: specnext reference/jetpac/Jetpac_1983_Ultimate_Play_The_Game_a_16K.z80 (Dean, 2026-10-19).
NO RECORDING (Dean, 2026-10-19: "no rzx this time"): the differential test runs on a 6000-frame free
run (jetpac.free_keys: menu 1/3/5, then Jetman walks, flies and fires both ways) + unit tests over
every graphic. A real Fuse RZX would add the game's own paths (rocket build, fuel, items, levels 2+).

    python nexclash.py auto Jetpac.z80 --no-record

| Output | MD5 | Status |
|---|---|---|
| jetpac.nex (plain, tail 0x5B00) | feff51b7038606d21c03c260055481e4 | boot sim OK |
| jetpac_sprites.nex (altrom, stateless hooks, 82 patterns) | 3cf8fbd2762091244c7580ccfa79d82d | free run IDENTICAL, unit PASS (round 2 fix); hardware: round 2 pending |
| (round 1 build, superseded) | c963b42f0e685d648d552656fde4d6f9 | hardware: rocket sections flash, fuel invisible, no flames |

Verification (2026-10-19): free run 6000 frames: 20433 draws, 100 erases, 23192 colour paints,
5 screen clears, 2193166 sprite pixels = the original plot; unit (round 1): 5616 graphic cases (every graphic
incl. all 8 levels' aliens and the 12 carried rocket parts x 8 positions incl. both edges x 3 inks x
first/last object), erase 2, clear 1, guard 1, negative control 40/40.

## Rocket (round 2, 2026-11-03: the user's hardware report)
Faults (user, round 1 build): (1) a rocket of 2-3 sections shows only the top one, the lower
ones flash; (2) the fuel pod is invisible (collectable); (3) no take-off flames. All three are in
paths the free run never reaches (it never builds the rocket), so every check passed.
- Causes (code): the rocket is ONE object (6, 23856) that draws up to 4 figures per frame: base,
  middle, nose in the loop 26432 (29278 per section, (IX+2) - 16 each, (IX+4) = sections) and the
  flames at 26265 (29339; graphics 32652 / 32687 at y + 21, erased by 26255 / 26261 through
  29344). The hooks gave each object one sprite set and hid the rest on every draw, so each
  section replaced the last. The flames were not in gtab (drawn as nothing, and hid the rocket).
  The carried-part buffers 24268.. are built from (23860) = parts landed: 3 = the fuel pod
  (words 12-15 of 26563); the hook drew nothing for part >= 3.
- Fix: the rocket's figures get a pair each (102-103 base, 104-105 middle, 106-107 nose, 108-109
  flames; role from gtab kind bits 2-4) and touch only that pair; e_e1 (graphic known) hides only
  the erased figure's pair (the flame erase no longer hides the rocket); e_e2 and the clear hide
  all (clear: 0-109). Carried part 3 (fuel) in the tables. Flames in gtab, bright red (the game
  paints 66 over them, 26268).
- Colours: the game paints the rocket per character row after drawing (26488-26562): white,
  fuel F rows magenta from the bottom (F = (IX+5) 1-5), full = flashing 67 / 71 by bit 4 of
  (24012). The hook computes this per section (rcol); rocket part patterns use index 1 on the
  bottom 8 lines and index 2 on the top 8, palette offset 8 = magenta below / white above (the
  half-fuelled section; offset 8 = ink 0 bright is never an object ink, 25877). Partial fuel only
  standing at y 183 (cell-aligned rows); take-off needs F = 6 (26384), landing F = 0 (26340).
- Rocket x is 168 on every level (template 24600): sections never wrap at x = 256.
- Alt ROM: 1149 bytes, ends 0x3CFF with the 20-byte register block (1 byte left).
- Flame erase then draw (26255-26265) hides the flame pair for ~18 lines of raster time, as the
  original erases and redraws its flames on the ULA: same as the original.

## Patch design
- Alt ROM only (hooks + tables 0x386E-0x3CEB, 1149 bytes + 20-byte register block to 0x3CFF): no RAM page, no state. 82 4-bit patterns
  (bank 11, uploaded at setup across both 8K pages), sprite palette offset n index 1 = Spectrum
  colour n (8-15 bright). Tail 0x5B00 (0x5B00-0x5B7F zero; a loader leftover at 0x5B80-0x5B8D is
  never touched).
- e_nw at 29263 (replaces LD A,(DE) / LD B,A / LD (24004),A, all replayed): object i = (IX-23808)/8;
  graphic (DE-1) looked up in gtab: static graphics directly, alien buffers by (24048) & 7, carried
  part buffers by (23860) * 4 + ((24048) >> 2) & 3; sprite x = byte column * 8 + the graphic's left
  trim, y = bottom line - 16 * rows + 1 (patterns bottom-aligned); up to 2x2 sprites, the column
  crossing x = 256 copied at x - 256 (the ULA row wrap); colour = (IX+3) ink + 8 * bright as the
  palette offset; unused sprites of the object hidden. Runs at 28 MHz (NEXTREG $07 3 -> 0): ~4K T
  per draw in the simulator.
- e_e1 / e_e2 at 29344 / 29349 (CALL 29223 / 29220, erase only): hide the object's 6 sprites
  (the rocket: e_e1 only the erased figure's pair, e_e2 all; ## Rocket).
- e_cls at 24717 (CALL 29112, every new screen): hide sprites 0-109.
- Screen-write removals: 30532 77 -> 00 (erase AND), 30561 77 -> 00 (draw OR), 29171 72 -> 00
  (object colour over its cells). The plotter keeps running: all game state stays the original's.
- Stack: lowest SP inside the hooks 23762 (sites >= 23782); + the ROM ISR's 16 bytes = 23746, above
  the code the game runs at 23728-23730 (the game alone reaches 23742).

## Hardware checklist (round 2: the rocket fix)
- Level 1: build the rocket - after the middle and after the nose land, ALL sections stay shown,
  no flashing.
- Fuel pods: visible falling and while carried (cycling colour), drop onto the rocket.
- Fuel filling: the rocket turns magenta from the bottom one character row per pod; full = the
  whole rocket flashes magenta / white.
- Take-off: red flames under the rocket, alternating; the rocket rises whole; landing on the next
  level: flames again, no flames left once it stands.
- Level 5: the new rocket (base only, parts to collect) shows no leftovers of the old one.
- Everything from round 1 below unchanged (Jetman, aliens, items, explosions, edges, speed).

## Hardware checklist (first test)
- Boots to the menu (1, 3, 5) and plays; Jetman, aliens, rocket parts, fuel, items, explosions are
  sprites in their game colours (aliens red / magenta / green / cyan by slot, items cycling).
- No colour clash: platforms and lasers keep their own colours where figures pass.
- Aliens wrapping across the left/right edge show on both sides like the original.
- Rocket assembly, fuel filling (parts turn magenta), take-off, level 2+ aliens (not reached by the
  toolkit's free run: proven by unit tests only).
- Speed: the same as the plain .nex (hooks at 28 MHz).
- Game over / new game: no sprites left on the menu.

## Snapshot (inspect)
- IM 1, DI at snapshot, I = 0x3F, SP 0x5CE6, RAMTOP 24575; game code 0x6000-0x7FFF.
- Menu: 1/2 players, 3 keyboard, 4 Kempston, 5 start. Free-run start keys: `10-12:1;20-22:3;30-32:5`.
- ISR = ROM 0x0038 (reads IY: keep IY = 0x5C3A); slots 1, 3-7 never touched by the handler.
- `auto`: engine unknown; plain .nex builds (tail 0x5B00, checked safe).

## Rendering model (one plotter for every moving figure)
- Move-and-redraw at 30522 (0x773A): per object, erase the OLD frame with CPL/AND (30529-30532)
  and draw the NEW one with OR (30559-30561), line by line, wrapping within the 32-byte row;
  29422 = next pixel line up. Old frame from (24000-24006), new from IX (+0 type/dir/flags,
  +1 x, +2 y). Entries: 29290 (move), 29278, 29339/29344/29349/29365 (draw / erase only).
- Graphic: [y offset, W bytes, H lines, W*H bytes], rows stored BOTTOM line first (the plotter
  steps up a line, 29422; first sheets were upside down - Dean, 2026-10-19). Pre-shifted: 4 shifts by x&6, direction =
  bit 6 of (IX+0); table 30458 word index (type-1)*8 + dir*4 + (x&6)/2:
  type 1 Jetman walking, type 2 Jetman flying (ROM data 30614-31640), type 3/4 = RAM buffers
  24064-24470 (aliens, explosion).
- Aliens: built per level into 24064/24166 by 26921 from table 26949 [(24048) & 7] (8 types;
  calling 26921 with 24048 = L builds level L's aliens - used for the colour sheet).
- Rockets, fuel, items: graphic pointer from table 26563 (+(IX+6)): words 0-11 = 4 rockets x 3
  parts (rocket r = words r, r+4, r+8; r+8 = nose, r = base), 12-15 fuel pod, 16-20 five bonus items.
- Plot callers (code): 25685, 25778, 25823, 25925, 25940, 25950, 26052, 26255, 26261, 26265,
  26299, 26305, 26403, 26446, 26846, 26871, 28037, 28146, 29895. Seen in free runs: 28149
  aliens, 29898 Jetman, 26449/25943/25928 rocket parts, 26849/26874 explosion.
- Other screen writers (scan, frames 0-530): 29023, 29119 (clear), 29171, 29060, 25038, 28829,
  28708/28717 - lasers, platforms, HUD/text: not classified yet.

## Dean's decisions (2026-10-19)
- Split APPROVED: Jetman, aliens, rocket parts, fuel pod, bonus items, explosions -> sprites;
  lasers, platforms, HUD, text -> ULA. Sprites in front of the ULA.
- Colours: the game's own (the ULA ink each figure gets in play: Jetman/rockets white, aliens
  their per-object attribute colour, etc.) - no painted sheet; the colours json is generated
  from the game's attributes. Sheets regenerated in those colours before delivery.

## Colours (game's own; measured at 29160 = LD D,(IX+3), the attr 29135 paints after each draw)
- Jetman 71 (bright white), rocket parts 71 (filled: 67 bright magenta, 26524), aliens 2-5 by
  object slot (27204: ((IX>>3)&3)+2 -> red, magenta, green, cyan), explosion cycles 66/67/70/71.
- Items (code, 25794 table by (IX+6)&15): offset 32 -> 70 yellow, 34/36 -> 69 cyan (0 when
  (24012)&31 >= 24: flashing), 38 -> 68 green, 40 and fuel (24) -> 25870: ((24012)>>2)&7 | 64
  (cycling bright colour). Fuel/items never reached in a free run: from code, not measured.
- The engine applies the object's (IX+3) ink per sprite (palette offset) at run time, so
  per-slot and cycling colours stay the game's. Sheets show the first/default colour.
- Sheet builder: tools/prototypes/jetpac_sheets.py (moves into nexclash/jetpac.py in phase B).

## Phase A question (sent 2026-10-19)
Proposed: Jetman, aliens, rocket parts, fuel pod, bonus items, explosions -> sprites; lasers,
platforms, HUD, text -> ULA. Depth: sprites over the ULA. Colours: Dean paints
jetpac_PAINTING_SPRITES.png (sheets in specnext reference/jetpac/; built by the phase-A script,
defaults all white until painted).

## Open
- Real recording (Fuse RZX) for the differential test: the free run never builds the rocket, so
  fuel, items, take-off and levels 2+ are proven by unit tests (round 2: the rocket's own routines
  26217 / 26419 from captured states with poked rocket fields, ## Results). The synthetic
  _auto.rzx stops at frame 532 under scan (BRIEFING C2 29).
- Recolour (PLAYBOOK 3b): not built. Dean chose the game's own colours (2026-10-19), which the
  hooks take from (IX+3) at run time; a painted sheet would need per-pixel nibbles in the patterns.
- Two-player games: the alien lookup assumes (24048) is the level the aliens were built for
  (26921 runs at each level start); not exercised (the free run is 1 player).
- Erase-then-draw in one frame (the flames, 26255-26265) hides and re-shows the flame pair within
  the frame, as the original does on the ULA (round 2: the rocket's sections are no longer hidden).
- Lasers, platforms, HUD and text stay on the ULA (decision); their writers (29023, 29060, 28708 /
  28717, 28829) are untouched.

## Results (round 2, 2026-11-03)
- Quick 2000 frames: draws 6245, erases 52, colour paints 7324, clears 4, 700054 sprite pixels,
  rocket routines 1079 (178035 pixels: the standing base every frame) -> IDENTICAL.
- Unit: graphics 6480 (now incl. flames and the carried fuel pod), erase 2, clear 1, guard 1,
  rocket 37 cases x 2 frames x (flames 26217 + sections 26419) (44954 pixels; 4 rockets, 1-3
  sections, fuel 0-6, flash bit, y 183 / 163 / 150 / 41) -> PASS; negative controls: shifted
  patterns 40/40, the build without the rocket's pairs (neg_rk) 36/37 (the 37th: a lone base, no
  flames - the fault cannot show), the build dropping part 3 (neg_pt) 16/16 fuel cases.
- Full verification (selftest --game jetpac --verify --stamp, 6000-frame free run + unit + boot): PASSED, stamped 2026-11-03.

## Lessons
- [card detect.tracked-unit §Recognise] One object drew 4 figures a frame (the rocket: 3 sections in a loop + flames, same IX); a sprite set per object showed only the last, and the per-draw check passed because it compares each draw alone. Observed on hardware (user), demonstrated by the neg_rk build failing 36/37 whole-routine cases. Card: Recognise bullet + failure row.
- [doc docs/PLAYBOOK.md §6. Verify (differential test)] No RZX and a free run that never builds the rocket: the unit tests now run the game's own routines (26217 flames, 26419 sections) from a captured state with the rocket's fields poked. The lookup guard `part < 3` came from the name ("3 parts"); the game writes 3 = fuel (24858, 26041). PLAYBOOK 6 line added.
- [local: Jetpac only - the alt ROM gap 0x386E-0x3CFF is its only hook space] Hooks + tables now end at 0x3CFF with the register block: 1 byte left. Further growth needs table compaction (the fuel subtables repeat one graphic, 48 bytes) or a RAM page.
- [local: game-specific colour rule] Rocket fuel rows (per character row) done with two-index patterns (top 8 lines index 2) and the unused palette offset 8 (magenta below, white above); valid because partial fuel occurs only standing at y 183, where rows and sections align.
- [doc docs/LEARNINGS.md §2.6 Process / tokens (this sandbox)] `$!` after `setsid nohup` is the wrapper's PID: a `kill -0` wait on it ended at once (independent check, 2026-11-03); the job's PID comes from `ps`.

## Technique use
- detect.tracked-unit: corrected: its composite question missed one object drawing several figures; card amended with that case

## Stage log
- 2026-11-03 stage 4 (round 1 hardware report: 3 faults): ~2 h, ~60 tool calls, 0 user rounds; main had nothing new at the start (fetch).
- 2026-11-03 stage 4 check (no hardware report yet): independent re-verify `selftest --game jetpac --verify` PASSED (rebuild MD5s, free run IDENTICAL, unit + rocket 37 PASS, boot OK); specnext files match; two stale Patch-design / results lines corrected. ~25 tool calls.
