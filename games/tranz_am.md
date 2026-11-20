# Tranz Am (Ultimate Play The Game, 1983; 16K)

## Next session
Stage: 3 (verified, stamped)   State: 2026-11-20: the cars and the roadside items as sprites on their own pixels in
their own colours, over the game's unchanged drawing; verified on two machine-played recordings and unit cases
over every type; runs in OverSpec; not on hardware
Inputs (private, pilot runs/tranz_am/reference_files/tranz_am): tranz_am.z80 (TOSEC "[a2][16K]", at the game's
menu), tranz_am_m2.rzx + tranz_am_m3.rzx (machine-played, see "Recordings"), tranz_am_loading.scr (the tape's
screen), enNextZX.rom (the Next's ROM, for the verifier's ROM model)
Branch: add-tranz-am    Commit: this one    Checks: selftest --game tranz_am --verify --stamp, doccheck
Pending user answers: "Open" 1-2
Start with: a recording played by hand (night, the cups, a long drive), then hardware
Read: "Build", "Open"

## Result (2026-11-20)
Techniques: `patch.xor-overlay-keep-ula`, `patch.preserve-r`, `patch.restore-speed`, `patch.whole-altrom-image`

Two whole machine-played recordings (20,133 and 20,031 frames, 7 games each).

| | |
|---|---|
| Builds | tranz_am_sprites.nex 91a66955 (cars and roadside items as sprites in their own colours, loading screen), plain 8308134d |
| Verify | IDENTICAL on both: 26,818 figures as sprites (2,796,472 sprite pixels against the model of the figure, and the model against the original's own plot at every draw-only entry), 162 draws past the set-up's start left to the game, 393 erases, 78 clears, 26,818 draws from their entry, every pace site; every register with R and all memory, the bitmap too; 16,885 paints not painted and 17,536 (the fixed block) left to the game; the alt ROM's IM 1 handler against Sinclair's at 39,986 interrupts |
| Unit | PASS: 3,264 graphic cases (all 34 types x 8 places x 3 colours x four objects, through the draw-only entry: sprites, model and the original's plot agree), 16 speed cases, erases, clear, 12 paint cases, 6 guard cases, a type not in the table, negative control 40 of 40 |
| Negative | 6 broken builds, all detected |
| Boot | simulated: registers and RAM as the snapshot |
| ROM paths | pass: every ROM byte the game runs as recorded |
| OverSpec | the plain and the sprite build run to play |

## Recordings
- No recording of this game could be had. The two here are machine-played from the snapshot: the toolkit's
  recorder (48K, Kempston) driven by a small explorer that tries ten bursts of input, keeps the one that runs the
  most new code, plays on, and starts a new game from the menu when one ends (one unbroken recording each, no
  state reloaded; the explorer is in the pilot run folder): 20,133 and 20,031 frames, 7 games each. The explorer
  crashes the car often and does not drive far.
- The types the recordings do not reach are covered by the unit cases: every type of the table at eight places in
  three colours for four objects through the game's own plotter.

## Feasibility (PLAYBOOK 3d, 2026-11-20)
- 16K game in a 48K snapshot. IM 1: the ROM's handler runs; interrupts are on in most of the code; the main loop
  is not frame-synced. Hook time is game speed.
- The plotter (0x7170) has the control flow of Jetpac, Pssst and Cookie with one entry (0x7101: the old type at
  0x5E22, 0 = draw only through 0x7149) and an erase-only entry (0x7139); old-frame set-up 0x70B2 / 0x70B5,
  new-frame set-up 0x70D2 / 0x70D5. The row routine: a graphic is [H, H rows of 2 bytes, bottom line first], 16
  pixels wide, shifted at run time (a count at 0x5E40 / 0x5E41), the old frame ANDed out and the new one ORed in.
- The set-up cuts a figure at the top: at most y - 8 rows are drawn, so no row above line 9.
- Graphics: the type table 0x7F06, a word a type, types 1-34: 28 graphics, all fixed data.
- Objects are not one table: the roadside items (trees, rocks, cups: 7 slots of 3 bytes from 0x5E50: type, x, y;
  their colour is a byte the game keeps at 0x5E42 and gives to the paint) and the cars (0x5E80 the player's, then
  0x5E8C and 0x5E98: +0 type, +1 x, +2 y, +3 colour).
- Colour: after a plot the handler paints over the figure's cells (0x704B with (IX+3), 0x7052 with a colour
  given); the paint leaves cells whose attribute is 0x76 and the top row alone. A third caller (0x6AC8) paints a
  fixed block of cells that is no figure.
- Two routines (0x6472, 0x6893) CALL the new-frame set-up past its start with a place and a graphic of their own
  and then the draw-only end: not an object's figure (IX is whatever it was).
- No game logic reads the screen; collisions use coordinates.
- Other screen writers: the dots of the ground (0x6EFD), the map, text, the clears. Left as they are.

## Build (stage 2, 2026-11-20; asm/tranz_am_hooks.asm, nexclash/tranz_am.py; after cookie)
The game's bitmap stays the original's; sprites lie on the figures' own pixels.
- The engine is cookie's shape at this game's addresses (the draw hook at the new-frame set-up's CALL of the screen
  address, the erase-only entry, the bitmap clear, the plot's set-up at 28 MHz to pay for the hook, R kept, the
  whole alt ROM image, the loading screen), with these differences:
- An object is known by its IX from a list (7 items, 3 cars): 2 sprites each. A roadside item takes the colour
  the game keeps at 0x5E42, a car its (IX+3).
- The game's own entry marks a draw (a byte in hook RAM); the draw hook places sprites only for a marked draw, so
  the two routines that CALL the set-up past its start change no sprite.
- The colour paint: its two CALLs for objects go to a copy in hook RAM whose store is a read (the same
  instructions, flags, R and time, no colour); the fixed block's CALL is not changed. The routine is not rewritten
  by the game (checked: no store into it).
- The sprites' window starts at line 9, as the game's cut at the top.
- The reference for the sprites is a model of the figure; the model is checked against the original's own plot
  wherever the entry draws without erasing, in the replay and in every unit case.
- A type the table does not hold: the object's sprites go off.
- Hook code and tables in the alt ROM image at 0x386E; entries, the paint's copy, R, the speed latch and the mark
  in hook RAM at 0xB000 (a 16K game never addresses it). Interrupts stay on in the hooks.
- DMA / DDMA (docs/DDMA.md): not used. The patterns are sent once at set-up; a hook writes only sprite attributes.

## Hardware checklist
Starts from the menu after the loading screen (a key or 5 s); menu and keys as the original; the car, the other
cars and the roadside items in their own colours, the car keeping its colour as it crosses an item and the item
its own; day and night; nothing left behind after a crash or a new game; the map, the dials and the cups
untouched; sound unchanged; the game's speed as the original's over a minute of driving.

## Open
1. The recordings are machine-played and short drives: night, the cups and the other cars at length are proven by
   the unit cases, not in play.
2. No Enhanced (painted) set: the default is the game's own colours, a colour an object.
3. Pace is by construction (the plot's set-up at 28 MHz pays for the hook, as Jetpac 1.3); not measured in JNext.
4. The clash this removes is small in this game: a car and a roadside item sharing cells.

## Decisions
- 2026-11-20 (owner): "Let's finish off the ultimate games". Default as Jetpac's published patch: the game's own
  colours, figures as sprites.
- 2026-11-20: the bitmap is kept (the figures stay drawn under their sprites); only the objects' colour paint goes.

## Lessons
- [local: this game's hooks] A set-up that other routines enter past its start cannot tell the hook whose figure
  it is from IX alone: the game's own entry marks the draw, and an unmarked one changes nothing.
- [local: this game's verifier] An event that starts in the middle of a draw has to be given what the hooks before
  it left (here the mark), or it tests a state the game never has: all 794 draws failed until it was.
- [local: this game's hooks] A negative control that changes "the first LD A,n after the entry" changed the mark's
  constant, not R's: the hook's lines were reordered so the control changes what it names.

## Friction
- reuse: [local: this game's module] cookie's module and hooks, turned into this game's by two scripts.
- retries: [local: this game's verifier] the mark in the mid-draw events; the stop of a draw that came past the
  set-up's start.
- hand-rolled: [local: private run folder] none new.
- environment: [local: this machine] none new.
- scratch: [local: private run folder] the run folder's tools.

## Technique use
- patch.xor-overlay-keep-ula: helped: the bitmap compares equal.
- patch.preserve-r: helped: taken whole from jetpac_v11.
- patch.restore-speed: helped: the same.
- patch.whole-altrom-image: helped: the game runs the ROM's interrupt handler; the image is Sinclair's ROM.

## Stage log
- 2026-11-20: stages 0-3 in one session (machine-played recordings; the plotter read against Cookie's; cookie
  adapted), about 1.5 h (one full check in the background), about 15 tool calls, no user round of its own (the
  owner's request for the Ultimate games).
