# Sabre Wulf (Ultimate Play The Game, 1984; 48K) - engine `sabre_wulf` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record sabre_wulf); toggles QAOP + Space, Jungle floor (1.3, engine 2026-11-07); JNext only, never on a Next.
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

## Controls (how the game reads them; 2026-11-05)
- Control select: the menu loop 0xB3F5 reads row 0xF7FE (1 / 2 players: bit 0 of 38546; keys 3 / 4 / 5 / 6 set bits 2:1 of
  38546 to 0 / 1 / 2 / 3) and row 0xEFFE (0 starts). Mode 0 keyboard (default), 1 Kempston, 2 cursor (5 6 7 8, 0), 3
  Interface 2 (6 7 8 9 0).
- 0xB0A3 (called by the player's two handlers, 0xADE5 and 0xAF0E, once a round under DI, and by the hall of fame's name
  entry 0xB6DF / 0xB71C) returns C = the action byte, Kempston's order: bit 0 left, 1 right, 2 up, 3 down, 4 fire.
  - keyboard 0xB0FA: LD A,0xFB / OUT (0xFD),A / IN A,(0xFE) / CPL / LD C,A / RET: the QWERT row as it is, Q left, W
    right, E up, R down, T fire (bits 5-7: the port's, inverted).
  - Kempston 0xB0D9: IN A,(0x1F), bits 0-3 re-ordered (right, left, down, up -> 1, 0, 3, 2), fire bit 4.
  - cursor 0xB103: rows 0xF7FE (5 left) and 0xEFFE (6 down, 7 up, 8 right, 0 fire); Interface 2 0xB0B1: row 0xEFFE
    (6 left, 7 right, 8 down, 9 up, 0 fire).
- Pause 0xAC28, called at every round end (0x9A30, after the probe 39453) and at 0x9F84, 0xA245: EI / LD A,0x7E / OUT
  (0xFD),A / IN A,(0xFE) / BIT 0,A / RET NZ / CPL / AND 0x1E / RET NZ: Space or Caps Shift (bit 0 of rows 0x7FFE and 0xFEFE
  together) with no other key of those rows pauses at 0xAC36 (border flash, waits on FRAMES); the same key resumes.
- Any-key waits: 0xB289 and 0xBD55 (all rows). Nothing else reads the keyboard (work3/scan_in.py, the recordings:
  work3/keyprobe.py: every key read at IFF 0 in mode 0).

## QAOP + Space toggle (.nxc v1.1, 2026-11-05; profile sabre_wulf_qaop, asm/sabre_wulf_qaop.asm)
Off by default; with it off every build is v1.0's byte for byte. On: 67 bytes, the same in both colour sets.
- 0xB0FA -> JP h_qaop (0x3C00, 54 bytes in the ROM's 0xFF area past the base code and register block): the QWERT byte
  made from Q (up), A (down), O (left), P (right), Space (fire), bits 5-7 the 0xFBFE read's, then the game's CPL / LD C,A /
  RET. F kept (pushed), R set to the original's (LD A,R / RLCA / SUB 70 / RRCA / LD R,A), the caller's clock, B D E H L
  untouched. About 220 T more a round at 3.5 MHz.
- The stub's alt ROM copy (bank 10 offset 0xAD) runs on to 0x3C36: the stub writes only lo..hi of the page into the alt
  ROM (z80tonex.altrom_fill), so code past the register block needs the longer copy (the verifier caught a JP into 0xFF).
- 0xAC29-0xAC35 (pause, no hook: it runs every round): LD A,0x7E / OUT (0xFD),A / OR 0x80 / IN A,(0xFE) / RRCA / RET C /
  NOP x3: the game's own OUT (0x7EFD, 0x7E: LD A,0xFE before it would have sent 0xFE to 0xFEFD, the AY select port on a
  128K decode), then row 0xFEFE alone: Caps Shift pauses. 6 M1s as the original's (R the same), 3 T more. A and F at the
  return are dead (0x9A3C, 0x9F87, 0xBB7C write both first). Caps Shift with Z X C V held pauses too (the original's
  other-keys test does not fit in 13 bytes). Resuming is the game's own: Space or Caps Shift.
- Clash: Q was left and is now up; Space was pause and is now fight. With the toggle on the read is replaced, not added
  to: W E R T do nothing, Space never pauses. Kempston, cursor, Interface 2, the menu keys and the any-key waits are
  untouched; with a joystick chosen the pause key is Caps Shift too.
- Proof (work3/): replay with the key sites forked (sabre_wulf.key_event: the recording's QWERT byte for the original,
  qaop_ports' four half-rows for the build), every other hook as in v1.0, the Enhanced build beside it; unit tests
  (qaop_units); negatives (O and P swapped, down read from Caps Shift, R one off, pause bytes left, keys as recorded); an
  exact lockstep in the simulator (work3/lockstep_sim.py) and JNext trials (work3/trials_q.py) on fixture 2. Results in
  the run's REPORT.md.

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
colours (see the next section for the orchids and Sabreman). No white outlines in either set.

### Orchids and Sabreman in a painted set (2026-11-07, reported by a player on jattree/nxc #1)
In the original the orchid's colour tells the player its effect, and Sabreman takes it while it acts (colour table
42749: 0x42 red slows him (max speed 32, 44997), 0x45 cyan speeds him (64), 0x43 magenta reverses the controls
(44820), 0x46 yellow holds him (44792), 0x47 white is normal; timer 38576, the white flash below 47). A plant is painted
by cell rows: the bottom row bright green (42674), the row above in IX+5 (42689; frame & 7 = 0: none); 3 cells wide at
full bloom. Painted pixels are fixed, so a painted set loses both cues.
- Orchids: the colour map gives the plant frames' upper cell row nibble 1 (the run-time colour) except black outline;
  data only (the pilot's map, not in the repo).
- Sabreman: the Enhanced hooks (`load_eprofile`, asm/sabre_wulf_enhanced.asm, SABREMAN_BANKS) show object 0 in palette
  offsets 0-7 (his ink, no +8). Every colour the game gives an object is bright (39579, 40412, 41412, 42744, 42893;
  tables 39608, 41895, 44151), so offsets 0-7 are his alone. The setup gives his part entries (`sabparts`: 5, 6 = helmet,
  shirt, trousers in the painted set) the bright ink in offsets 0-6, offset 7 (white: no orchid acting) keeps the
  painted colours, and entry 1 is bright in 0-7. Apply: INC L / DEC L / JR Z (L = 8i in the state pointer); the two
  INC HL / DEC HL pairs in apply and show (no effect) go, so the image is the base's length and every address the
  game and the stub use is the base's. The default build is unchanged byte for byte.
- `sabreman_banks(nex)` swaps the Enhanced hooks and setup into a built (and recoloured) .nex, base or QAOP.
- Verify: `enh=` with the Enhanced hooks accepts exactly the bright bit clear on Sabreman's sprites, his state +6 and
  SCOL, and ignores the dead stack below the return (return addresses into hook code moved by 2 bytes); the unit
  colour cases and `event` use `palette_offset`.
- Results (pilot runs/sabre_wulf work4, simulation): 5 recordings IDENTICAL, all 283,009 events beside the default;
  colour model at 85,046 frames (every orchid and Sabreman pixel in the palette the setup writes, also against the
  original's attributes); unit tests and the 268-case clock matrix of the Enhanced hooks pass; negatives (1.1's set,
  1.1's palette, 1.1's hooks, 1.1's map) detected. JNext: 1.1 against 1.2 Enhanced 30 pace trials -0.01 to +0.03%.
  Never run on hardware.

## Jungle floor toggle (.nxc v1.3, 2026-11-07; profile sabre_wulf_floor, asm/sabre_wulf_floor.asm)
Display only, with the Enhanced colours: a dim floor of grass tufts, stones and twigs on the black ground of each room,
pebbles in the six cave rooms. Off by default; with it off every build is 1.2's byte for byte. Jungle floor art: Jon
Attree (assets/sabre_wulf: jungle.png and cave.png, the 128 x 96 tiles as Layer 2 palette indices 0-5; jungle.rle and
cave.rle, their rows as the asm includes them; `floor_code` refuses a profile whose pictures are not the .png files).
- `jungle_floor(nex)`: the last step on a built .nex of this engine (default, QAOP + Space, either with its Enhanced
  set): the 1,504-byte block at 0xF200 in the state page (bank 11 offset 0x1200; zero in every build, as are DRAWN
  0xF17F and the row buffer 0xF180-0xF1FF) and e_clr's CALL leave (0x3908) -> CALL floor (bank 12 offset 0x1909).
  1,456 bytes change, the same in all four builds. recolour and sabreman_banks refuse a floor build; so does a second
  jungle_floor.
- The floor runs at the end of every clear (47964), before leave (R, slots, clock: leave's). The game's return
  address says what comes next: a room (45399, 45543, 45582, 41550) -> Layer 2 shown for room (38659), anything else
  (title, game over, ending, amulet display) -> hidden. Cave = the room's item list holds the rock 0x847C (rooms
  135-137, 151-153). A room's arrangement is Layer 2's scroll, X 16 (room & 7), Y 16 ((room >> 3) mod 6): the tile
  2 x 2 in banks 18-20 (jungle) and 21-23 (cave), drawn once at the first clear (the title's). Layer 2 under the ULA
  (0x15 = 0x09), the ULA's black (palette 0, 8, 16, 24) the transparent colour, fallback black, clip lines 16-191.
- In the .nxc: menu name `FLOOR_NAME` ("Jungle floor"), kind 3 (display only), with the rule "Jungle floor needs
  Enhanced". The engine builds equal the published 1.3 (jattree/nxc d4aeed3) for every combination it allows:
  332c9526, +QAOP 72f236e2, Enhanced edb28374, Enhanced + floor 3a69c783, Enhanced + QAOP 471d4bef, Enhanced + QAOP +
  floor 95cfba3e (Enhanced = the pilot's colour map and palette as 1.2's, then jungle_floor). Default + floor (not
  allowed by the rule): 8c3af3e5, + QAOP b3508eed.
- Verify: `verify_floor(rzx)` (needs numpy): at every clear the original and the floor build from one state, as
  `event`: every register with R, IX IY I IFF, stack, game memory, screen writes, slots, clock and 0x243B; only the
  floor's NEXTREGs, port 0x123B and palette entries; Layer 2 against `floor_model` (bank, scroll, order, clip,
  palettes, its 96K the art 2 x 2, never written after the first clear); and each room's picture composed as the Next
  shows it: the original's where the ULA is not black, the room's floor where it is. `floor_rooms(z80)`: all 256 rooms
  in the simulator. `floor_negatives`: wrong arrangement, the floor over the ULA, no cave variant.
- Results (2026-11-07, simulation): 5 recordings IDENTICAL, 821 clears, 808 rooms shown (158 in the cave, rooms
  151-153), 808 pictures composed; floor_rooms 256 of 256 match, caves 135-137 and 151-153; negatives on sw_nocheat 3 of
  3 detected, in floor_rooms 2 of 2 (the floor over the ULA does not change the bank or scroll). JNext 1.1.104 (pilot
  runs/sabre_wulf work5): Enhanced + floor flicker and 15-minute soak clean; pace against 1.2's Enhanced -0.04 to
  +0.05 % (30 trials). Never played by a person; never on hardware.

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
Enhanced (verify enh=, pilot work2/verify_all.py): all 283,009 hook events beside the default, the same registers, memory,
state and attributes, every shown unit the set's bytes. Unit PASS: frames 3,276 positions, guards, colours, states; the
every-site clock matrix 268 cases in each set. Negatives, each a replay of sw_roam1's first 10,000 frames (pilot
work2/negative.py): 14 of 14 DETECTED (patterns shifted, one row write left, HL and DE swapped, clear leaves sprites on,
move ignores the old image, colour ignored, x off, y off, never uploaded, slot 7 not restored, forced 3.5 MHz exit at
7 MHz, R one off, the cache replaces a shown frame, player frames point elsewhere); controls at 3.5 and 7 MHz clean;
Enhanced: default patterns shown, x off: both DETECTED, control clean.
JNext 1.1.104 (pilot runs/sabre_wulf/jn2): pace, pilot work2/trials.py, fixture 2, probe 39453, 10 trials a scene:
| Scene | approved build b60fd71e | this build | Enhanced, approved b5dce79b | Enhanced, this build |
|---|---|---|---|---|
| quiet | +2.58 % | +1.67 % | +2.58 % | +1.67 % |
| busy | +2.49 % | +1.48 % | +2.49 % | +1.48 % |
| sound (fight held) | +2.61 % | +1.68 % (9 measured) | +2.61 % | +1.68 % |
Hook time 0.9 % of the time at 28 MHz, the rest the 3.5 MHz entries and exits. Flicker 300 frames, both sets: 0 out of
step, 0 vanished, 0 transients. Soak 15 minutes, both sets, against the .z80: no freeze, loop or crash; play, game overs,
restarts on the sheet. The .nxc's menu builds reach play in both sets, cheats on and off.

## Hardware checklist (nothing here has run on hardware)
1. Boot the .nex: the loading screen waits for a key (BASIC's PAUSE 0); any key, the title; 0 starts.
2. Walk through several rooms: figures keep their colours over foliage; foliage keeps its own.
3. Enemy speed as the plain build. Fight (T). A hit flash on the player.
4. Lose all lives: game over text with no figures left over, hall of fame, restart.
5. Enhanced (menu): the painted colours; the speed key F8 mid-game changes the game's speed and the hooks keep it.
6. Jungle floor (menu; turns Enhanced on): a dim floor on the black ground in each room, none over the panel or
   the plants' colours; pebbles in the cave rooms; the title, game over and hall of fame show no floor.
Hardware risk review: hooks 0x386E-0x3B71, not in DivMMC's 0x3D00-0x3DFF. IM 1 needs ROM 0x0038 = Sinclair's (the image).

## Open
- Never run on hardware. JNext only.
- Pace: the hooks cost about 1.5 % of the rounds' time (below 2 %, never faster); a pace window over the paint loop could
  repay it, not built.
- Joysticks not exercised; the amulet and the cave not played.
- Jungle floor: shows through the black between the plants' leaves too (accepted for 1.3); the first title screen
  after loading waits about a tenth of a second while the pictures are drawn.

## Lessons
- [local: this game's pace] demonstrated: the approved build's paint NOP made each painted cell 3 T faster; CP (HL) keeps 7 T and the cell access, and a build with only the screen sites stays in lockstep with the plain build for 600 rounds (+0.00 %).
- [local: this game's pace trials] demonstrated: enemy pace follows rounds per second and the player's once-a-frame gate makes runs drift apart; with every time source of the logic read from the round counter in both runs (pilot work2/fixture2) the trials stay in lockstep for 160-600 rounds.
- [local: this game's RNG] observed: R at 39376, 40484, 41707 and FRAMES in ten places give the game its chance; the hooks preserve R, the pace trials take both out.
- [local: the archive's trainers] observed: of 16 .pok trainers, See Ending and Paralyzed Enemies freeze the game, Keep SabreMan cyan sets colour 186 and stops the orchid effects ending, Immunity still loses lives; the menu keeps the six shown to work (pilot work2/cheats).
- [local: this game's Enhanced map] demonstrated: a fixed palette entry painted on a pixel the game colours at run time (the orchid bloom, 2026-11-07, jattree/nxc issue #1) hides the game's cue; the orchid's upper cell row now takes the run-time colour and Sabreman's helmet, shirt and trousers follow his effect colour (5 recordings identical, pilot work4).
- [local: this game's Jungle floor] demonstrated: a display-only toggle whose bytes are one block in free state-page
  space and one CALL operand is the same in every build, so the engine adds it as a last step (jungle_floor) on any of
  the four builds instead of four more hook profiles; the published 1.3 builds come out byte for byte (2026-11-07).

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
- 2026-11-07 Jungle floor toggle (.nxc v1.3) moved into the engine: asm/sabre_wulf_floor.asm, profile sabre_wulf_floor,
  art in assets/sabre_wulf, jungle_floor / verify_floor / floor_rooms; the published builds reproduced byte for byte.
