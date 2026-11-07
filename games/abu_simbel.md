# Abu Simbel Profanation (Dinamic 1985, 48K) - engine `abu_simbel` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware)    State: v1.0 published as nxc 1.0 (2026-11-07), proven in the simulator and JNext; never run on a Next.
Inputs: the run folder (abu_simbel.z80 md5 2909c2f0, recordings rzx/*.rzx, pace fixtures v10/pace/), handoff HANDOFF-V1.0.md.
Start with: the hardware checklist below (EAR bit 6, 28 MHz pace).
Read: "v1.0" first (it replaces the design below where they differ). Open: "Open".

Techniques: `detect.gameplay-screen-readers`, `patch.runtime-colour-map`, `patch.restore-speed`, `patch.preserve-r`,
`patch.pace-limiter` (recipe, owns and results: docs/records/abu_simbel.json)

## v1.0 (2026-11-07): rebased on main 102091f, shared hook library, original pace
Design change: the plotter is no longer edited. The hook builds the sprite pattern (page 31 code at slot 7), copies the box's
attributes into page 31, maps page 31 into slot 2 and CALLs the plotter whole at 28 MHz: every screen and attribute byte it
writes lands in page 31 (below 0x1B00; the hook's state is above), never shown. Its only slot-2 reads are the box's
attributes (BIT 6 decides whether it reloads ATTR-T, so the copy keeps its path, R and time the original's) and ATTR-T (only
written back). Sites: AD1D, B465 (plots), BD36, A361 (hides), DE98 EI -> NOP (an interrupt between the plotter's EI and the
hook's restore of slot 2 would run the ROM ISR on page 31's sysvars); the old LDIR stand-ins and the attribute NOP are gone.
The stack is in slot 3 (0x65xx), checked at every site.
Libraries: HLIB_SPEED_IN/OUT, HLIB_R_IN/OUT + hlib_r_set (delta = R after - R before the plotter - 22), hlib_pace (full).
Pace: the plot is a game-routine window x K_PLOT 100 (JNext measured the original's plot time over the plotter's 28 MHz
time at 110.6 player / 111.6 enemy; at 111 the game ran +0.3 to +0.7 %, as the rest of the Next build runs about 0.4 % slower
than the .z80 on a 48K machine; owner's rule 2026-11-07: never slower, so 100); the pattern work is debt (UNMEAS 96/16 lines: entry, exit, gaps and the window's own 28 MHz overhead
x K, less the wait's rounding, +6 from JNext). Interrupts stay off through the hook, as through the original plot.
Pace control: the original .z80 on a 48K machine, not the plain .nex: NextZXOS's ROM3 BEEP (the game's sound, ROM 0x03F8)
runs 12% faster than Sinclair's, so the plain .nex is faster than the original in sound scenes. Fixture: RND's seed moved
from FRAMES to 0x5CB0 in both (test only), so original and build stay in lockstep.
26.11: alt ROM image 1 is Sinclair's whole 48K ROM (bank 47, z80tonex ALTROM_FILL whole), so NextZXOS's ROM3 is never run;
the game prints through RST 10 and beeps through the ROM. OPT1 top bank 47: fits a 1MB Next with every option.

### v1.0 results
| Output | MD5 |
|---|---|
| abu_simbel.nex (plain) | 82c1349ae5d34e68a67a7aabc68e039f |
| abu_simbel_sprites.nex (v1.0) | c2dd86f174c55a4ae9155abb90689d8b |
| abu_simbel_enhanced.nex | b45603707d1f71bb7704436dbe0c3169 |
| abu_simbel_english.nex | 2e3aa22510d9a925a5b0800aad3f26c9 |
| abu_simbel_english_enhanced.nex | 053806e52684ce68b89a020a848e7196 |
The sprite build and the three sets are the bare builds of the published nxc 1.0 (`nxc.py --bare`, nothing chosen /
Enhanced / English / both), byte for byte. With the three cheats as well (abu_simbel.pok, the record's reference input)
the all-options build is fda9c1b267aeb6220ad0bb8032e54895, also the published one.
Replay (auto, 10 recordings, 69,928 frames): player 26,065, enemies 49,362, clears 87, 6,367,816 sprite pixels, CMP_R
registers, IDENTICAL; the model pace (28 MHz = K/16) -0.18 to -0.55 % per recording. Enhanced table on attract, gameover,
c_r32: IDENTICAL. Unit PASS: 630 positions, 78 graphics, 48 inks, depth 12, guard 4, every-site matrix 48 cases; 18
negatives caught (x/y off by one, ink ignored, depth both ways, slot 2/5/7 left mapped, screen not redirected, EI kept,
R off by one, R in the hides, limiter never waits, speed forced to 3.5, HL clobbered, enemy index, no hide, wrong image).
JNext pace (nexclash.pace vs the original .z80, lockstep), K 100: 19 runs, base / Enhanced / English, rooms 1, 16, 32,
attract, -0.73 to -1.70 % (quiet thirds to -2.08 %, slowest 20-update window +0.17 % in attract); 26.11 card the same. English builds stay in lockstep with the Spanish original.
Cheats (simulator, alone, 3 seeds): Immunity B0EF C3, Infinite lives BA44 00, No enemies B335 C9 (the archive's
"Transform objects"); left out: BA4D (same as BA44), Lives (asks), Invulnerability (hangs in water), BA28 (unclear).

## Inputs
Snapshot: archive "Abu Simbel Profanation (1985)(Dinamic)(ES)[a][a].z80", md5 2909c2f0f18eca08479a74ad6dc8d193, chosen against its .256: 99.12 % of non-zero bytes match and all 3,456 graphics bytes plotted. The clean (Dinamic)(ES) file matched 98.71 % and stayed on the menu for 1,200 frames with no attract. Gremlin re-releases matched 95 %. ZXDB filecheck: 502, tried once; no ZXDB id in the patch.
48K, no 128K release seen. Stopped in the menu music: PC 0x03E7 ROM BEEPER, DI. `inspect` calls it a loader; the game is running.
Keys: menu 3 keyboard (hold it: read between notes). O left, P right, A-G row high jump, Q-T row low jump, CAPS+SPACE quit, 1 + ... pause. Compiled BASIC.

## Port FE bit 6 (matters on hardware)
Play compares whole port-FE values (0xBE, 0xBF, 0xA7), so EAR must read 0. The toolkit's recorder returns 0xFF: the game ignored every key. Recordings here use the Issue 3 rule (work/lib.py issue3). JNext gives bit 6 = 0 and the plain and sprite builds both move. A real Next's EAR input is unchecked.

## Rendering model
One plotter 0xDD78, two callers: player 0xAD1D, enemies 0xB465 (loop 0x971A = 0-2). Block 0x9700: new y, x, graphic, old y, x, height 16, width 2. Graphics 0xC800- (enemies), 0xD300- (player), 32 bytes.
0xDED3 paints ATTR-T (0x5C8F, always 1-7) over every non-BRIGHT cell of the box and leaves BRIGHT cells. 0xDEF7 LDIRs rows opaque. 0xDF12 LDIRs zeros over what it left.
So: scenery that is not BRIGHT takes the figure's colour and loses its pixels; a figure in a BRIGHT cell takes that cell's colours; in a BRIGHT cell with ink = paper (water 0x49, white 0x7F) it cannot be seen. That last is the game's depth rule: balls sink behind water and ice.
Collision: 0xFDE8 reads 3 attributes, `CP 0x40`; 0xAFDC-0xB095 compares them with 0x4F, 0xC1-0xC7, 0xCD, 0x40, 0x41, 0x49. All >= 0x40, so figures' paint cannot change a decision.
RND (0xA36A) reads FRAMES, so game randomness depends on timing in any build.

## Clash (work/clash_check.py)
No menu option changes the drawing (menu: Kempston, keyboard, instructions). Figure plots spanning several attributes 0.0-4.5 %, ink in another colour 0-1.6 %, ink hidden in solid cells 3.1 % in attract. Scenery cells repainted with pixels in them: 196-1,575 per recording, up to 26,494 pixels. Kind A, low figure share, the larger part being scenery recoloured and wiped. The owner's "clash" stands: png/same_r24.png.

## Design (defaults, unattended)
Sites in asm/abu_simbel_hooks.asm. The plotter keeps running; 0xDED3 NOP; both LDIRs get stand-ins that copy source onto itself for LDIR's own flags. Sprites: enemies 0-2, player 3. Patterns built each plot, double buffered, 2 slots a sprite. Hide at room redraw (0xBD36) and CLS (0xA361).
Depth kept: pixels in BRIGHT cells with ink = paper are transparent (mask per cell row, in the hook).
Colours: the plot's ink; palette 1-7 Spectrum, 8 black, 9-15 bright. Map pages 28-30 (slot 5 in the hook), state page 31 (slot 7).
Turbo: hook and first part of the plotter at 28 MHz, stand-ins at 28 MHz. Attract in JNext: about 4 % behind the plain build at frame 4,900.
Tail 0x6000: zero, untouched in all 10 recordings.

## Results
| Output | MD5 | Status |
|---|---|---|
| abu_simbel.nex | 82c1349ae5d34e68a67a7aabc68e039f | boot OK, reaches play in JNext |
| abu_simbel_sprites.nex | 102c92e393c7eaa4aa416dc1542abb2e | 10 RZX IDENTICAL, reaches play in JNext; hardware untested |
| abu_simbel_spec256.nex | 2b1ccc19d2ba6570f3b6e702e3d93c6b | recolour of the above, reaches play in JNext |
Hooks over 10 recordings, 69,928 frames: player 26,065, enemies 49,362, room clear 76, CLS 11, first LDIR 1,206,816, second 215,464, attribute write 567,897. None idle.
Negatives 16 of 16: 14 on gameover.rzx, the two depth ones on attract.rzx, which reaches solid cells. An earlier run missed "stand-in leaves C": C is dead by the plot's return, so verify now compares one LDIR in five directly.
Whole-game (work/wholerun.py): original against no-figure-writes plotter, input by poll count, FRAMES ticked in the game's loops: plot arguments identical in order, 8 runs. RAM differs only at 0x5BFA-0x5BFC, the last raw attributes read.
Unit tests (auto on gameover.rzx, 1,500 frames): see work/unit.log.

## Coverage
Enemies in all 44 rooms that have them (attract); room 33 has none. Player in 13 rooms: 1, 2, 7, 8, 9, 16, 21, 24, 26, 30, 32, 35, 40. Game over to credits. Not reached: the ending 0xA791; door routine 0xA58E never checked by eye.

## Defaults taken (a human would have decided)
1. Every figure a sprite. 2. Scenery, HUD, text ULA. 3. Depth as above, sprites over all other scenery. 4. Colours the game's ink. 5. Paper of a figure transparent where the original was opaque: scenery now shows through and is no longer wiped.

## Open
Hardware: bit 6; speed; tearing. A figure whose erase was relied on by scenery: none seen. Spec256 set is the owner's to judge.
v1.0: two Failure lookup rows for card patch.pace-limiter (K-window overhead as debt; the .z80 as control for ROM-beep games), deferred while the card is at its word budget. The real loader on the 26.11 card for this patch (its welcome screen needs other keys; JNext ran slowly on it).


## Lessons
- [deferred Open: reconsider when card patch.pace-limiter has room under its 600-word budget (Failure lookup row)] The plain .nex is not always the pace control: its ROM is NextZXOS's ROM3, whose BEEP ran 12%
  faster than Sinclair's in JNext; a game that beeps through the ROM needs the original .z80 (48K machine) as control.
- [local: redirecting a routine's screen by MMU] Reads in the remapped slot can still decide the path (BIT 6 on attributes):
  R and time differed until the box's attributes were copied into the scratch page.
- [deferred Open: reconsider when card patch.pace-limiter has room under its 600-word budget (Failure lookup row)] Window overhead at 28 MHz is multiplied by K: account it as debt, or the target grows.
- [local: a game that compares whole port values] `record` returns 0xFF on port FE and the game ignores every key, with no warning: an Issue 3 recorder (work/lib.py) fixed it. The recorder could offer this.
- [local: the picture check found the depth rule] Verify passed with figures showing over water and ice, because its model was mine; only frames beside the original showed the balls should sink. The rule then went into the model and the negatives.
- [local: dead registers pass a compare at the return] A stand-in that left C wrong passed at the plot's return, as the next row reloads it; compare at the stand-in.
- [local: a negative control is only as good as its recording] The depth controls were missed on room 1 and detected on attract, which reaches solid cells.
- [local: outputs moved after the last tuning] The record and notes kept the K 111 build's MD5 after K went to 100; rebuilding
  against the published patch found it. Rebuild from the record after the final change, not before.

## Friction
- reuse: [local: nexclash.pace and hooklib.every_site used as they are; the verifier's Next model follows hooklib.NextModel]
- retries: [local: the first pace runs used the plain .nex as control and read +4 %; the per-plot JNext timing found the BEEP difference]
- environment: [local: the shared venv has no `z80` package, so the nxc repo's menu tests ran from a private venv; JNext was slow with other agents' runs]
- hand-rolled: [local: an RND-seed pace fixture (run folder v10/work/fixture.py), test only]
- scratch: [none: the run folder's v10/work scripts stay there; nothing added to tools/]

## Technique use
- detect.gameplay-screen-readers: helped. patch.runtime-colour-map: helped, 4 bytes per graphics byte.

## Stage log
2026-11-03 stages 0-3, about 50 min wall, one session, no user rounds.

## Enhanced and English sets (in the engine since nxc 1.0)
`auto` writes both from the sprite build: `enhanced()` recolours it with docs/profiles/abu_simbel_enhanced.json (the
Spec256 colours approved 2026-11-03, from Spectrum Magic's older Spec256 conversion, painter not established; bank 14
only); `english()` writes docs/profiles/abu_simbel_english.json's text (English text: NextTang) into banks 5, 2 and 0,
refusing any byte that is not the game's own in the build, so no hook site can be touched. The two are disjoint.

## English language set (2026-11-03, owner's request)
Rules from NextTang's patch for the .256, applied to this snapshot's bytes (`english_edits`; first in the run folder's lang/mk_en.py, the same 465 bytes): 14 of 15 rules, 465 bytes, banks 5, 2, 0. Every string keeps its length, so nothing had to be cut.
"DINAMIC PRESENTA......" is not in this snapshot: in the .256 it sits at 0x5D1D, over which this file's loader has already run, and it is printed before the menu, so nothing to change.
`font-lines`: the .256 stops during the intro scroll; this snapshot stops at the menu, so no scrolled line is on screen. `redraw`: 3-TECLADO and 4-INSTRUCCIONES are on the snapshot's screen and the game does not print them again until the menu comes round; both drawn from the game's font (0x9ECE) at their places, row 9 and 11, column 9. No copy of those lines exists in RAM, so nothing is restored over them.
Enhanced colours: bank 14 only, disjoint. All four combinations byte-exact through `apply` and, by MD5 of /tmp/NEXCLASH.NEX, through the loader in JNext.
Spanish against English on one input: plots identical (attract 5,010, play 8,844, cheats 8,778), RAM differs only in FLAGS once, from interrupt timing. Text bytes decide nothing.
Seen in JNext through the loader: Language stepping, first and reprinted menus, HUD, credits; play in room 1 only. Not seen: "THE SECRET IS..." (the ending), "CODE ?" (loader prompt, not reached from this snapshot).
