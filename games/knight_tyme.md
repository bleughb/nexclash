# Knight Tyme (Mastertronic Added Dimension 1986, 128K edition) - engine `knight_tyme` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: imported into nexclash 2026-11-04 (ported from Jon Attree's .nxc work,
2026-11-04); JNext only, never on a Next.
Inputs: specnext/reference/knight_tyme/ (knight_tyme.z80 md5 8e720b5c, kt_t1 / kt_rooms / kt_over / kt_cmds .rzx,
knight_tyme.tzx = the archive's (128K)[Magic Knight 3].tzx for the loading screen). Pilot run folder: runs/knight_tyme.
Published .nxc: Knight Tyme v1.1 (nexclash-patch patches/, 23485e65): --bare 645401e4.
Start with: hardware checklist. Read: this file. Open: under "Open".

Techniques: none of the cards fit whole; the method is below (see Technique use).

## Inputs
Snapshot: archive "Knight Tyme (1986)(Mastertronic Added Dimension)(128K)[Magic Knight 3].z80", md5 8e720b5cc11fe0d9445fe0af4825c8bf. 128K, title menu, PC 0x90FF in RAM, 7FFD 0x10 (ROM 1, bank 0), IM 2 (I 0xBF -> 0xFFFF: JR via ROM byte 0 -> 0xFFF4 -> JP 0xAF10). ZXDB lookup: 502.
128K edition confirmed at run time: 7FFD values 1, 4, 6, 7, 0x10 in play; every frame AY writes from the ISR's music in bank 4 (CALL 0xC006); OPTIONS has TURN MUSIC OFF / ON; 48 rooms entered by poke.
Menu: Z down, SPACE select (held 4 frames a line). Play: N left, M right, A up, SPACE opens the command window. Recording: ROM 1 = stock 48K ROM (Next's ROM 3), since 128-1.rom adds keypad code at 0x386E; so scan/survey on these RZX desync (use the 128K ROM in a first rzx for those tools).

## Rendering model
Knight: masked composed box 3 x 32 lines: 0xAC1B copies clean bytes from bank 7 (0xE000 = the room's copy of the screen) to 0x5D05 and 0x5D65; 0xAC85 masks in graphics (0xF3F4 + image*96, mask 0xF6F4 + ..; image = shift 0-3, + 4 facing left); HALT; 0xACBE blits the old clean box from 0x64E0; 0xAD54 CALL 0xACBB blits the new from 0x5D05. Run from 0xACE5 every main loop tick (once per HALT), from 0xAD18 at room start.
Characters: 0x7052 -> 0x706C CALL 0xB30F (masked 2 x 4 cells, table 0xC544 idx: graphics, mask) in the room build. Objects: 0x93F2 -> 0x941E CALL 0xB30A (2 x 2). Both before 0x6AAA copies the screen to bank 7. So they are part of the "clean" copy; a character moves only in a rebuild.
Windows: 0x8F76 / 0x8F7E -> 0x8FB8 (rectangle in 25765-25768). A closed window rebuilds the whole room (0x6D7E). 0x7878 / 0x78F8 show a picture in a window through the same plotter: they stay ULA (IX = 25568 tells 0x93E7's from the room's).
Game never reads figure pixels: lockstep below.

## Clash numbers (work/clash_check.py, 2,646 frames, walk through three rooms)
Option PLAYER ATTRIBUTE IGNORE (default, 23705 = 0): 47.1 % of Knight plots span several attributes; 59.6 % of 590,617 ink pixels show a colour not the Knight's own. Kind A: the figures take the scenery's colours. Option UPDATE (23705 = 1): 27.4 % span, 6.5 % other colour (cells with paper bit 5 refuse), and the figure paints scenery cells in its colour. No figure has clash-free mode in the original. Owner's eye: clash; agrees.

## Design (defaults, unattended)
Sites and method: asm/knight_tyme_hooks.asm head. Original plot runs, cells restored, so game instructions are the same in the same order and the same state. Page H = 26 at slot 4, interrupts off in hook bodies only (ISR touches every slot); stubs in alt ROM image 1 at 0x386E. Alt image 0 filled from ROM 0, as 0xC10D in bank 1 (7FFD = 1) reads it as a star map for the Bridge.
Option UPDATE neutralised: 0x6892 LD A,1 -> LD A,0: figures have their own colours in either option. 23705 has five references (0x688D, 0x7071, 0x9428, 0xACFE, 0xAD1F), all attribute painting.
Sprites 16 x 16, 4-bit. Knight: 8 images x 6 tiles cached in patterns 0-47, sum of the 192 bytes + colour keys the cache; slots 122-127 on top. Room figures: patterns 48-127, slots 0-121 from the room build, in plot order; past the pool tiles drop (counted; 50 objects in one room only, unit test).
Colours: ink from the game's own table (Knight 25162, characters 0x7086, objects 23695). Game's mask = solid silhouette with black knocked-out paper. Outline: a 1-pixel ring round the mask, white; for white figures black, round ink only, as the mask is already their halo.

## Crew on the Bridge (owner's report after playing, 2026-11-03)
The two seated crew in room 1 are room graphics: their heads, hands and shoulders sit in the cyan cells of the window frame's row. They stay on the ULA as drawn; site 0x6F0A adds sprite tiles over their ink, from the room's own pixels (page 27). The tiles are never stored here: each build derives them from the player's snapshot (`crew_tiles`: room 1 built in a simulator to 0x6F0A, the crew's pixels read from that screen as work/mkcrew.py first did), and refuses unless the cells' sum and the tiles' MD5 are the profile's `overlay` pins (the approved build's): heads and hands skin (palette index 2, unused by any figure: verify checks), the shoulder pixels in cyan cells white. Lowest sprites, so everything else stands in front. If the cells' sum differs from the room's, no tiles; verify fails if the Bridge is ever built with cells unlike the profile, and checks every crew pixel in the sprite layer. Right crew's right hand: (178,151) added after the first build left it cyan. JNext (jn/fix/): the Knight walks past both crew in front of them; rooms 4, 12, 23, 27, 37 frames identical to the pre-crew build, room 1 differs at the crew and in the Knight's walking frame (the room build takes a little longer). out/knight_tyme_fix.png. Not on the colour sheets.
All 48 rooms checked on contact sheets (work/roomshots.py, png/rooms0-3.png), with the people and machines zoomed. Same fault nowhere else. Characters drawn as scenery: Hooper on his throne, room 45, cell-aligned colours, no fault seen, left as drawn. Droids (rooms 13, 19, 25, 32, 34), helmets, crane: cell-aligned, left as drawn.

## Defaults taken (a human would have decided)
1. Objects and characters count as figures. 2. Hand pointer, pictures in windows, text, icons stay ULA. 3. Depth: objects, characters, Knight on top. 4. Window: only tiles the figure really fills under the window hide; pieces of a figure can go while a window is up; the original shows figure pieces beside a window the same way. 5. Option UPDATE is no longer different.

## Results
| Output | MD5 | Status |
|---|---|---|
| knight_tyme.nex (plain) | 0f91cab91a9261bb8645a0ec9cc871f2 | boot sim OK, reaches play in JNext |
| knight_tyme_sprites.nex | a7a1ee37f10071663a58bcdc37109132 | below; reaches play in JNext; hardware untested |
| knight_tyme_sprites_loading.nex | 55275fe76b3effccc525b0cecec3841b | tape's loading screen added; real loader MD5 exact, default and cheats 1+2 (jn/ld3, ld4); out/knight_tyme.nxc. Previous, before the crew: c9a5cd19, out/knight_tyme.prev.nxc |
Lockstep (work/final.log), all IDENTICAL, 33,534 frames: kt_t1 3,346, kt_rooms 6,720 (48 rooms, 49 graphics), kt_over 882 (game over, new game), kt_cmds 22,586 (750 windows, 141 room builds). Counts per hook: Knight commits 11,285; characters 166; objects 465; room builds 200; windows 831; wipes 3; crew overlays 5 (kt_t1 4, kt_rooms 1; every Bridge build). 3,625 stable frames: sprite layer and ULA against the model, 512 of them with the crew; 25,064 hook exits with registers checked. Run on 473cdb2. Unit: 42 figure cases, pool full, window pictures. Negatives 18/18 (work/neg.log): 15 on kt_cmds 1,500 frames, the 3 crew negatives (tiles not loaded, one pixel right, skin in the wrong colour) on kt_t1 1,500 frames, which builds the Bridge twice by then. kt_cmds never builds the Bridge, so the crew negative first run there was not detected (work/neg.prev.log, 15/16): a crew negative whose run builds no Bridge now reports NOT EXERCISED. The RAM-write control stores HL.
Not replayed: option UPDATE (flag held at 0 on the patched machine, work/upd.py; not viewed in JNext).
Colours: sheets in sheets/, recolour run on a test painting (paint/); an empty map returns the build byte for byte.
Cheats: archive .pok's [128K] entries; time and others' stats held in the simulator on the original code; strength, fuel not run. The file's other entries are 48K addresses (they land inside instructions here): left out.

## Lessons
- [local: the pilot added the loading screen after the build with its own script] Rebuilding the approved .nex
  needs the post-step in the engine: stub source in the .asm, the screen from the tape beside the snapshot.
- [deferred Open: reconsider when the ROM path check can replay recordings made on the 48K ROM as ROM 1] The record pins
  `rom_paths: skipped`; the engine's lockstep runs ROM 1 from the image the Next holds instead.
- [local: a composite whose clean copy is captured after figures are plotted needs the plots undone before the capture] Run plot, restore cells: all registers equal for free, no second path.
- [local: count hook instructions out and the original and patched machines stay in lockstep] Whole 128K compared per frame, with no per-site pairing; every hook counted as nothing. Works only where game instructions stay the same.
- [local: the 128K ROM 1 in SkoolKit is not the Next's] 128-1.rom has keypad code at 0x386E on the ISR path; a stub there broke replay. Record on the 48K ROM for this kind of engine.
- [local: a negative needs a check of its own] Blit from the composed box passed every model at first: screen + sprites still matched. Added: under each box the ULA equals the room's clean copy.
- [local: tile-level window hide cuts figures beside a window] Store the figure's real extent per tile.

## Technique use
- detect.gameplay-screen-readers: no help: the lockstep shows it directly, no memory outside the listed buffers ever differs
- optimise.pattern-cache: used: Knight images only

## Hardware checklist
1. Loading screen shows, a key or 5 s, menu; Z down, SPACE; PLAY GAME.
2. Knight, droid: no clash on machines; white ring on coloured figures.
3. SPACE: window, hand pointer, text; figures under it gone, back after.
4. Bridge stars: pattern differs from a 128K (they come from ROM 0).
5. Music plays; a room change doesn't stutter it (a hook can miss one interrupt).
6. Game over, new game: no stale sprites.

## Stage log
- 2026-11-03 stages 0-3 in one session (pilot, unattended); 0 user rounds.
- 2026-11-04 import into nexclash (phase 7, group 2): loading screen in the engine, record, stamped verify; 0 user rounds.

## Open
- Hardware, CSpect: never run.
- Alt image 0 is the set-up's copy of the Next's ROM 0, so the Bridge's star map reads NextZXOS's ROM 0 (REFACTOR item 2):
  opt-in rework `altrom0`, not this build. Puzzles, transporter trips and the ending not played: rooms by poke.

## Whole alt ROM image (2026-11-04, pilot/runs/altrom_audit/AUDIT.md and FIXES.md)
The build now writes all of alt ROM image 1: altrom = (0x2000, 0x4000) from a page of Sinclair's 0x2000-0x3FFF plus the
hooks, and altrom_low = Sinclair's 0x0000-0x1FFF in page 25 (bank 12's upper half, unused before). Before, only the hook
bytes were copied over the stub's first fill, which is NextZXOS's ROM3, not Sinclair's: its IM 1 handler CALLs 0x386E and
its UDG print JPs to 0x387E, both into the hooks, masked only by NextZXOS's DivMMC trap at 0x0038. The verifier now models
the image as the Next fills it (ROM3 from work/.../enNextZX.rom, MD5 8c34d957, then the build's writes); hook_range keeps
the hook bytes for "hook instructions"; rom3_left() rebuilds the previous build byte for byte and is the new negative.
The .nex differs from the previous one only in bank 10's stub (the fill, 15 bytes longer, the code after it shifted) and
bank 12 (the image's page bytes). Emulator only.

## Import (2026-11-04, refactor phase 7: ported from Jon Attree's .nxc work)
- From runs/knight_tyme/nexclash (clone of d7abd1c, 222cf2f..6a1958c): nexclash/knight_tyme.py, asm/knight_tyme_hooks.asm,
  docs/profiles/knight_tyme.json, this file; the clone's record rewritten (inputs, verify recipe, pin, outputs). The
  clone changed no shared code.
- Ported: rom3() now comes from nextboot.system_rom3 (NEXCLASH_NEXT_ROM / --next-rom; the pilot read
  work/rom/enNextZX.rom, the same file, md5 8c34d957). alt_image stays the engine's own: nextboot.alt_image puts
  Sinclair's ROM under a partial image (the new default fill), which would make the previous-build negative equal the
  good build; for this build both give the same image. Without the Next ROM the previous-build negative is not run
  (said in the report). load_colours also reads coloursheet.save's form (selftest's empty map: the recolour guard,
  which the pilot never ran).
- Loading screen: the pilot added it after the build (work/mkload.py, stub in loading/work/stub.asm, bank 22). The stub
  is MODULE ldscr in the .asm (blocks lstub, lfinal, byte-equal to the pilot's stub.bin); add_loading writes the file
  as mkload.py did, from the tape beside the snapshot (.tap / .tzx / .scr, screen md5 82f0e3df); loading_check runs
  the stub on a model. The boot check runs on the base .nex (nextboot.boot ignores the entry bank).
- New defaults: the build already writes its whole alt ROM image (altrom 0x2000-0x4000 + altrom_low, so
  z80tonex.altrom_whole is False and the output is unchanged); alt image 0 is the old ROM 0 copy (Open). The record
  pins `rom_paths: skipped`: the shared ROM path check replays the recordings on SkoolKit's 128K ROMs, these were
  recorded on Sinclair's 48K ROM as ROM 1 (Inputs), so it desyncs at frame 1 and its SkoolKitError ends `auto`.
- How it runs in today's tree: rebuild `python nexclash.py auto --no-nxc knight_tyme.z80 --no-record -o OUT` (the
  .tzx beside it); verify `NEXCLASH_MAINTAINER=1 NEXCLASH_REFERENCE=<specnext/reference> NEXCLASH_NEXT_ROM=<enNextZX.rom>
  python selftest.py --game knight_tyme --verify --stamp`: kt_t1 in the main process (unit-test states), the other
  recordings and the 19 negatives in worker processes, about 12 min.
- Results (2026-11-04, this tree, stamped): published v1.1 .nxc (23485e65) --bare = 645401e4 = the rebuild (base
  ed735a24, plain 0f91cab9). Lockstep IDENTICAL: kt_t1 3,346 frames (commits 2,836, crew overlays 4), kt_rooms 6,720
  (48 room builds), kt_over 882, kt_cmds 22,586 (750 windows); unit PASS (42 figure cases, pool full, window pictures);
  negatives 19/19 DETECTED (crew ones on kt_t1); recolour guard OK; boot OK; loading stub OK.

## Friction
- reuse: [local: rebuild and boot model are today's shared code; rom3 from nextboot.system_rom3; the loading wrapper is new, in the engine]
- retries: [local: the first verify failed the recolour guard (map form) and the previous-build negative (nextboot.alt_image); both fixed in the engine]
- environment: [local: needs NEXCLASH_NEXT_ROM=runs/altrom_audit/rom/enNextZX.rom; killing a selftest leaves its worker processes: kill them by PID]
- hand-rolled: [local: TZX block reader for the loading screen, in the engine]
- scratch: [none: no scratch scripts kept]
