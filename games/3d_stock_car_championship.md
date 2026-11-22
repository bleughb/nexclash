# 3D Stock Car Championship (Ace Software / Firebird, 1988) - engine `stock_car_3d`

48K. Code: nexclash/stock_car_3d.py, asm/stock_car_3d_hooks.asm, docs/profiles/3d_stock_car_championship.json
(after any .asm edit: `python tools/asm2profile.py 3d_stock_car_championship`), art in
assets/3d_stock_car_championship/ (original paintings and layouts: no game data). Dispatch: nexclash/engines.py,
by signature at 0xC55A. Reference: 3d_stock_car_championship/3d_stock_car_championship.z80 (the menu) +
3d_stock_car_championship.rzx (Jon, 2026-11-16: one scripted race of 200 seconds, no human player).

    python nexclash.py auto 3d_stock_car_championship.z80 --rzx 3d_stock_car_championship.rzx --no-record

| Output | MD5 | Status |
|---|---|---|
| 3d_stock_car_championship.nex (plain, tail 0x5B00) | 7ffdcd3ec8660074a1fcc697d521cfe7 | boot sim OK |
| 3d_stock_car_championship_sprites.nex (base: the game's own car shapes and colours as sprites; 1MB) | 6edc58d59de04c69261df37391ec7fcb | RZX IDENTICAL, unit tests PASS; hardware: plays fine (owner, 2026-11-17) |
| ..._engines.nex (toggle "Engines") | 3de0a63ac436f98d8a6304ddc8893f2b | unit tests PASS; hardware untested |
| ..._painted.nex (toggle "Enhanced colours": the painted cars) | depends on the art | unit tests PASS; hardware untested |
| ..._backgrounds.nex (option "Backgrounds": 25 painted circuits + menu; needs 2MB) | depends on the art | unit tests PASS; hardware untested |
| ..._painted_backgrounds.nex, ..._engines_backgrounds.nex (a toggle with Backgrounds) | depend on the art | boot sim OK |
| ..._everything.nex (all three: the other build the RZX is verified on) | depends on the art | RZX IDENTICAL |

## Jon's decisions (2026-11-16)
- The four cars become painted 4-bit sprites (one livery per car, by the game's ink), drawn OVER the game's own
  cars, which stay on the ULA: the game reads its screen for collisions and for the computer drivers.
- Each of the 25 circuits gets a painted Layer 2 backdrop, 320 x 256, and the menu / text screens one more.
  The game's own stands, trees and flags are covered by Layer 2 priority colours, never erased.
- Engine sound for every car on the Next's sound chips is a toggle, off by default. The game's own beeper
  sound (car 1 only) is untouched.
- Cars only is the base build (1MB Next). The pictures are an option that needs a 2MB Next.
- 2026-11-17: the base keeps the game's own car shapes and colours; the painted cars became a toggle
  ("Enhanced colours"), so any Next is offered them. Menu names: main line "Colour", pictures "Backgrounds".
- "Smoother movement" was dropped: the game already moves and draws every frame.

## Patch design
- Overlay (card patch.xor-overlay-keep-ula's idea without the XOR): the game draws, erases and tests its cars
  exactly as before. Six attribute writes `LD (HL),B` (0xC8AE, C8B7, C8BF, C8CF, C8D8, C8E0) become NOP: a car
  no longer colours its cells; the sprite carries the colour. ULA palette: black paper is see-through, ink solid.
- Alt ROM only (hooks from 0x386E), no RAM page, no state of their own in the game's memory.
- e_done at 0xC90D (replaces `DEC A / JP NZ,0xC8FD`, then does the routine's RET): after "draw all cars" has
  settled each car's move, sets sprites 0-3 from the ACCEPTED place (IX+0x08), (IX+0x05) and the image the
  game's own rule (0xC35D) gives for the accepted heading (IX+0x0B), (IX+0x0A). The proposed fields (+0x46,
  +0x43, +0x5F) are wrong after a refused move (about one draw in nine). x + 32, y + 28 (the image sits 4 rows
  down in its 16 x 16 pattern); (IX+0x5F) = 28 or a car not in the race hides the sprite. With the Engines
  option, then writes the sound chips: cars 0-2 on chip 1 A-C, car 3 on chip 2 A, noise on chip 2 B for a
  crash or a skid.
- e_cls at 0xF9D0 (replaces `LD H,0x5B / LD B,0x18`): silences the chips, hides the sprites. Called from
  0xBEDE (returns to 0xBEE1) it is the clear before a track: Layer 2 off. Any other caller (through 0xF9CE)
  is a text screen: the menu picture is shown.
- e_track at 0xD27B (replaces `LD D,0xD6 / EXX`): shows the picture listed under the track data address at
  0xD4B9. Both use `show`: index in bank 21's first page (35 bytes a picture), palette + ten ZX0 streams
  unpacked into Layer 2 (banks 16-20) at 28 MHz with interrupts off and a stack of its own in the printer
  buffer; the game's pages, the speed and the interrupt state are put back. The key of the picture Layer 2
  holds is kept in the index page, so nothing is unpacked twice.
- The game starts on its menu with no clear: the build pre-fills Layer 2 with the menu picture and setup
  loads its palette.
- Bank use: 11 patterns, sprite palette, menu palette; 12 alt ROM image; 16-20 Layer 2; 21-46, 48-89 the
  packed pictures (47 is the converter's).

## Game facts
- Car records 0xD900 + 0x100 n, count at 0xF994 (records are compacted when a car is UNWANTED; +0x3B is the
  original car number). +0x01 speed, +0x10 bit 6 crash, bit 7 skid, +0x3F ink, +0x52..0x57 attributes kept
  under the car. 28 images of 16 x 8 at 0xBA86 (26 bytes each, the last 5 rows never drawn).
- 0xC55A "draw all cars" runs every frame (HALT at 0xC57C): erase, collision tests on the screen, draw, then
  the loop at 0xC8FD commits each move unless a collision refused it (bit 7 of +0x10). That loop is also
  called on its own when the cars are placed.
- 25 circuits (the game's text says 24); track data from 0x5E88, the 25th at 0xF047. 0xD4B9 points at the
  circuit's data when 0xD27B draws it.
- IM 2 with an empty handler. No LD A,R and no LD A,I anywhere: R has no consumer.
- The game writes below 0x4000 while drawing (ignored on a 48K, and here).

## Pacing measurement
Recording of 10,003 frames (one race, four cars): "draw all cars" runs 9,002 times, each with one HALT (no per-frame
count was asserted); each car's controls and timer run every fourth pass. The hooks add work after the draw (four sprites; with
Engines about forty port writes) and nothing before the frame wait. Not measured: T-states of the hooks, busy scenes
on other circuits, hardware.

## Dependency investigation
Exercised in the recording: 0xC55A whole, 0xC8FD loop on its own (8 calls), 0xF9D0 (1), 0xD27B (2). Screen pixels are
read for collisions and by the computer drivers, so the game's cars stay on the ULA. Attributes are read only at
the six instructions 0xC8A7, C8B0, C8B9, C8C8, C8D1, C8DA (36,008 times each), each keeping one cell. R and I are never read. The printer buffer is never
touched. Beeper sound is untouched. Not exercised: text screens other than the start, circuits 2-25, fewer than four cars.

## Divergent state (ENGINE_CONTRACT exceptions)
- R is not preserved by the hooks: no instruction in the game reads it (unit test "no LD A,R or LD A,I").
- Attribute cells under a car, and the six bytes per car record (+0x52..0x57) where the game keeps those cells'
  old attributes: the patched game never colours them, so they differ from the original's. Consumers: only
  0xC8A7-0xC8E0 inside the draw routine, which copies attributes to those bytes and back. The verifier carries
  the patched game's own copy of both from event to event and runs the patched code on it; registers and every
  other byte of memory must still match. Every read in the recording is audited: an attribute read by anything
  but those six instructions, or a kept byte read from outside the draw routine, fails. None.
- The printer buffer (0x5B00-0x5BFF) is the hooks' stack while pages are swapped: the game neither reads nor
  writes it in the recording (every access audited).
- The frame wait (HALT) is stepped over in both runs of an event.

## Verification
RZX 10,003 frames, replayed twice: on the build with every option on and on the cars-only build. Each: 9,002 car
draws, 1 clear, 2 track draws, 1,227,976 car pixels found under their sprites - IDENTICAL: all registers but R, T and
MEMPTR, the interrupt state, all memory but the divergent state above and 32 bytes below the stack pointer; every
write below 0x4000 at the same address; no write to a patch site; the patched code never changes an attribute's
value; all five attribute bytes of each sprite (the game's accepted place, the game's image, plain 4-bit, no mirror
or scale); Layer 2 and its palette equal to the picture, Layer 2 off while it is unpacked, nothing unpacked when the
picture is already held; only the Next registers and ports the hooks own; pages and speed put back. A HALT other
than the game's frame wait fails the run. A recording that reaches no car draw fails.
Unit tests 3,236 cases: the hook on 1,536 hand-set car states (1-4 cars, every heading, hidden cars, screen edges)
with the Engines option on and off; every picture, a track with none, the same picture twice; the clears before a
track and for a text screen with interrupts on and off; a text screen after a race (the menu picture comes back);
the setup stub (patterns, sprite palette, see-through black, the menu picture and its palette); the builds with an
option off; every painted pattern covers the game's car. Negative controls detected 6/6: a sprite one pixel off its
car, and a colour write left in the game.
Not proven: behaviour with an interrupt taken inside a hook (the handler is empty; `show` runs with interrupts
off and reads the interrupt state twice, card patch.iff-safe-read; interrupts are lost while a picture unpacks and
the game does not count them); the rendered picture of a sprite (attributes and pattern bytes are checked, not
pixels on a display).

## Known visual differences (by design)
- Cars are painted sprites in front of everything on the ULA; a car no longer tints its attribute cells.
- The game's stands, trees and flags are hidden under the backdrop on a circuit that has a picture.
- A pause while a circuit's picture is unpacked (not timed on hardware).

## Open
- The recording is one scripted race on circuit 1 (no human player, four cars). Circuits 2-25 and the text
  screens are covered by unit tests and by emulator runs (OverSpec: all 25 circuits to FINAL POSITIONS), not
  by a recording. A human recording across several circuits, and one with fewer than four cars, are owed.
- Packaging: `nexclash.py patch` makes the whole .nxc since nexclash/nxc.py was re-vendored (SET3): Backgrounds
  as the option offered only on a 2MB Next, Enhanced colours and Engines as toggles on any.
- Engine sound has only been measured (60 Hz ticking over, rising with speed), not judged by ear; no stereo;
  it does not follow the game's own SOUND OFF setting.
- Hardware: the owner played it on a real Next, 2026-11-17: played fine (which options were on was not
  noted, so the checklist below is not ticked item by item). Hook timing not measured.
- Colour sheets / recolour (PLAYBOOK 5) are not provided: the art is edited as assets/.../cars.png (layout in
  cars_layout.json) and the circuit pictures.

## Hardware checklist
1. Menu on its picture from the first moment; instructions (I held) and FINAL POSITIONS on the same picture;
   text readable.
2. Race: four painted cars exactly on the game's cars at every angle; no white or coloured car pixels showing
   round a sprite; no stale sprite after a crash, on the grid, or on a text screen.
3. Each circuit shows its own picture; the game's fences, start line and timers are clear of scenery.
4. The pause when a circuit loads is short; no garbage on the screen during it.
5. Engines on: a note per car that follows speed, noise on a crash; silence on the menu and results.
6. Cars-only build on a 1MB Next: as the original but for the cars.
7. Faults: Fuse "Record from snapshot" on the .z80, autosave off, send the RZX.

## Lessons
- [kb lesson.sprite-from-committed-state: sprite from the accepted state] a sprite set from a routine's proposed fields sat off the car after
  a refused move; set it after the commit, from what the game drew from.
- [local: a caller tells the screens apart] one clear routine serves text screens and the track; its return
  address distinguishes them without any state.
- [kb lesson.nex-header-bank-byte: this engine sets it in auto(); raised in the pull request] a build that adds banks above 47 must say so in
  .nex header byte 8, which the converter leaves at 0.
- [kb lesson.nxc-tape-patch-recipe: closed in this pull request, nexclash/nxc.py re-vendored] this repo's packager could not make an
  option that needs more memory (SET3); the re-vendored one does, with toggles beside it.
- [card patch.iff-safe-read §Use] `show` first trusted one LD A,I; review caught it, hooklib.iff_audit now says twice.
- [kb lesson.loader-clears-turbosound-bit: turbosound after setup] the loader clears NR 0x08 bit 1 after the setup stub; a hook that needs the
  second chip must set it itself.

## Technique use
- patch.xor-overlay-keep-ula: helped: the idea of keeping the game's own figure on the ULA under the sprite.

## Friction
- reuse: [local: this game's build] chuckie.py as the loop to adapt; hooklib.CMP; simpool; z80n.install.
- retries: [local: this game's build] the sprite hook moved from the frame wait to the end of the commit loop after measuring coverage.
- environment: [none: nothing new about the environment]
- hand-rolled: [local: game-specific model, no shared replacement] the paging model for the patched run (pages, MMU slots, Layer 2 palette) in NextState.
- scratch: [local: they build against a private emulator] measuring harnesses kept outside the repo.

## Next session
Stage 3 done in software; played fine on a real Next (owner, 2026-11-17). Next: a human recording over
several circuits; the checklist item by item with each option on; whether Engines sounds right.
