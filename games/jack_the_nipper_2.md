# Jack the Nipper II - In Coconut Capers (Gremlin Graphics, 1987) - stage 2 done; the whole-recording stamp running

Techniques: `patch.scratch-redirect`, `optimise.pattern-cache`, `patch.restore-speed`, `detect.pacing-structure`, `detect.gameplay-screen-readers`

## Next session
Stage: 3 (prove + deliver)   State: engine, units, negatives, record and test .nxc done 2026-11-23; the stamp
(`selftest.py --game jack_the_nipper_2 --verify --stamp`, ~4 h) was running at the laptop's shutdown
Inputs: TOSEC `Jack the Nipper II - In Coconut Capers (1987)(Gremlin Graphics Software)[a].z80` (md5
6f5d708c439f3356a930ea4f176a0c8f: 48K, in game); rzxarchive `j/jacknipper2.rzx` (158,593 frames, 52 min)
Reference: reference-local/jack_the_nipper_2 (to bleughb/specnext with the PR)    Branch: add-jack-the-nipper (local)
Start with: the stamp's result (rerun it if it never finished); then "Results" + the record's result `pass`, the
owner's test of `~/nxc-test/Jack the Nipper II 1.0 test`, colour sheets (docs/COLOURS.md), the PR with Jack the Nipper
Open: pace 4.5 % (below); Immunity untested in play; the rope (drawn another way) stays on the ULA in the scenery's
colours (owner question, below)

## Snapshot (0b)
- The plain TOSEC `.z80` (812f365c792c8af30edafcf227843a96) is a BASIC loader (`LOAD ""SCREEN$`, "IBM copy by
  Cysio", PC in ROM PAUSE): not a build input. The `[a]` snapshot is in game: 48K, PC 0xBC79, IM 1 with interrupts
  OFF, I = 0x3F, SP 0xFFFA.
- The recording was made on a 128K machine running the 48K game: 0x7FFD = 0x10 (the 48K ROM, bank 0 at the top,
  paging as a 48K machine), banks 1, 3, 4 and 6 empty, and RAM 97 % equal to `[a]` (the rest is game state). So the
  build targets the 48K game and this recording can verify it.

## Survey (2026-11-22, the whole recording, from the TOSEC loader snapshot's survey: the replay uses the RZX's own start)
- Engine: unknown (no detector, no TID / Dizzy 1 signature): a new engine, feasibility first (PLAYBOOK 3d).
- Rendering: 0xB25F writes 62 % of the pixel bytes (164 bytes a call, 55,675 calls) reading 0xFB00-0xFD7F,
  0xBDC0-0xBDFF and 0xF940-0xFA3F: a copier from a composed buffer. 0x935E / 0x939F draw the status panel's
  numbers; 0x967F (482,000 T a call, 498 calls) redraws whole screens; 0x9B1A (21 callers) prints text.
- Pacing: no interrupt accepted in 158,593 frames: no frame sync (as Jack the Nipper).
- Coverage: GATE CHECK: 0x967F's call from 0xA958 and 0x9B1A's calls from 0x9B62 / 0x9B9C never ran (code near them
  did). 0x967F is a screen redraw and 0x9B1A a text printer, not figure plotters: likely a message or screen the
  recording did not bring up; confirm in stage 1.
- Plain conversion: built from the loader snapshot, so not meaningful; rebuild from `[a]`.

## Stage 1 analysis (2026-11-22/23)
- 0xB25F is the object loop, not a copier: a table at 0x88E2, 11 bytes each, count at 0xBDF2; per object 0x9D91 then
  the draw at 0xB28B: x = (IX+0) (+-6 by (IX+5) bit 0 for some types), y = (IX+1), (IX+8) bit 5 = skip.
- No shadow screen (unlike Jack the Nipper): the draw composites straight onto the screen: screen address from x / y,
  the attribute map at 0xFB00-0xFD7F (32 x 24 cells), background tiles at 0xE900 + 8 x tile (IY), graphics fetched with
  SP as a data pointer (POP blits, SP saved at 0xBDE8), widths patched into the code (self-modifying, 0xB412 / 0xB417
  ...), a path per (IX+2) type bit (0xB5D3, 0xB534, 0xB3B1). A conversion splits the composite: background only to the
  screen, the figure as sprites.
- Correction (2026-11-23): the draw composites into a cell buffer, not onto the screen. Per object: 0xBA56 clears
  0xE900-0xECFF (PUSH 0); 0xBAF9 / 0xBB64 / 0xBA8A set up the object's cells and its colour ((IX+9) into the cell
  colour list at 0xBD68); the blit masks the figure into the buffer (AND mask, OR graphics; column stride 24 / 32 / 40
  bytes, INC IY per pixel row). After the loop, 0xBC62 walks the dirty-cell map 0xFB00-0xFD7F beside the tile map
  0xF800 and writes changed cells to the screen (0xBCC7-0xBCD9 pixels, 0xBCEF attributes).
- Figure format: CALL 0x92A3 returns the graphics in HL ((IX+3/4) when (IX+8) bit 6, else by type); per row the mask
  bytes then the graphics bytes, top row first (mask 1 = background shows). Size by (IX+2), as the dispatch at
  0xB2E9 reads it: bit 0 16x16, bit 1 16x24, bit 2 24x24, bit 3 24x32, bit 4 16x24, none 24x32. x & 7 picks a
  run-time shift (a shift ladder, 0xB484); (IX+5) bit 1 draws it mirrored through the byte-reverse table at 0xE800.
  One SP blit per size x shift x mirror: 16 sites (0xB34B ... 0xB9B3), each right after the CALL.
- Census (whole recording, jtn2_figures.py at the 16 blit sites): 142,528 blits, 100 distinct figures (51 of
  16x16, 32 of 16x24, 9 of 24x24, 8 of 24x32): Jack, natives, monkeys, a lion, a hippo, scorpions, snakes, birds,
  the explorer with a gun, fruit and pick-ups, a few sparkle effects. Every figure fits 2 x 2 16x16 sprites; the
  game mirrors at run time, which a sprite's X-mirror bit does for free.
- No pixel logic (`scan --writers`, frames 0-40,000): screen readers are the panel animation (0x935E: cells of the
  bottom rows with attribute 0x6F, pixels rotated in place) and the panel digits (0x93B4); attribute readers the
  panel test and a colour cycler (0xC0B3); buffer readers the maskers and the room decoder (0xAA00). Collisions
  come from the object table, not pixels.
- Design: the owner, 2026-11-23, "you can go on those": the same answers as Jack the Nipper (every figure a sprite, effects too, outline kept, the game's own colours until a painting); not a colour run yet.
- Cheats: see "Cheats" below (checked against the code 2026-11-23).
- Per object (trace, 2026-11-23): 0xBAF9 gives each cell the figure covers a buffer slot (counter 0xBDF1, from 3 each update; the dirty map 0xFB00-0xFD7F entry points at it, 0xBC08) and copies the cell's background tile into it (0xBC19, 8 bytes at 0xE900 + 8 x slot); the blit then masks the figure into those slots through IY; 0xBC62 after the loop writes each slot to the screen. So the buffer keeps the background if the blits land elsewhere: at the 16 sites (LD (0xBDE8),SP, 4 bytes) IY's high byte AND 0x3F maps 0xE900-0xECFF onto the slot-1 page (0x2900-0x2CFF), as Jack the Nipper's RES 6,H. Also: 0xBAF9 writes the figure's colour (IX+9) into the cells' colour list at 0xBD68, which the copier makes the cells' attributes (the clash): the clash-free build keeps the background's attribute there (to design: what the list holds without a figure).

## Design decisions (the owner, 2026-11-23)
The same answers as Jack the Nipper: every figure a sprite (pickups and effects too), the outline kept, the game's own
colours until a painting; no pause or message window known. Not a colour run yet.

## Build (stage 2, 2026-11-23)
- Sites: the 16 blits' `LD (0xBDE8),SP` (4 bytes) jump to 9-byte stubs, which hand their way back to one shared body
  (the page is RAM: a JP operand); the body records the figure (graphics, colour, size, x from 0xB2D5, top, mirror)
  at 28 MHz and moves IY's high byte AND 0x3F, so the blit masks into a scratch copy of the cell buffer at
  0x2900-0x2D4F (slot-1 page 24) and the real buffer keeps the scenery. The copier's entry (0xBC62) commits.
- Colours: each sprite pixel takes the ink or paper of its cell in the game's own colour list (0xBD68), read before
  the commit puts the scenery's colour back in every slot's entry (TILEATTR[TILEMAP[cell]], as the copier's background
  path). So an item coloured per cell (0xBA8A's table at 0x8A36: the pineapple) and the two-colour creatures
  ((IX+6) = 0xD0: white head, red body) look as on the original; where two figures share a cell its one colour serves
  both, as on the original. One palette bank: 1-8 normal black .. white, 9-15 bright blue .. white.
- Patterns: one-colour figures keyed by graphics + pair + colour in slots 0-47 (a two-pixel look-up per build; a miss
  takes the oldest slot of the probe window); several colours: slots 48-63 under an exact signature (x & 7, top & 7,
  mirror, every covered cell's colour), else rebuilt.
- Colour list: the recorded figures' boxes; the game's slot counter (0xBDF1) says when a slot lies outside them (a
  rope is drawn another way, overlapping objects orphan slots), and then the whole map.
- Builds: plain e63f00da, sprites 5e157c09 (record). Page: state 0x2000-0x28FF, scratch 0x2900-0x2D4F, code
  0x3000-0x3B55, the tail's backup 0x3E00, the stub's registers 0x3F00; the start-up tail at 0xBF00 is put back.

## Results
- 3,000 frames (simulator): 2,768 blits, 994 copies, 165,872 figure bytes redirected and checked against the
  original's buffer, 688,466 sprite pixels against the original's colour list, no failure. IY, the values read back
  from the scratch and E' proven dead on the first 300 blits and every 100th after (a proof on every blit: ~40 h).
- auto (2,000 frames, the per-cell build): IDENTICAL; units: every site at four speeds (68 cases), the copy as a hide
  (16), the figure table full (4); negative controls DETECTED: no redirect, colour list not put back, one colour for
  every figure, never mirrored, wrong palette bank, leftover sprites not hidden, the caller's speed not given back;
  the eighth (the multi-colour cache ignoring the colours) caught on 1,500 frames (15 sprite pixel failures).
- The whole recording: the stamp run (pending).
- JNext 1.3.5 headless: both builds reach play; the figures show as sprites, the pineapple green over bright green.

## Pacing
No interrupt accepted in 158,593 frames: no frame sync, so the work is the pace (as Jack the Nipper). The blits still
run whole (redirected), as do the copier and the object loop. The hooks add 4.5 % of the time over the first 3,000
frames (994 updates; 2.8 % over the first 1,000), measured as hook-page T-states with 28 MHz time counted at an eighth:
the colour walk where a rope or overlap sends it over the whole map (1.4 %), the two-colour creatures' rebuilds as
they move (each x alignment colours their cells differently on the original: 1.2 %), the figure colour check (0.5 %).
First build: 14 %; the cache and walk changes above took it to 4.5 %. So the game runs about 5 % slower. Not measured in
JNext (verify.update-locked-pace): open.

## Dependencies
Readers (`scan --writers`, frames 0-40,000): the panel animation and digits read the screen, the colour cycler and
the panel test read attributes, the maskers and the room decoder read the buffer: no logic reads figure pixels;
collisions come from the object table. R is not read. The verifier proves IY (moved to the scratch), the flags and A
read back from the scratch, and E' (the last copied cell's colour) dead.

## Cheats
Every patch carries them, off by default (checked against the code; the archive's are from the Super Collection
"Pokes"): Infinite lives 43251 = 0 (0xA8F3 `DEC (HL)` on the lives at 34886); Infinite ammo 38306 = 0 (0x95A2 `DEC
(HL)` on the weapon's charge, whose zero drops the weapon); Immunity 43212 = 201 (ours: 0xA8CC `XOR A` to `RET` in the
death routine 0xA8C3, so a death never starts; its ten callers all `JP` to it and its own death path returns to the
same level). Not used: the archive's Immunity 1 (34426 = 0 freezes the flashing timer after a hit: Jack flashes for
ever and the charge drains), Immunity 2 (a RET at 0xA8C3 with its `JP`s turned to `CALL`s: the callers run on into
code no death reaches) and Lives 255 (34631: the one-digit lives display). Immunity is not yet tried in play.

## Owner questions (raise on return; the build keeps the current behaviour)
- The rope (a swinging line drawn by another routine, not one of the 16 blits): it stays on the ULA, and its cells
  keep the scenery's colours, so it shows in the scenery's ink. Keep, or the rope's own colour on its cells (the clash
  back on those cells only)?

## Hardware checklist
- Boots from the .nxc menu (cheats off), reaches play; Jack, the creatures and the pickups are sprites over the
  scenery with no colour bleed; the pineapple green over bright green; mirrored figures face the right way.
- A room with the rope: the rope drawn, no stray colours.
- Each cheat on: lives stay, the weapon's charge stays, no death on contact (and no stuck state after a fall).

## Stage log
- 2026-11-22: stage 0, ~1.5 h wall (with Jack the Nipper), ~20 tool calls, no user rounds.
- 2026-11-23: stage 1 analysis (draw path, figure census, readers), ~25 tool calls, no user rounds.
- 2026-11-23: stage 2 (engine, verifier, units, negatives, record, .nxc), ~120 tool calls, no user rounds (design
  as Jack the Nipper).

## Lessons
- [card optimise.pattern-cache §Failure lookup] demonstrated: a miss taking the first unshown slot from the hash
  evicts animation frames the next update needs (Jack: 162 builds of 23 keys in 1,000 frames); the oldest unshown
  slot of the probe window builds each key once; the oldest anywhere is worse (outside the window: never found).
- [card optimise.pattern-cache §Failure lookup] demonstrated: images coloured per cell rebuilt each update under key
  0; an exact signature (alignment, mirror, covered cells' colours) in reserved slots cuts the builds (71 to 15).
- [doc LEARNINGS 2.3] demonstrated: a verifier modelling slot-1 stores by wrapping store opcodes must wrap every form
  the hooks use: CALL cc was left out, the return address was dropped and the commit returned to 0x0000.
- [local: this game's colour model] observed: an item's cells take colours from a table (0x8A36 + 4 x (IX+9)) and
  (IX+6) = 0xD0 objects two colours, so the object's own colour field is not the picture; the verifier compares every
  sprite pixel with the original's colour list instead.
- [local: this game's draw paths] observed: a census at the 16 blit sites missed the rope, drawn another way, whose
  cells also take slots; the colour walk counts against the game's slot counter and falls back to the whole map.

## Technique use
- detect.pacing-structure: used: no frame sync, so the hooks' time is the slowdown; measured per routine
- patch.scratch-redirect: used: IY's high byte AND 0x3F, as Jack the Nipper's RES 6,H
- optimise.pattern-cache: used and amended (the window's oldest slot; signatures for per-cell colours)

## Friction
- reuse: [local: per engine] the verifier shares Jack the Nipper's overlays, slot-1 store model and NextSide (imported)
- retries: [doc LEARNINGS 2.3] the dropped CALL cc return address cost a trace; a `pgrep -f` wait loop matched itself
  (CLAUDE.md already says never; stopped it)
- environment: [none: no workaround]
- hand-rolled: [local: kept with the notes' numbers] the hook-time meter (hook-page T-states, 28 MHz at an eighth) was
  written for this engine, as for Jack the Nipper; a shared one needs each engine's overlay model
- scratch: [local: dropped] hangtrace.py, pace*.py, negone.py, quickverify.py: per-engine harness runs
