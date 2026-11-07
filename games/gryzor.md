# Gryzor (Ocean, 1987, 48K form) - engine `gryzor` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record gryzor, stamped); JNext only, never on a Next.
Inputs: specnext/reference/gryzor/ (gryzor.z80 md5 fdab5fb6 = TOSEC "Gryzor (1987)(Ocean)(48K-128K).z80"; c1, c2, c3, n2,
n3.rzx). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card.
Start with: the hardware checklist below. Open: under "Open".

Techniques: `detect.gameplay-screen-readers`, `patch.whole-altrom-image`, `patch.restore-speed`, `patch.preserve-r`,
`patch.pace-limiter`, `optimise.pattern-cache` (recipe and results: docs/records/gryzor.json)

## Import (2026-11-05)
Ported from Jon Attree's .nxc work, 2026-11-05 (pilot clone runs/gryzor/nexclash, base d7abd1c, head eca24cb). The owner
approved the look of that build in JNext with its white outline set (gryzor_sprites_outline.nex 7cc6d100), then asked for
two changes: the outline black instead of white, and a speed pass (it felt laggy, most of all when jumping). This port is
a new build, not a byte rebuild: the picture is the approved one but for the outline's colour; the hooks are new.
- Whole alt ROM image (patch.whole-altrom-image) in both builds. The hooks' entries and exits ("the gate", 124 bytes) and
  the start-up register block sit in Sinclair's ROM's 0xFF area at 0x386E; the hook code and state are in RAM page 24,
  mapped into slot 1 by the gate's NEXTREG $51 under itself (the page holds the same gate bytes) and mapped out at the
  exit. Outside a hook the game sees Sinclair's ROM + those bytes. The 2026-11-03 build kept page 24 in slot 1 for good
  over NextZXOS's ROM3.
- 28 MHz in every hook, the caller's speed restored at every exit (patch.restore-speed, asm/lib/hlib_speed.asm).
- R as the original's at every hook's return (patch.preserve-r, asm/lib/hlib_r.asm), the star routine included (below).
- Pace ORIGINAL by the limiter (patch.pace-limiter, asm/lib/hlib_pace.asm) with patterns prepared at build time.
- Outline black (owner, 2026-11-05), same pixels as the approved white one: docs/profiles/gryzor_outline.json.
- Correction of the 2026-11-03 notes: they put the hooks under 2 % of a tick, dividing their T by eight as if they ran
  at 28 MHz. They never switched speed: 3.5 MHz with interrupts off, about 8 % of a frame (pilot SPEED-REVIEW.md:
  5,816 of 56,007 T). Measured in JNext that build was 4.11 % slower quiet, 13.28 % running and jumping, 15.66 % firing.
Published .nxc: Gryzor v1.0 (pilot runs/gryzor/out/gryzor_v1.0.nxc), target the TOSEC .z80.

## Inputs
Snapshot: TOSEC "Gryzor (1987)(Ocean)(48K-128K).z80", md5 fdab5fb61b2cb01ce38edcfa85ea9e80, the file the 2026-11-03 engine was
proven on (no re-proof needed for another dump). 48K, stops in the game's menu (PC 57509). The 128K form,
"Gryzor (1987)(Ocean)(128K).z80" md5 0910fe35, is not used.
Multi-load: this form holds the first section only, the jungle. Its end shows START TAPE TO LOAD SECTION2 and waits in the
tape loader (65190). The .nex has no tape, so play ends there. Later levels are not converted.
Keys: 0 starts, and is fire. Menu 1 keyboard, 2 Kempston, 3 cursor keys (default), 4 Sinclair, 5 define. Cursor: 5 left,
8 right, 7 up (jump), 6 down. The menu checks the keyboard from its interrupt every few frames: hold a key, a 1-frame press
is often missed (in the original too). No option changes the drawing.
Recordings (no Fuse, no human; pilot work/rec.py, random walks; the cheat NOPs DEC A at 34919 in the RZX's own snapshot,
never in a build). 33,038 frames:
| Recording | Cheat | Reaches |
|---|---|---|
| c1, c2, c3 | lives | whole first section, the door at its end, the walk out, START TAPE |
| n2, n3 | none | first section as far as a random walk gets, four game overs each, menu, restarts |
Not reached: Kempston and other input modes in play; 5 define keys.

## Clash
Kind A. Owner's eye: clash. Attributes are bands: rows 4-7 paper green, 8-11 yellow, 13-20 cyan, all ink black. Figures
have no colour: outlines are ink, bodies are mask 0, so they show the paper of whatever row they are in: a figure is yellow,
then green, then cyan as it jumps. Plots spanning more than one attribute value: 53 % on c1, 70 % on n2.

## Rendering model
Every tick (2 to 3 frames: logic and drawing, then the frame wait 39771: beeper notes, EI, HALT, DI, a delay) 39557 blits
rows 4-19 from code, pushes zero into row 20, then 40775 plots objects set in the rock (40798, whole bytes), 40504 the
player, 36439 four enemies, 37428 bullets, 35792 the objects' eyes (AND only), later 38168 the stars. No undo: the next blit
covers everything. Lines 168-191 are ink = paper, attribute 0x6D, so a figure below line 168 is invisible: that is how
figures wade and drown. Interrupts are off from the frame wait's DI to its EI: at every hook site (verify counts IFF).
Images: 2 bytes per pixel byte (graphics, mask; bullets mask, graphics), in rows of two lines that run across and back.
Enemies have four copies, each shifted 2 pixels. The level-end walk-out (35461) runs ticks without the star call.
Random numbers: LD A,R at 35115 and 39152. The star routine's path is 2 M1 longer for a byte holding 0, so a figure drawn
in a star's byte changes R in the original.

## Design
| Site | Original | Now |
|---|---|---|
| 40 stores in five loops (STORES) | LD (HL),A | NOP (the loops no longer run; the NOPs keep the verifier's bare replay equal to the build) |
| 40370, 40188, 40709, 40539, 37662 | LD (46081),SP | JP gate: the whole loop (below) |
| 34750, 35469 | CALL 39557 | CALL e_tick: hide what the last tick did not draw, clear the plot records |
| 34509 | LD HL,16384 | JP e_cls: all sprites off at the menu's clear |
| 32870 | CALL 42007 | CALL e_clr: all sprites off at the level's end |
| 34850 | CALL 38168 | CALL e_star: the stars |
Plot hooks replace their whole loop. A loop's registers at its end depend on the image and the geometry, never on the
screen: B = 0, DE the last pair popped (clip loop: E = E' after a row that crosses a character row), HL stepped, A and F
from the last row's address step, C as at the site (clip loop: A'). lsim works them out row by row, with the loop's
T-states and M1s (table KT: prefix, row, crossing, no-carry branch; clip + 17 T and 4 M1 a drawn byte a row; the last DJNZ
5 T shorter), runs the last row's step again with the loop's own instructions for A and F, and jumps to the loop's
LD SP,(46081). The hook writes 46081 as the original did. Each plot hook is a pace window whose target is the loop's
T-states + 1 T (SC_T) a contended access (a screen read and write a byte drawn; popped bytes below 0x8000) less its own
time at the incoming clock (FIXP 267 T).
The star hook works out each star byte as the original saw it: the build's byte with this tick's plot records (y, column,
lines, width, column mask, kind, image; 8 bytes, every plot, drawn or not) drawn over it in order, then sets R from the
original's path (203 + 2 per byte at 0, mod 128), A and F from the last byte (the original's own instructions), B, DE, HL
as the original leaves them, and flips the build's star bytes as the original routine would on the build's screen (the
approved look). Its window's target is the star routine's time: 1,787 T + 9 T per 0 + 3 T per 255 + SC_T an access.
Tick, cls and clear hooks pay their time into the debt.
Patterns: the 92 listed images (profile figures) prepared at build time from the colour plane (store_pages, pages 36-40, 34,560 bytes),
copied with OTIR runs of 128 bytes; any other image from the plane as before (slow path). The prepared bytes equal the slow
path's for every listed image (unit: store cases). 32 groups of 4 patterns, key = image + shape found by CPIR, replaced in
rotation, never a group shown this tick or the last. Sprites stay in plot order, later in front, as the game. Clip window
lines 0-167 keeps wading and drowning as the original shows them.
Colour: entry 1 black, the game's ink; entry 2 bright yellow, the paper of the figures' own band. Entries 3-15 fixed.

## Outline (owner's decision, 2026-11-05)
Without an outline the bodies vanish on the yellow forest (they are the same yellow). Jon asked for an outline on
2026-11-03 and approved the white one in JNext; on 2026-11-05 he asked for it black. BRIEF-3's rule is no white outlines;
this black outline is his explicit request for this game. Same width and placement as the approved build: a see-through
pixel 4-next to an opaque one, inside the image's own bytes, bullets included (docs/profiles/gryzor_outline.json, 2,776
entries, the approved paint/outline_colours.json with its nibble 15 as 1). The outline nibble is palette entry 1, black.
Colour route only (recolour): plane and store banks change, 9,034 nibbles 0 -> 1; the hook page, game bytes and palette do
not; back to the default byte-exact. Proof that it adds pixels only where the approved one did: the white twin of the map
(nibble 15) verifies IDENTICAL on every recording with that nibble counted as see-through, and the black build differs
from the white twin in that nibble only.

## Verify (what it checks)
Three replays of each recording. The first notes what the star routine finds. The second has the stores NOPed: its screen
is the bare one, and the play area may change after the objects are drawn only at the stars and the eyes. The third runs
the original: registers and memory against the second at every tick, R included; each hook in a simulator from the real
state (alt ROM image, page in slot 1 only inside, plane and store windows, NR 7 and a time model for the video line),
entered at the game's clock (verify clock=). Plot hooks: every register but SP (dead: LD SP,(46081) follows) against the
original loop run to its end, R included, and the hook's loop T-states against the simulator's. Star hook: R, A, F, B, C,
D, E, H, L against the original routine run from the same state, and the screen bytes it writes. Every hook: the exit
speed is the incoming one, slots back, no ROM or plane write. At every tick the sprites over the bare screen against the
original's screen, every byte of lines 0-167. Pace model: per tick, the hooks' real time against the displaced original's.

## Results (stamped run 2026-11-05, `selftest.py --game gryzor --verify --stamp`; simulation only)
Builds: gryzor.nex 180adc9071309e8c9a5a10789040d3a1, gryzor_sprites.nex 81f84fdbceb9f6b493140e196de4af99,
gryzor_sprites_outline.nex 827a770f7964fc8c21d038dfa99b7a00 (the black outline, the published build); boot OK.
| Recording | Frames | Ticks | c4 / c3 / clip / b4 / c5 | Star calls | Clears | Verify | Outline twin |
|---|---|---|---|---|---|---|---|
| c1 | 5001 | 1972 | 2913 / 2588 / 550 / 745 / 36 | 1844 | 0, 1 | IDENTICAL | IDENTICAL |
| c2 | 5013 | 2002 | 2843 / 2580 / 486 / 796 / 92 | 1874 | 0, 1 | IDENTICAL | IDENTICAL |
| c3 | 5016 | 1606 | 2634 / 2269 / 485 / 824 / 21 | 1478 | 0, 1 | IDENTICAL | IDENTICAL |
| n2 | 9002 | 3937 | 6925 / 3522 / 1531 / 1862 / 179 | 3936 | 8, 0 | IDENTICAL | IDENTICAL |
| n3 | 9006 | 3949 | 7232 / 3635 / 1551 / 1851 / 101 | 3948 | 8, 0 | IDENTICAL | IDENTICAL |
Every hook ran (tick hook 13,466 times, screen clear 16, bitmap clear 3), R compared at every tick and after every hook.
Stars where a figure changed the original's path: 632, each with R, A and F as the original's. Uploads 2,892 of 48,251
plots. Pace model per tick, the build over the original: +110 to +217 T on average (a tick is 2 to 3 frames).
Unit PASS: 659 plot cases, 92 prepared images against the slow path, 64 random-R cases, every-site clock matrix 152
cases over 8 sites. ROM paths: all three builds, all 5 recordings, every ROM byte the game runs as recorded (13 bytes),
the tail never read before written.
Negatives, each a full replay of c1 (5,000 frames), 23 of 23 DETECTED: a store left in, column / line off by
one, bodies see-through, ink and body swapped, DE wrong, plane left mapped (slow path forced), store page left mapped,
no hide at the tick, left clip ignored, game memory written, figures left at the level end / the menu, bullet not
converted, cache ignores the shape, a store writing game memory, forced 3.5 MHz exit (replayed at 7 MHz), missing cache
invalidation, R delta one off, star hook ignoring the figures, limiter never waits, slot 1 left on the hook page, no star
hook.
JNext 1.1.104 (pilot runs/gryzor/jn2), against the plain build, input keyed to updates, probe 0xA439, 10 trials a scene,
300 updates each, every run in lockstep with no fixture: quiet +0.00 %, busy (running and jumping) +0.39 % (worst
+0.60 %), sound (firing) +0.38 % (worst +1.03 %); none faster; beeper writes per update equal in all 30 (2.809, 2.890,
1.595). The 2026-11-03 build, the same way with LD A,R as LD A,I in both (it changes R): +4.11 %, +13.28 %, +15.66 %.
Soak 15 minutes: no freeze, loop or crash. Flicker: 2, 18 and 1 frames of 220 out of step (figures a frame behind the
scrolled scenery; the 2026-11-03 build 42 in the same window), no figure vanished, no attribute flashes: NOT clean.
The .nex with the .nxc menu reaches play from Enter and 0.
Cheats (work2/cheats.py in the pilot folder, 6 seeds x 6,000 frames of random play, simulator): Infinite lives (34919,
0): 0 lives lost against 113; Immune to enemies touch (35604, RET): 0 touch deaths against 76; Immune to enemy fire
(35651, RET): the fire death 35655 never ran, against 38. Dropped: 35549 RET (skips 4 of the 10 object slots, fire
deaths 38 to 21, not immunity) and the .pok's [L1] lines (another release's addresses: data or mid-instruction here).

## Defaults taken (a human would have decided)
Every masked figure a sprite, bullets too. Objects in the rock and their eyes stay as scenery. Body colour bright yellow for
every figure. Wading and drowning hidden, as the original. 48K form, so one section.

## Stays on the ULA
Scenery, objects set in the rock and their eyes, stars, HUD, menu, text.

## Hardware checklist (nothing here has run on hardware)
1. Start: the menu; hold 0. Walk and jump: figures stay yellow with a black outline across the bands; scenery keeps its
   colours. Stars do not flicker around figures.
2. Speed and sound against the plain .nex: walk, jump, fire; the game no slower, the shot notes as long.
3. Walk into the water: legs hidden below the surface. Bullets on show.
4. Lose all lives: last frame held, a key gives the menu with no figures left. Finish the section: door, walk out, START
   TAPE with no figures left.
5. The speed key F8 mid-game: the game takes the new speed and keeps it (the hooks never undo it).
Hardware risk review: the gate maps RAM page 24 into slot 1 under the code that runs it (NEXTREG $51 from 0x386E); never
tried on a board. The limiter needs NR 0x1E/0x1F (core 3.0+). Contention: the pace target assumes 1 T a contended access,
calibrated in JNext only.

## Open
- Never run on hardware. JNext only.
- The owner's look: in the yellow forest the black outline meets the forest's black pattern and figures read less well
  than with the white one (out/gryzor_outline_before_after.png in the pilot folder); on cyan and green it reads well;
  on the black sky it is invisible and the yellow body reads as before. His call.
- Flicker: while the scenery scrolls a figure can show a frame behind it (2-18 frames in 220). The game blits the
  scenery, then plots the figures: when a frame ends between, the original shows the scenery with the figures erased,
  the build the figures where they were. Fixing it needs the sprites to change with the blit (the attributes known
  before the plots) or a double-buffered ULA.
- The star hook ignores the eyes drawn over a star byte between the figures and the stars (none in the recordings: verify
  counts "under a figure and an eye").
- Random-key recordings only; no human recording.
- 128K form not studied: it would have all the levels.

## Lessons
- [local: this game's loops] demonstrated: NOPing a plotter's stores saves only 3 T a byte, less than a hook's fixed entry and exit at 3.5 MHz (about 250 T), so a 28 MHz plot hook in front of the loop made the game slower (pace model +3,800 T a tick); replacing the whole loop, with its exit registers from the geometry, gave the window the loop's whole time (+36 T a tick).
- [local: this game's RNG] demonstrated: the star routine's path depends on the figures in its bytes; a star hook that works out the original's bytes from the tick's plot list keeps R exact, and the pace runs stay in lockstep with the original with no fixture.
- [local: this game's menu] observed: the menu reads the keyboard from its interrupt every few frames; a 1-frame JNext keypress is often missed, in the plain build and the original alike; hold the key.
- [local: the archive's trainers] observed: the .pok's [L1] lines name addresses of another release (data or mid-instruction in this file); only Infinite Lives (34919) and the unlabelled-version lines 35604 and 35651 work here, proven on the simulator.

- [local: the outline map can keep only its bits] gryzor_outline.json's check values are null (each was the game's byte); _entry trusts a null check, and the image comes from the player's snapshot. Builds unchanged.

## Friction
- reuse: [local: work2/trials.py, pace_summary.py, fixture.py, cheats.py in the pilot run folder, after Cobra's]
- retries: [local: the first speed design (a 28 MHz hook in front of the NOPed loop) was slower than the original; measured on the verifier's time model before any JNext run]
- environment: [local: NEXCLASH_REFERENCE is an overlay of symlinks in the pilot run folder (specnext/reference + ref/gryzor), as the brief forbids writing specnext]
- hand-rolled: [local: the loop T-state and M1 table (KT) by reading the loops; the verifier checks it against the simulator at every plot]
- scratch: [none: scratch scripts stay in the pilot run folder, none added to the repo]

## Technique use
- patch.whole-altrom-image: helped: the gate in the ROM's 0xFF area kept Sinclair's ROM everywhere else.
- patch.restore-speed: helped: the every-site matrix and the forced-exit control.
- patch.preserve-r: helped: r_check named each hook's delta; extended to a game routine (the stars) whose path a figure changes.
- patch.pace-limiter: helped: the window per loop; the debt carried the tick hook's time.
- optimise.pattern-cache: helped: prepared patterns, one OTIR run per 128 bytes.
- detect.gameplay-screen-readers: helped: the star routine was the only reader that changes logic (through R).

## Stage log
- 2026-11-03: stages 0-3, one unattended session, no user rounds; white outline set after the owner's play.
- 2026-11-05: import (pilot runs/gryzor/nexclash2 on refactor-final ecabb13): whole alt ROM image, 28 MHz hooks, R kept
  (star hook), whole-loop plot hooks with the limiter, prepared patterns, black outline, .nxc v1.0.

## Enhanced-colour check (2026-11-05): HARD, not built
No .256 for Gryzor in Spec256-256-all38. Figures are line art with one body colour (the paper they stand on); the scenery
is blitted from code, not a tile map. Players and enemies differ in shape. A repaint would need figures and scenery together.
