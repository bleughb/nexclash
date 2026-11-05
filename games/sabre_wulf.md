# Sabre Wulf (Ultimate Play The Game, 1984; 48K) - engine `sabre_wulf` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record sabre_wulf); JNext only, never on a Next.
Inputs: specnext/reference/sabre_wulf/ (sabre_wulf.z80 md5 d8fb649b = TOSEC "Sabre Wulf (1984)(Ultimate Play The Game).z80";
sw_nocheat, sw_two, sw_roam1, sw_roam2, sw_ending). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card.
Start with: the hardware checklist below. Open: under "Open".

Techniques: `detect.gameplay-screen-readers`, `patch.whole-altrom-image`, `patch.restore-speed`, `patch.preserve-r`,
`optimise.pattern-cache`, `verify.update-locked-pace` (recipe and results: docs/records/sabre_wulf.json)

## Import (2026-11-05)
Ported from Jon Attree's .nxc work, 2026-11-05 (pilot clone runs/sabre_wulf/nexclash, base d7abd1c, head 1c7647c). The
owner approved the look of that build in JNext on 2026-11-03: sabre_wulf_sprites.nex b60fd71e (the game's own colours)
and its Spec256 set b5dce79b ("eh .......wowow!!!"). Its .nxc was never published. This port is a new build, not a byte
rebuild: it takes the new defaults and changes the hooks' timing, never the picture. Both sets' pattern pages and the
Enhanced palette are byte-equal to the approved builds' (pilot work2/enhanced.py).
- Whole alt ROM image (patch.whole-altrom-image) in both builds; the plain build carries Sinclair's ROM too. The old fill
  ran IM 1 over the hooks at 0x386E (pilot runs/altrom_audit: "UNSURE (masked)").
- Start: the snapshot's own BASIC (PAUSE 0: RANDOMIZE USR 24576), no stub (START_STUB = False keeps the old one).
- The caller's speed latched at entry and restored at every exit (patch.restore-speed: speed_in / leave; the latch is in
  the state page, so the read is HLIB_SPEED_IN's sequence with the page mapped after the NEXTREG).
- R as the original's (patch.preserve-r): the game takes chance from R (39376, 40484, 41707). Each hook reads R at entry and
  sets it in leave to entry + D_xxx (asm), measured on the verifier.
- Paint site LD (HL),D -> CP (HL), not NOP: 7 T and one access of the cell, as the write (the NOP was 3 T a cell faster).
- Speed pass: no sprite write when the object's frame, x, y and palette offset are as last shown; the object index from a
  table (IXT); patterns from a frame cache in pattern RAM (below).
Published .nxc: Sabre Wulf v1.0 (pilot runs/sabre_wulf/out/sabre_wulf_v1.0.nxc), target the TOSEC .z80.

## Inputs
Snapshot: the TOSEC "Sabre Wulf (1984)(Ultimate Play The Game).z80", md5 d8fb649ba5d8fa086cac43d0cd1c497e (the file of the
2026-11-03 engine). 48K. Stops in ROM PAUSE on the loading screen: the edit line is PAUSE 0: RANDOMIZE USR 24576. The tape's
picture is not a standard 6,912-byte block (the TOSEC .tap's 35,936-byte block at 24576 is unpacked by its loader); the
snapshot holds it on screen and the build shows it from bank 5 while BASIC's PAUSE 0 waits.
Keys: any key, wait, 0 starts (menu: 1 / 2 players, 3 keyboard is the default, 4-6 joysticks). In play Q left, W right,
E up, R down, T fight, SPACE pause.
Recordings (no Fuse, no human; pilot work/bot.py and work/rec_end.py; cheats change code in the RZX's own snapshot):
| Recording | Cheats | Reaches |
|---|---|---|
| sw_nocheat | none | rooms near the start, deaths, game over, hall of fame, menu, restarts |
| sw_two | none | two-player games, game over |
| sw_roam1 | lives (43575), immunity (43848) | 17 rooms, enemies, orchids |
| sw_roam2 | same | 34 rooms |
| sw_ending | room test removed (41361) | the ending text, game over, hall of fame, a new game |
Not played: the amulet collected by a player and the walk into the cave. All 182 non-empty frames are in unit tests.

## Clash
Kind A. work/census.py (pilot): sampled plots spanning more than one attribute value 20-22 %, figure pixels in a colour not
their own 17 %. The paint routine 47941 gives a figure's cells its ink wherever paper is 0, so foliage takes the figure's
colour and overlapping figures share. Owner's eye: clash. Menus: no option changes the drawing.

## Rendering model
Pure XOR, no mask. Rows are XORed through shift tables at 0xF000-0xFFFF. Move = one routine alternating old row and new
row. Object IX: IX+0 frame (also its type: handler table 39742), +1 room, +3 x, +4 bottom line, +5 colour; saved image at
38559-38561. 47529 toggles both, 47385 the object's, 47349 the saved. Frame table 49028: width bytes, height, rows bottom
up. 25 objects at 38658, stride 12. Toggling is exact: 0 cases of an object showing a second image across the recordings.
No game logic reads the screen except the XOR itself and the paint routine's paper test.
Pace: the round robin at 39346 has no frame cap. The player runs once a frame (FRAMES gate, DI), the enemies as fast as
the CPU allows, so enemy pace = rounds per second (probe 39453, the round's end). The row loops keep running.

## Design
| Site | Original | Now |
|---|---|---|
| 47529, 47385, 47349 | CALL | toggle the image in the object's state, show it, then the original CALL |
| 47908 | LD L,(IX+3) | show the object again if its colour changed (a hit flash changes IX+5 for one paint) |
| 47964 | LD HL,16448 | all sprites off, every image ended, no frame referenced |
| 32 row writes | LD (HL),A | LD A,(HL) |
| 47948 | LD (HL),D | CP (HL) |
Object i has sprites 4*(24-i).. +3, player on top. Frames are preconverted 4-bit patterns in Next pages from 26 (128-byte
units). Frame cache (optimise.pattern-cache): the 128 pattern units of pattern RAM hold canonical frames (frames sharing a
graphic and colour rule share one id); UL holds each resident frame's units, UOWN each unit's frame, REF the objects
showing it. A frame not resident takes units by a clock hand, skipping any unit of a frame with REF > 0, and is uploaded
once. Hooks at 28 MHz in alt ROM image 1 (0x386E-0x3B71), state and tables in page 22 at slot 7, sources at slot 6.
Interrupts stay on: the ISR touches the stack and the system variables only (`isr`).
Colour: palette offset = ink + 8 if bright, entry 1 of each offset. Entries 2-15 are the same fixed colours in every offset,
for painted pixels. Plant frames 72-79: bottom 8 rows bright green, as the game's 42674 paints them.
A' after a plot holds the last row byte, which depends on the screen, so the verify does not compare it; aprime_probe
scrambles it through each recording: same memory at the end, no desync.

## Enhanced set
Painted from the Spec256 conversion's colours: `Sabre Wulf.256` (Spec256-256-all38, built from the Spectrum Magic zip
Sabrew.zip, the same SABREW.GFX as the MVV package, whose readme says "Recolouring by: Spec256"; no painter named).
100 % of 7,619 graphics bytes match; paint/colours.json (6,847 entries) applied by `recolour`, palette entries 2-15 from
paint/palette.hex in the setup code. Khaki Sabreman, coloured parrot, pale spider, dusky scorpion. Painted pixels are fixed
colours, so Sabreman's colour no longer shows the orchid effects. No white outlines in either set.

## Verify (what it checks)
Per hook event, original and patched run from the same state to the enclosing routine's return: every register but T /
MEMPTR, R included (A' excluded after a plot, above); IX, IY, I, IFF never changed; hook stack depth; no screen writes;
game memory equal; slots 6 and 7 back, the incoming speed back, port 0x243B on register 7; the sprite change equals the
original's XOR toggle bit for bit; palette offset = the object's colour; no pattern unit another sprite shows is written.
Once a frame: screen XOR every visible sprite = the scenery, unchanged since the last clear. Enhanced (verify enh=): its
hooks beside the default's at every site: the same registers, memory, state page and attributes, and each shown sprite's
unit holds the set's bytes of its object's frame. Unit: every frame at 9 x and 2 y positions, guards, colours, states, and
the every-site matrix (hooklib.every_site: each captured entry at NR 7 = 0-3, the same results, its clock back).

## Results (2026-11-05; simulation only)
Builds: sabre_wulf.nex 06fbcf50, sabre_wulf_sprites.nex 332c9526, Enhanced f156d50d (work2/enhanced.py); boot OK.
| Recording | Frames | move | toggle | old | paint | clear | sprite pixels | screen checks | Verify |
|---|---|---|---|---|---|---|---|---|---|
| sw_nocheat | 20005 | 2715 | 86 | 1 | 2929 | 13 | 235914 | 1766 | IDENTICAL |
| sw_two | 20005 | 2086 | 47 | 0 | 2454 | 6 | 150245 | 1378 | IDENTICAL |
| sw_roam1 | 40005 | 69864 | 2515 | 44 | 64927 | 370 | 7410745 | 40386 | IDENTICAL |
| sw_roam2 | 40005 | 68083 | 2708 | 46 | 63157 | 425 | 7459295 | 40375 | IDENTICAL |
| sw_ending | 3745 | 206 | 7 | 0 | 313 | 7 | 1038 | 333 | IDENTICAL |
Every hook ran (old: 91 calls in all). A' probe: no effect on all 5. ROM paths: both builds, every ROM byte the game runs as
recorded; the tail never read before written.
RESULTS-PENDING

## Hardware checklist (nothing here has run on hardware)
1. Boot the .nex: the loading screen waits for a key (BASIC's PAUSE 0); any key, the title; 0 starts.
2. Walk through several rooms: figures keep their colours over foliage; foliage keeps its own.
3. Enemy speed as the plain build. Fight (T). A hit flash on the player.
4. Lose all lives: game over text with no figures left over, hall of fame, restart.
5. Enhanced (menu): the painted colours; the speed key F8 mid-game changes the game's speed and the hooks keep it.
Hardware risk review: hooks 0x386E-0x3B71, not in DivMMC's 0x3D00-0x3DFF. IM 1 needs ROM 0x0038 = Sinclair's (the image).

## Open
- Never run on hardware. JNext only.
- Pace: the hooks cost about 1.5 % of the rounds' time (below 2 %, never faster); a pace window over the paint loop could
  repay it, not built.
- Joysticks not exercised; the amulet and the cave not played.

## Lessons
- [local: this game's pace] demonstrated: the approved build's paint NOP made each painted cell 3 T faster; CP (HL) keeps 7 T and the cell access, and a build with only the screen sites stays in lockstep with the plain build for 600 rounds (+0.00 %).
- [local: this game's pace trials] demonstrated: enemy pace follows rounds per second and the player's once-a-frame gate makes runs drift apart; with every time source of the logic read from the round counter in both runs (pilot work2/fixture2) the trials stay in lockstep for 160-600 rounds.
- [local: this game's RNG] observed: R at 39376, 40484, 41707 and FRAMES in ten places give the game its chance; the hooks preserve R, the pace trials take both out.
- [local: the archive's trainers] observed: of 16 .pok trainers, See Ending and Paralyzed Enemies freeze the game, Keep SabreMan cyan sets colour 186 and stops the orchid effects ending, Immunity still loses lives; the menu keeps the six shown to work (pilot work2/cheats).

## Friction
- reuse: [local: the round-counter fixture is this game's; nexclash.pace has no fixture support]
- retries: [local: the first pace trials kept the frame gate and drifted apart within 100 rounds; fixture 2 fixed it]
- environment: [local: NEXCLASH_NEXT_ROM (enNextZX.rom) and NEXCLASH_JNEXT_CARD point into other pilot runs, read only]
- hand-rolled: [local: the Enhanced replay beside the default (verify enh=) is this engine's]
- scratch: [none: scratch scripts stay in the pilot run folder, none added to the repo]

## Technique use
- patch.whole-altrom-image: helped: also removed the start stub.
- patch.restore-speed: helped: the every-site matrix and the 7 MHz replay caught the forced exit.
- patch.preserve-r: helped: R compared at every hook; the one-off negative caught.
- optimise.pattern-cache: helped: frames an animation comes back to are not uploaded again.
- detect.gameplay-screen-readers: helped: `scan --writers` showed the XOR plotter and paint routine as the only readers (2026-11-03).

## Stage log
- 2026-11-03 stages 0-3, one unattended session, no user rounds.
- 2026-11-05 import (pilot runs/sabre_wulf/nexclash2 on refactor-final f6b8ac0): new defaults, start without the stub, speed
  latch, R, frame cache, every-site matrix, Enhanced replay, negatives, pace / flicker / soak in JNext, .nxc v1.0.
