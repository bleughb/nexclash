# Pssst (Ultimate Play The Game, 1983; 16K)

## Next session
Stage: 3 (verified, stamped)   State: 2026-11-20: every moving figure of the main object table a sprite on its own
pixels in its own colour, over the game's unchanged drawing; verified on two machine-played recordings and unit
cases over every graphic; runs in OverSpec; not on hardware
Inputs (private, pilot runs/pssst/reference_files/pssst): pssst.z80 (TOSEC "[a][16K]", at the game's menu),
pssst_m2.rzx + pssst_m3.rzx (machine-played, see "Recordings"), pssst_loading.scr (the tape's screen),
enNextZX.rom (the Next's ROM, for the verifier's ROM model)
Branch: add-pssst    Commit: this one    Checks: selftest --game pssst --verify --stamp, doccheck
Pending user answers: "Open" 1-2
Start with: a recording played by hand into later levels, then hardware
Read: "Build", "Open"

## Result (2026-11-20)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

Two whole machine-played recordings (20,098 and 20,083 frames, 7 games each, first level).

| | |
|---|---|
| Builds | pssst_sprites.nex 40ae6ece (figures as sprites in their own colours, loading screen), enhanced 6d14ba48 (44 pictures painted, 13 fixed colours), plain db271c07 |
| Verify | IDENTICAL on both, both builds (Enhanced: every pixel's colour against the painted map too): 111,080 figures as sprites (13,019,621 sprite pixels against the original's plot on an empty screen, none across the right edge), 30,218 figures left to the game (flower, leaves, lives), 1,007 erases, 106 clears, 140,349 draws from their entry, every pace site; every register with R and all memory, the bitmap too; 111,080 paints not painted and 30,218 left to the game; the alt ROM's IM 1 handler against Sinclair's at 36,814 interrupts |
| Colour | 447 paints (explosions) of another colour than the sprites took at the plot: one update early |
| Unit | PASS: 2,352 graphic cases (all 49 graphics x 8 places x 3 colours x first and last object), 24 speed cases, erases, clear, 36 paint cases, 5 guard cases, a graphic not in the table, negative control 40 of 40 |
| Negative | 6 broken builds, all detected (the system ROM left under the hooks, the window never opened, never closed, R one off after a draw and after an entry, the colour painted after all) |
| Boot | simulated: registers and RAM as the snapshot |
| ROM paths | pass: 572 ROM bytes used, every byte the game runs as recorded |
| OverSpec | the patch from its menu: loading screen, the game's menu, play |

## Recordings
- The rzxarchive lists a recording of this game and denies its distribution. The two here are machine-played from
  the snapshot: the toolkit's recorder (48K, Kempston) driven by a small explorer that, from the current state,
  tries ten bursts of input, keeps the one that runs the most new code and raises the score, plays on, and starts a
  new game from the menu when one ends: one unbroken recording each, no state reloaded (the explorer is in the
  pilot run folder). 20,098 and 20,083 frames, 7 games each, first level only: 37 and 39 of the 49 graphics.
- The graphics the recordings do not reach (the later levels' pests, two bonus items) are covered by the unit
  cases: every graphic at eight places in three colours through the game's own plotter.

## Feasibility (PLAYBOOK 3d, 2026-11-20)
- 16K game in a 48K snapshot. IM 1: the ROM's handler runs (FRAMES, the keyboard); interrupts are on in most of the
  code. The main loop is not frame-synced: every time FRAMES changes it runs the player's objects once with
  interrupts off (0x70ED), the rest of the objects as fast as the processor goes. Hook time is game speed.
- The plotter is Jetpac's, instruction for instruction, at other addresses (games/jetpac.md "Rendering model"):
  move-and-redraw at 0x75D0, set-ups 0x74A5 / 0x74BD and their inner entries, entries 0x74DF, 0x74EB, 0x751C,
  0x7521, 0x7526, 0x7536. One difference: this plotter does not wrap within the 32-byte row; past column 31 it
  runs on at column 0 of the next character row.
- A graphic is [x offset, W bytes, H lines, W*H bytes], rows bottom line first. 49 of them, all fixed data
  (0x769A-0x7FD1), named by the tables 0x761A (types 1-3: 8 words a type) and 0x764A (types 4 on: 4 words) and by
  pointers in the handlers. The build checks that no other word of the code points at a graphic's header.
- Objects: the main table 0x5E6C + 8i, i = 0-15 (+0 type and direction, +1 x, +2 y, +3 colour): Robbie, his can,
  the spray, bonus items, the pests, explosions. Three kinds of figure are drawn once and left on the screen: the
  lives' icons (IX 0x5E0F), the leaves (IX 0x5E3C) and the bud and flower (IX 0x5E8C, in the main table; its last
  picture, 0x7CCF, is taller than two sprites).
- Colour: after a plot the handler paints (IX+3) over the figure's cells (0x7450, 9 CALLs or JPs). That is the
  clash: a pest's colour over the leaves, the can's over Robbie.
- Some handlers CALL the plot's parts themselves (the set-up 0x74C0 from 0x66CF, 0x6A10, 0x6C92 and 0x600F, then
  the plot at 0x74F2 or 0x7539), and one erases at a place it gives (0x667C: CALL 0x74AB, JP 0x7529).
- No game logic reads the screen (readers: the plotter itself and the score flash); collisions use coordinates.
- Other screen writers: text (0x73CD), the stalk (0x6D77 / 0x6D7E), the clears. Left as they are.

## Build (stage 2, 2026-11-20; asm/pssst_hooks.asm, nexclash/pssst.py; after jetpac_v11)
The game's bitmap stays the original's; sprites lie on the figures' own pixels.
- The engine is jetpac_v11's shape (the same hooks at this game's addresses: the draw hook at the new-frame set-up,
  the erase-only entries, the bitmap clear, the plot's set-up at 28 MHz to pay for the hook, R kept, the whole alt
  ROM image, the loading screen), with these differences:
- The game goes on drawing every figure into the bitmap: no store of the plotter is removed. The sprites show the
  same pixels in the object's own colour (palette offset = ink + 8 * bright of (IX+3) at the plot).
- The colour paint: its six CALLs or JPs from the handlers of the objects that have sprites go to a copy of the
  routine in hook RAM whose store is a read (LD A,(HL) for LD (HL),D): the same instructions, flags, R and time,
  no colour. The three others (lives, leaves, flower) are not changed: those figures keep the game's own colour.
- Sprites only for the main table's objects but the flower: any other IX changes no sprite.
- The erase at a place the handler gives (0x667F) hides the object's sprites as the two erase-only entries do.
- The copy of a column that crosses the right edge sits 8 lines down, as this plotter runs on. From the last
  character row of a third the game's own figure would run on 56 lines up instead; no figure crosses the right
  edge in the recordings (counted), and the unit places avoid that row.
- A graphic the table does not hold: the object's sprites go off and its colour is not painted (the figure shows
  in the cell's colour). None exists in this snapshot (the build's pointer check).
- An explosion changes (IX+3) between its plot and its paint: its sprites take each colour one update before the
  original paints it (counted in the replay: "of another colour than at the plot").
- Hook code and tables in the alt ROM image at 0x386E (0xFF in Sinclair's ROM); entries, the paint's copy, R and
  the speed latch in hook RAM at 0xB000 (a 16K game never addresses it; the verifier fails on any game read or
  write above 0x7FFF). Interrupts stay on in the hooks.
- DMA / DDMA (docs/DDMA.md): not used. The patterns are sent once at set-up (81 patterns); a hook writes only
  sprite attributes.

## Enhanced (2026-11-20, first pass; owner: "have codex do the enhanced colours")
- Sheet: one picture a distinct shape (44), painted by a Codex pass from a brief; files in the owner's painting
  folder (`nexclash-pssst`); `sheet2colours.py` (pilot tools) makes `pssst_colours.json`, kept beside the snapshot: it holds
  the figures, so it is not in this repository.
- These sprites have one palette for every figure: 13 fixed colours (nibbles 2-14 of every palette offset, 9 bits
  each, written by the set-up) and nibble 1 = the object's own colour at run time. A pixel left unpainted keeps
  the game's colour, so a figure the game shows in several colours still does. 44 pictures have painted pixels.
- The hooks and tables are the same as the default's: only the patterns' nibbles and the 13 colours differ. The
  default build's set-up writes zeros there and no pattern of it uses them.
- Verify: the replay and the unit cases run for both builds; a sprite pixel must be the object's ink where the map
  leaves it and the map's fixed colour elsewhere.

## Hardware checklist
Starts from the menu after the loading screen (a key or 5 s); menu and keys as the original; Robbie, the cans, the
spray and the pests in their own colours with no colour spilling onto the leaves, the stalk or each other; the
leaves, the flower and the lives as the original; nothing left behind after a lost life or a new screen; sound
unchanged; the game's speed as the original's over a minute of play.

## Open
1. The recordings are machine-played and stay on the first level: later pests and the bonus items are proven by
   the unit cases, not in play.
2. The Enhanced painting is a first pass the owner has not seen in play; where the painted map lives for a public
   patch (it holds the figures; the .nxc carries the painted patterns).
3. Pace is by construction (the plot's set-up at 28 MHz pays for the hook, as Jetpac 1.3); not measured in JNext.
4. The flower, the leaves and the lives stay on the ULA: a pest crossing a leaf is in front of it and no longer
   colours it, but the flower's own cells keep one colour as in the original.

## Decisions
- 2026-11-20 (owner): "Let's finish off the ultimate games". Default as Jetpac's published patch: the game's own
  colours, figures as sprites.
- 2026-11-20: the bitmap is kept (the figures stay drawn under their sprites); only the colour paint goes.
- 2026-11-20: the flower stays the game's (one picture too tall for two sprites, and it only moves as it grows).

## Lessons
- [kb lesson.enhanced-palette-rgb-check: this engine's build step] An Enhanced build's fixed colours were compared as symbols only, never with
  the RGB the set-up uploads (Codex review 2026-11-20): palette_wrong replays the boot's NEXTREG writes against the
  painted map, the default build as its negative. Clipped figures now check their fixed colours too.
- [kb lesson.sites-found-by-bytes: this game's analysis] The same plotter as a published game's is found by its bytes with the addresses
  left out; the hooks then move over address by address. What does not move is the game round it: which objects
  are drawn once and left (here three), and which handlers call the plot's parts themselves.
- [kb lesson.nop-stores-keep-timing: this game's design] With the bitmap kept, only the colour paint needs to go, and a copy of it with the
  store read instead of written takes the same time to the T state: no pace cost and no exception in the memory
  comparison but the colour cells.
- [kb lesson.plotter-edge-behaviour-differs: this game's verifier] A check written for another game's plotter (a figure wraps within its row) failed a
  third of the edge cases here: this plotter runs on into the next row. The unit places are the game's own.
- [local: this game's verifier] The replay stopped at 6,000 frames of a 20,000 frame recording: a default meant
  for a free run. A recording is replayed to its end.

## Friction
- reuse: [local: this game's module] jetpac_v11's module and hooks, turned into this game's by two scripts; the
  recolour and rocket parts left out.
- retries: [local: this game's hooks] the flower left to the game after its tall picture was found; the erase at a
  given place and the direct calls of the set-up after the first replay.
- hand-rolled: [local: private run folder] explore.py (the unbroken explorer that starts new games), plots.py
  (objects and graphics at the draw site), play.py.
- environment: [local: this machine] four of the TOSEC snapshots are stopped on the loading screen; the [a] ones are
  at the menu.
- scratch: [local: private run folder] the run folder's tools.

## Technique use
- patch.xor-overlay-keep-ula: helped: the bitmap compares equal, so the plot needs no exception in the verifier.
- patch.preserve-r: helped: taken whole from jetpac_v11.
- patch.restore-speed: helped: the same.
- patch.whole-altrom-image: helped: the game runs the ROM's interrupt handler; the image is Sinclair's ROM.

## Stage log
- 2026-11-20: stages 0-3 in one session (no recording to be had: machine-played; the plotter matched to Jetpac's;
  jetpac_v11 adapted; unit cases over every graphic), about 4 h (one full check of 50 minutes), about 60 tool
  calls, 2 user rounds (the request, a go-ahead).
