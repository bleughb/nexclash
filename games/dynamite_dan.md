# Dynamite Dan (Mirrorsoft, 1985; 48K) - engine `dynamite_dan` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record dynamite_dan); JNext only, never on a Next.
Inputs: specnext/reference/dynamite_dan/ (dynamite_dan.z80 md5 3470d12b = TOSEC "Dynamite Dan (1985)(Mirrorsoft).z80";
t1, n1; the pilot's census r00-r47, a1, c1 beside them). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card.
Start with: the hardware checklist below. Open: "Open" below.

Techniques: `patch.xor-overlay-keep-ula`, `patch.whole-altrom-image`, `patch.restore-speed`, `patch.preserve-r`, `verify.update-locked-pace`
(recipe and results: docs/records/dynamite_dan.json)

## Import (2026-11-05)
Ported from Jon Attree's .nxc work, 2026-11-05 (pilot clone runs/dynamite_dan/nexclash, base d7abd1c, head fcfeb73). The
owner approved that build's look in JNext on 2026-11-03: "no clash, solid", then the airship foreground ("works perfect!",
dynamite_dan_sprites.nex 8e43e4c7). Its .nxc was never published. A new build: bank 11 (Dan's patterns, the airship's
hull and cable tiles and their table) is byte-equal to the approved build's; the hooks and the start change.
- Whole alt ROM image (patch.whole-altrom-image) in both builds: the build now starts from the TOSEC snapshot's own BASIC
  (PAUSE 0, then RANDOMIZE USR 51200), not from a derived start; derive_start only gives fg_capture its state.
- R as the original's at every hook (patch.preserve-r; the game reads R at 0xDE1F).
- e_dan at 28 MHz, the caller's speed latched on its stack and written back at its exit (patch.restore-speed); the
  clears at the game's clock. Pace is the hook's time only (no padding to repay it from): measured below.
Published .nxc: Dynamite Dan v1.0 (pilot runs/dynamite_dan/out/dynamite_dan_v1.0.nxc), target the TOSEC .z80.

## Inputs
By Letter/d/dwa-dzw/Dynamite Dan (1985)(Mirrorsoft).z80 md5 3470d12b21edb24d6b665dfac5e8d84d, ZXDB 0001551 (eye-check list; zxinfo.dk 502 on 2026-11-03).
`inspect`: 48K, BASIC stopped at line 3 PAUSE 0, PC in ROM, line 4 RANDOMIZE USR 51200. derive_start() runs it with a key held to 0xC800:
dynamite_dan_start.z80 md5 c007eaca: the 2026-11-03 build input and most recordings' start; since 2026-11-05 the build
starts from the snapshot itself, and t1 (pilot work2/rec_tosec.py) is recorded from it. Interrupts: DI at 0xC800; 0 accepted in 10,175 frames (`isr`). The game reads the ROM only at 0x3D00-0x3D07 (`scan`).
No menu mode changes drawing: D define keys, K keyboard, J Kempston, S Sinclair, I instructions, P pause, ENTER play. Keys as stored: A left, S right, SPACE jump.

## Rendering (observed unless marked)
Main loop 0xC80A, no frame sync, about 2.6 frames a tick. Room table 0x69E6, room in 0xCFCA; moving between rooms ±1 / ±8.
| Figure | Routine | How | Clash |
|---|---|---|---|
| Dan | 0xD1CE (JP from every state handler, CALL at 0xD184) | 3 x 28 bytes frame|saved OR, x cell 0xC873, y pixel 0xC872, frame 0xC875, table 0x632A; attributes never written | takes each cell's colour: 12-21% of plots span several attributes, 0.6-2.5% of ink off colour (ropes, hull, floors) |
| 4 enemy tables | 0xE96B, cell aligned, pre-shifted; paints its own box, erases scenery | 0 of 187,938 and 229,596 cells over scenery attributes in play; 169 of 736,272 in the room census (Dan spawned by poke) | avoided by level design: stay on ULA |
| Lifts | 0xCD24 / 0xCD2B, 3 x 2 bytes, no attributes | stay on ULA, not measured | |
| Airship, conveyors, force fields, items | 0xD9EC, 0xCC5F, 0xE6DC, 0xE84E | scenery: ULA | |
Force field: the big red block in room 43 is the game's own (0xE6DC), seen in the plain simulation too.
Logic reads attributes under Dan (0xD205, 0xD8B4, 0xD96F) and screen bytes (0xD225 collision, 0xD65D new rows into 0x62D6), so nothing on the ULA moves: overlay.
Sinking: in water 0xDBED counts plotted row pairs down 12..1 (0xDBEE): Dan's bottom goes first.

## Patch plan
Cards opened: patch.xor-overlay-keep-ula (idea only: this plot is OR, not XOR, and Dan paints no attributes, so the ULA stays untouched). No card for clipping by the sprite window: design note here.
Sites: 0xD1CE (JP e_dan), 0xE801 and 0xE820 (clears hide), 0xE60B (end of game hides). Hooks in alt ROM 1 at 0x386E, no RAM, stateless; sprites 0, 1 (16 + 8 rows); 16 8-bit patterns from bank 11; xoff table gives each frame's window; clip window Y2 = y + 2 x rows - 1, written every plot.
0xC880 odd: the plotter draws the saved background: sprites hidden.

## Defaults taken (a human would have decided)
1. Only Dan is a sprite. Default 1 says every figure; enemies measured no clash, so a human may want them for painting (the route would need run-time patterns).
2. Depth: Dan in front of everything except the airship (owner's request, below).
3. Colours: bright cyan, the ink of an empty cell (0x45).
4. No outline.
5. Clash numbers below Arkanoid's and the owner said clash: built.

## Airship foreground (owner's request 2026-11-03)
The airship is fixed scenery of room 43, drawn once with the room (only the end of the game changes it, 0xE60B). The original's depth: hull cells non-bright cyan, so Dan's ink merges; cells 16-18 of row 5 are ink = paper (0x2D) and no floor, so he drops into a well at y = 22, x 15-17 ("the basket"); elsewhere he stands on top at y = 14. Cables (attribute 3) only make him magenta.
Chosen: 9 static sprites 2-10, above Dan by sprite number: the hull rows 5-6 cols 12-20 (each row's first to last non-black pixel) and the cables' ink, copied from the ULA at build time (fg_capture runs the game to the first plot in room 43; no game data in the repo). Shown at every plot in room 43, hidden by the clears. Rejected: Layer 2 with the priority bit: more memory and setup for one object. Propeller not included.
Verify: in room 43 every plot checks all 9 shown and each pixel equals the live ULA away from Dan; elsewhere untouched; clears hide them.
Other objects that would benefit: none measured; any scenery Dan crosses could use the same method, one table per object.

## Colours
docs/profiles/dynamite_dan_colours.json absent = defaults. Sheets: `dynamite_dan.sheets()`; key = graphics byte (%04X), bit = pixel, whole 16-wide window paintable (outlines). Palette indices 1-15 = Spectrum colours; 8-bit patterns. recolour only rewrites bank 11; tested with a throw-away painting (paint/).

## Results (2026-11-05; simulation only)
Builds: dynamite_dan.nex 3ad20495, dynamite_dan_sprites.nex 22961983; boot OK.
52 recordings (t1 from the TOSEC BASIC, n1, a1, c1, census r00-r47), 122,380 frames, IDENTICAL (pilot work2/verify_all.py):
Dan plots 22,117, clears 0xE801 110, 0xE820 159, 2,314,996 sprite pixels; 0xE60B (the ending) in unit cases only. R
compared at every hook. Every-site clock matrix 832 cases. ROM paths: both builds, t1 775 ROM bytes (BASIC included) and
n1, every byte as recorded; the tail never read before written.
Unit (auto): Dan 4,032, clears 6, end 6, negative controls 54 of 54 detected over t1 and n1's states, the new ones R one off
after a plot and a forced 3.5 MHz exit (NEXTREG 7 in the hook) among them.
JNext 1.1.104 (pilot runs/dynamite_dan/jn2): pace, pilot work2/trials.py, probe 0xC80A, lockstep on lives and room, 10
trials a scene of up to 300 ticks: this build quiet +0.09 %, busy +0.13 %, sound +0.14 % (single trials -0.6 to +0.5 %);
the approved build 8e43e4c7 +0.63 %, +0.69 %, +0.51 %. Flicker 300 frames: 1 frame out of step (Dan's sprite a frame
ahead of his own ULA pixels, the same cyan; the approved build 0 in the same window, 5 at the frame edge) and 1 one-frame
attribute change, also in the approved build: warnings. Soak 15 minutes against the .z80: no freeze, loop or crash. The
.nxc's menu build reaches play, cheats on and off.

## Open
Ending (needs all 8 dynamite, airship) not reached: hide covered by unit case only. Lifts stay ULA, not measured.
Never run on hardware or in CSpect.
The sprites move at the plot hook's entry, before the plotter's own ULA pixels: a frame edge between them shows the
sprite a frame ahead (1 frame in 300 in JNext). A hook at the plotter's end would close it.

## Hardware checklist
Dan solid cyan in room 43, cables in front of him, legs hidden in the basket; hull unchanged when he is elsewhere; sinking in water clips cleanly; sprite off during room change, menu, game over; end of game.

## Lessons
- [local: pilot, docs not edited] A per-room census found Dan's sinking (0xDBED); the no-cheat recording never drowned. Poke the start room to reach every room cheaply.
- [local: pilot, docs not edited] the room census counts Dan spawned inside scenery: use play recordings for the clash numbers, census for coverage.
- [local: this game] bot rollouts get stuck in room 6 (the lives cheat keeps them alive): 49,000 frames of nothing.
- [local: this engine] a negative control mutating one table entry passes on states that use another frame: mutate all.
- [local: this game's start] demonstrated: with the whole alt ROM image the TOSEC snapshot's BASIC runs to USR 51200 as on a 48K (t1: 775 ROM bytes as recorded), so no derived start is needed.

## Friction
- reuse: [local: the TOSEC-start recorder (pilot work2/rec_tosec.py) is this game's]
- retries: [none: the port took one round of R deltas]
- environment: [local: NEXCLASH_NEXT_ROM (enNextZX.rom) and NEXCLASH_JNEXT_CARD point into other pilot runs, read only]
- hand-rolled: [local: cheats proved by a random-walk run with and without each poke (pilot work2/cheats.py)]
- scratch: [none: scratch scripts stay in the pilot run folder, none added to the repo]

## Technique use
- patch.xor-overlay-keep-ula: helped (the idea; its requires render.composition.xor may be too narrow: this plot is OR and paints no attributes)
- patch.whole-altrom-image: helped: the build starts from the snapshot's own BASIC.
- patch.preserve-r: helped: R compared at every hook; the one-off negative caught.

## Stage log
2026-11-03 stages 0-3, about 30 minutes wall time by clock, unattended, no user rounds.
- 2026-11-05 import (pilot runs/dynamite_dan/nexclash2 on refactor-final f6b8ac0): whole alt ROM image, BASIC start, R,
  every-site matrix, a recording from the TOSEC start, cheats, pace / flicker / soak in JNext, .nxc v1.0.
