# Cookie (Ultimate Play The Game, 1983; 16K)

## Next session
Stage: 3 (verified, stamped)   State: 2026-11-20: every moving figure a sprite on its own pixels in its own colour,
over the game's unchanged drawing; verified on two machine-played recordings and unit cases over every graphic;
runs in OverSpec; not on hardware
Inputs (private, pilot runs/cookie/reference_files/cookie): cookie.z80 (TOSEC "[a][16K]", at the game's menu),
cookie_m2.rzx + cookie_m3.rzx (machine-played, see "Recordings"), cookie_loading.scr (the tape's screen),
enNextZX.rom (the Next's ROM, for the verifier's ROM model)
Branch: add-cookie    Commit: this one    Checks: selftest --game cookie --verify --stamp, doccheck
Pending user answers: "Open" 1-2
Start with: a recording played by hand into later levels, then hardware
Read: "Build", "Open"

## Result (2026-11-20)
Techniques: `patch.xor-overlay-keep-ula`, `patch.runtime-colour-map`, `patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

Two whole machine-played recordings (20,273 and 20,153 frames, 6 games each).

| | |
|---|---|
| Builds | cookie_sprites.nex faaacc0b (figures as sprites in their own colours, loading screen), enhanced 7df95fe3 (34 pictures painted, 12 fixed colours), plain df406298 |
| Verify | IDENTICAL on both, both builds (Enhanced: every pixel's colour against the painted map too): 106,799 figures as sprites (12,817,707 sprite pixels against the model of the figure, and the model against the original's own plot at every draw-only entry), none left to the game, 24 erases, 56 clears, 106,799 draws from their entry, every pace site; every register with R and all memory, the bitmap too; 104,519 paints not painted, none of another colour than at the plot; the alt ROM's IM 1 handler against Sinclair's at 32,491 interrupts |
| Unit | PASS: 1,632 graphic cases (all 34 graphics x 8 places x 3 colours x first and last object, through the draw-only entry: sprites, model and the original's plot agree), 16 speed cases, erases, clear, 84 paint cases, 3 guard cases, a graphic not in the table, negative control 40 of 40 |
| Negative | 6 broken builds, all detected |
| Boot | simulated: registers and RAM as the snapshot |
| ROM paths | pass: every ROM byte the game runs as recorded |
| OverSpec | the plain and the sprite build run to play |

## Recordings
- The rzxarchive lists a recording of this game and denies its distribution. The two here are machine-played from
  the snapshot: the toolkit's recorder (48K, Kempston) driven by a small explorer that tries ten bursts of input,
  keeps the one that runs the most new code, plays on, and starts a new game from the menu when one ends (one
  unbroken recording each, no state reloaded; the explorer is in the pilot run folder): 20,273 and 20,153 frames, 6 games each.
- The graphics the recordings do not reach are covered by the unit cases: every graphic of the type table at
  eight places in three colours through the game's own plotter.

## Feasibility (PLAYBOOK 3d, 2026-11-20)
- 16K game in a 48K snapshot. IM 1: the ROM's handler runs; interrupts are on in most of the code; the main loop
  is not frame-synced (as Pssst and Jetpac). Hook time is game speed.
- The plotter (0x763A) has Jetpac's and Pssst's control flow: the same entries (0x75C0 both frames given, 0x75CC
  move, 0x75FD and 0x7617 draw only, 0x7602 and 0x7607 erase only), the same old-frame and new-frame set-ups
  (0x7557 / 0x755A and 0x7584 / 0x7587) and the same walk up the two frames. The row routine is its own: a graphic
  is [H, H rows of 2 bytes, bottom line first], 16 pixels wide, shifted at run time to the pixel x (the shift is a
  jump the set-up writes into the routine) and XORed into three bytes.
- The set-up cuts a figure at line 159: rows under it are skipped. The compare is signed, so a figure whose bottom
  line is above line 31 counts as far under the bottom and is not drawn at all.
- Graphics: the type table 0x7702, a word a type, types 1-48: 34 graphics, all fixed data. Every handler gives a
  type; none passes a pointer of its own.
- Objects: 0x5F35 + 8i, i = 0-9 (+0 type, +1 x, +2 y, +3 colour): Charlie, his flour bombs, the ingredients, the
  nasties. No figure is drawn once and left: every draw in the recordings is an object's.
- Colour: after a plot the handler paints (IX+3) over the figure's cells (0x74EE, 14 CALLs or JPs), left of a
  column limit the game itself rewrites (0x7516, from 0x5FF8 and 0x6D4B).
- The code from 0x7E18 is a stale copy of part of the plot code: nothing calls it.
- No game logic reads the screen but the plotter's own XOR; collisions use coordinates.
- Other screen writers: text, the pantry, the bowl, the clears. Left as they are.

## Build (stage 2, 2026-11-20; asm/cookie_hooks.asm, nexclash/cookie.py; after pssst)
The game's bitmap stays the original's; sprites lie on the figures' own pixels.
- The engine is pssst's shape at this game's addresses (the draw hook, the erase-only entries, the bitmap clear at
  its three CALLs, the plot's set-up at 28 MHz to pay for the hook, R kept, the whole alt ROM image, the loading
  screen), with these differences:
- The draw hook is at the new-frame set-up's CALL of the screen address (0x75A9): it places the object's sprites
  from (IX+1) and (IX+2), not from the screen address. A graphic is 16 pixels wide: 2 sprites an object (up to 32
  lines), no pre-shifted copies, 38 patterns.
- The colour paint: every object has sprites, so its store is changed in place, LD (HL),D to LD A,(HL) at 0x7519:
  the same time, flags and R, no colour, and the game's own rewriting of the routine still works. (A copy of the
  routine, as in pssst, kept the column limit it was assembled with: the replay found it.)
- The sprites' window ends at line 159, as the game's cut. A figure whose bottom line is above line 31: the
  object's sprites go off, as the game draws nothing.
- The plotter XORs, so the original's plot on an empty screen shows the old frame as well. The reference for the
  sprites is a model of the figure (the graphic's 16 pixels at x, bottom line at y, the cut); the model is checked
  against the original's own plot wherever the entry draws without erasing, in the replay and in every unit case.
- A graphic the table does not hold: the object's sprites go off. None exists in this snapshot.
- Hook code and tables in the alt ROM image at 0x386E; entries, R and the speed latch in hook RAM at 0xB000 (a 16K
  game never addresses it). Interrupts stay on in the hooks.
- DMA / DDMA (docs/DDMA.md): not used. The patterns are sent once at set-up; a hook writes only sprite attributes.

## Enhanced (2026-11-20, first pass; owner: "have codex do the enhanced colours")
- Sheet: one picture a distinct shape (34), painted by a Codex pass from a brief; files in the owner's painting
  folder (`nexclash-cookie`); `sheet2colours.py` (pilot tools) makes `cookie_colours.json`, kept beside the snapshot: it holds
  the figures, so it is not in this repository.
- These sprites have one palette for every figure: 13 fixed colours (nibbles 2-14 of every palette offset, 9 bits
  each, written by the set-up) and nibble 1 = the object's own colour at run time. A pixel left unpainted keeps
  the game's colour, so a figure the game shows in several colours still does. 34 pictures have painted pixels.
- The hooks and tables are the same as the default's: only the patterns' nibbles and the 13 colours differ. The
  default build's set-up writes zeros there and no pattern of it uses them.
- Verify: the replay and the unit cases run for both builds; a sprite pixel must be the object's ink where the map
  leaves it and the map's fixed colour elsewhere.

## Hardware checklist
Starts from the menu after the loading screen (a key or 5 s); menu and keys as the original; Charlie, his flour
bombs, the ingredients and the nasties in their own colours with no colour spilling onto each other; a figure cut
at the bowl's line as the original; nothing left behind after a lost life or a new level; sound unchanged; the
game's speed as the original's over a minute of play.

## Open
1. The recordings are machine-played: later levels are proven by the unit cases, not in play.
2. The Enhanced painting is a first pass the owner has not seen in play; where the painted map lives for a public
   patch (it holds the figures; the .nxc carries the painted patterns).
3. Pace is by construction (the plot's set-up at 28 MHz pays for the hook, as Jetpac 1.3); not measured in JNext.
4. Under the sprites the game's XOR still leaves holes where two figures cross; the sprites cover them.

## Decisions
- 2026-11-20 (owner): "Let's finish off the ultimate games". Default as Jetpac's published patch: the game's own
  colours, figures as sprites.
- 2026-11-20: the bitmap is kept (the figures stay drawn under their sprites); only the colour paint goes.

## Lessons
- [local: this engine's build step] An Enhanced build's fixed colours were compared as symbols only, never with
  the RGB the set-up uploads (Codex review 2026-11-20): palette_wrong replays the boot's NEXTREG writes against the
  painted map, the default build as its negative.
- [local: this game's verifier] An XOR plotter on an empty screen draws the frame it means to erase: the empty
  screen is a reference only for an entry that draws and erases nothing. A model of the figure is the reference
  elsewhere, and the draw-only entries check the model.
- [local: this game's verifier] That check found what the model missed: the game draws nothing for a figure whose
  bottom line is above line 31 (a signed compare in the cut), and the sprites had shown one line of it.
- [local: this game's hooks] A copy of a routine the game rewrites as it runs keeps the bytes it was assembled
  with. Where every caller wants the change, the one instruction is changed in place.

## Friction
- reuse: [local: this game's module] pssst's module and hooks, turned into this game's by one script and a new
  alt ROM part (place by x and y, 2 sprites an object).
- retries: [local: this game's hooks] the paint's copy, then the store in place; the model's cut above line 31.
- hand-rolled: [local: private run folder] dbg.py, dbg2.py, dbg3.py (one site or one figure, original against
  patched or model).
- environment: [local: this machine] none new.
- scratch: [local: private run folder] the run folder's tools.

## Technique use
- patch.xor-overlay-keep-ula: helped: the bitmap compares equal; with an XOR plotter removing the stores would
  have changed what the game reads back.
- patch.preserve-r: helped: taken whole from jetpac_v11.
- patch.restore-speed: helped: the same.
- patch.whole-altrom-image: helped: the game runs the ROM's interrupt handler; the image is Sinclair's ROM.

## Stage log
- 2026-11-20: stages 0-3 in one session (machine-played recordings; the plotter read against Pssst's; pssst
  adapted), about 2 h (one full check of 50 minutes), about 25 tool calls, no user round of its own (the owner's
  request for the Ultimate games).
