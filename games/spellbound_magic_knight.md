# Spellbound (Mastertronic Added Dimension, 128K edition) - engine `spellbound_magic_knight` (unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into nexclash 2026-11-04 as spellbound_magic_knight (ported from Jon
Attree's .nxc work, 2026-11-04; spellbound_dizzy is another game); JNext only, never on a Next or in CSpect.
Inputs: specnext/reference/spellbound_magic_knight/ (spellbound_magic_knight.z80 = the pilot's rzx/s0.z80, md5 3bca7e72;
t*.rzx; the archive file 929d9e7f the .nxc applies to). Pilot run folder: runs/spellbound.
Published .nxc: Spellbound v1.1 (nexclash-patch patches/, e1fefc34): --bare default 379e61b0, Enhanced 3a824f3a.
Start with: hardware checklist. Open: everything under "Open".

## Snapshot and start
Archive "Spellbound (1985)(Mastertronic Added Dimension)(128K)[Magic Knight 2].z80", 929d9e7ffaeeb9a88a3e03e32cfe9aef. ZXDB filecheck: 502, once.
It is the 128K edition. In play, on the original: 7FFD 0x10, 0x13, 0x14, 0x16, 0x17, 0x07; 532 AY data writes in 500 frames (music from the ISR); banks 1, 3, 4, 6 hold data; the banner says SPELLBOUND 128K; rooms 0-56 are real, 57 rooms, the owner's lead; room 57 up is garbage. Title in game: copyright 1986.
The file stops in PAUSE 0 in 128 BASIC, the tape's picture on screen, before RANDOMIZE USR 26627. Stepped with a key held to PC 0x6803: rzx/s0.z80, 41 bytes of bank 5 differ (system variables, BASIC's stack). The .nex starts there; 128 BASIC never runs on NextZXOS's ROMs. Game file for the patch: the archive's file; the 41 bytes go in the patch.
Tape block 6,940 bytes at 50000: the first 6,912 equal the file's screen (work/scr.py, md5 13715aac): the loading picture is bank 5 as it stands. The set-up holds it until a key or 250 frames and waits for the key to go. Plain build: no hold.
Keys: menu Z down, SPACE select, sixth line PLAY GAME. Play: N left, M right, SPACE commands; in a window Z down (one line each 4 frames held), SPACE select.

## Rendering model
The same engine as Knight Tyme (same author; byte patterns found the routines; every site read here). Knight: masked composed box, 3 x 32 lines: 0xA4FF clean bytes from bank 7, 0xA569 masks in graphics 0xF9F4 + image*96, mask 0xFCF4 + image*96; 0xA629 HALT; 0xA630 blit the old clean box; 0xA63B CALL 0xA59F blit the new. Position 25718-25722, X 25354, line 25355, shift 25357, facing 25723, colour 25360.
Characters: 0x72CF -> 0x72E9 CALL 0xAD19 (2 x 4 cells, colour in the self-modified 0x7303). Objects: 0x94B8 -> 0x94E4 CALL 0xAD14 (2 x 2, colour 23695). Both in the room build, before 0x6AA8 copies the screen to bank 7. A window's picture: 0x94AD (IX = 25594), 0x7CE2, 0x7CEC, 0x8E03, 0x912E: left on the ULA, inside their windows.
Differences from Knight Tyme, each found by reading:
- Option UPDATE (23705) is ON from the start (0x6806). The Knight paints the cells he is in (0xA654, saved at 0x5DE5, put back by 0xA6B1); objects (0x9502-0x9517) and characters (0x7307, 0x7309) paint theirs. This is the game's clash here.
- Balls: 0xAB3B, an 8 x 8 XOR plot, three call sites, rooms 12, 19, 37, 50, 51 (0x8F06; four balls, one in rooms 19 and 50). Over the Knight in the original. Characters 116-119, table 36582.
- Smoke: 0x7312, five frames of 2 x 3 cells at 0x732D (graphics 94-98), twelve HALTs each, cells put back by 0x77F0, when a character arrives or the Knight teleports.
- 0x7282 / 0x718B: a character arriving in the room is plotted in play, then all are plotted again, then the clean copy is taken again. No figure moves in a room otherwise; each change rebuilds the room.

## Clash numbers (work/clash_check.py, t_rooms, 10,439 Knight draw passes over 57 rooms)
Option UPDATE (default): 7.1 % of 125,268 cells under the Knight repainted in his colour: scenery takes his. Option IGNORE (poked): 12.9 % of passes span several attributes, 3.7 % of 2,280,590 ink pixels show a colour not his. Kind A. Rooms are mostly black, so numbers are lower than Cobra's; the owner's eye says clash; png/spellbound_final.png row 2 shows the stonework turned cyan. Fixed.
Menu options read: GAME OPTIONS holds the option above. .256: none in Spec256-256-all38 for this game (Knight Lore's is another game): no Enhanced set.

## Design
Game code runs the same instructions in the same order. Plots run, cells put back; attribute stores and the ball's two stores are NOPs, one instruction for one, so either option behaves the same and the verifier stays in step. Blit from the clean box (data patch 0xA5A0). Hook code in alt ROM 0x386E- and page 26 at slot 4, interrupts off in hooks only.
Sprites 16 x 16, 4-bit. Knight: 8 images x 6 tiles, patterns 0-47, slots 122-127 on top. Room figures: patterns 48-123, slots 0-117, in plot order; past the pool tiles drop, counted. Balls: slots 118-121, patterns 124-127, a sprite per call where the call says; erasing calls name the place it already is. Smoke: tiles from the room pool, last frame's taken back, gone at 0x733C.
Colours: fixed, the game's own table: Knight 25360, characters 0x7303, objects 23695. Mask = solid silhouette, knocked-out paper black (the fill). Outline: one pixel, white; for a white figure black round ink only.

## Defaults taken (a human would have decided)
1. Objects, characters, smoke, balls count as figures. 2. Hand pointer, window pictures, text, icons stay ULA. 3. Depth: objects, characters, smoke, balls, Knight on top (the original's balls XOR over him). 4. Balls bright cyan with a white outline, the colour they show on black; about 50 opaque pixels, so outlined. 5. Smoke bright white with a black outline; the game gives it the cell's colour. 6. Option UPDATE no longer differs. 7. Scenery that looks like a figure (mirror frame excepted, an object; stag heads, plants, paintings) is scenery, as the game draws it.

## Enhanced set, second version (2026-11-03 evening), after the owner's play
Owner: "Thor looks like a devil and only half red"; the Knight wears armour, so grey/silver; every figure by its parts.
- Names, read from the game, not from name order: character record n at 25290 + 8n holds the attribute (byte 4) and graphic (byte 5); name n is token 0x82 + n (GIMBAL, THOR, FLORIN, ORIK, SAMSUN, ELRAND, ROSMAR, BANSHEE). EXAMINE in play confirms it room by room (sim frames: rooms 48 Gimbal, 23 Thor, 20 Florin, 32 Orik, 28 Samsun, 25 Elrand, 5 Rosmar). So 69 Gimbal, 71 Thor, 70 Florin the dwarf, 73 Orik, 76 Samsun, 75 Elrand, 74 Rosmar, 72 the Banshee. The figure seen as a devil, graphic 70 in room 20, is Florin, whose winged helmet reads as horns.
- Painting (work/enh2/paint2.py): each figure by its own ink parts, the 4-connected ink areas its black lines separate, split by rows or columns where one part carries two things. Black lines, knocked-out paper and see-through pixels as in the default build, so the silhouette and outline are unchanged. Knight: light grey armour, white on lit edges, dark grey on shadowed edges, every image. Gimbal: green hat with a gold band, skin face, white hair and beard, green robe. Florin: grey helmet, white wings, skin face and hands, brown hair and beard, red tunic, grey legs, brown boots. Thor: grey helmet, red hair and beard, white eye, skin nose and hand, blue tunic, brown legs. Banshee: magenta shroud, red eyes. Orik: white hood, skin face, yellow robe, grey sandals. Rosmar: fair hair, skin face and legs, magenta dress, red shoes. Elrand: gold circlet, brown hair, skin face and hands, green tunic, brown boots. Samsun: skin head, arms and chest, red breeches, brown boots. Where the game draws a face as black (Thor, Samsun, the Banshee) it stays black.
- Palette: a colour map may carry its own sprite palette, key 'palette', 16 bytes RRRGGGBB as NextReg 0x41 takes them; the setup loads it in place of PALETTE (bank 10, after the setup code). Only entries 1-5 may change (PAL_FREE): no object in the game's 50-entry table (39459 + 8n) has a dim ink but 6 and 7, smoke is 15, balls 13, outlines 8 and 15. Enhanced: 1 dark grey 0x6D, 2 skin 0xF5, 3 dim magenta, 4 dim green, 5 brown 0x88; 7 (dim white, 0xB6) is the light grey. Checked three ways: SpellboundPatch refuses a palette changing another entry; boot_check reads the 16 NextReg 0x41 writes after 0x43 = 0x20, 0x40 = 0 and compares them with the map's; verify fails a figure that shows its own ink in a changed entry ("palette ink checks"). recolour() writes the palette into bank 10 too. The default build has no 'palette' key and is byte-for-byte as before (0aa4ea40).
- Set size: SET2 has no limit of its own; a bank's chunk is at most 18,432 bytes. The 24,576-byte figure is the site table (SITE_TABLE_MAX), not sets.
- Gimbal (69) and the Banshee (72) are never plotted on any recording (the Banshee is in no room at the start, Gimbal not on screen in room 48): their colours are checked by the model and the hook code (outline census with the map, layer equal to the model), not in replay.

## Open
Hardware, CSpect. Speed on a board. Puzzles, spells that succeed, the ending, characters taking orders: not played. Two plots of an arriving character use the pool twice (duplicates, harmless, pool not filled on any recording).

## Lessons
- [backlog C2 #45] The pilot changed the shared boot model for its picture hold. A shared-code change of a pilot clone goes into the
  engine on import: _boot here is nextboot.boot plus the raster line model, used only by this engine's boot check.
- [tool nextboot.rom_paths] The ROM path check runs on this build now (2026-11-04): nextboot.boot's raster counter
  ends the picture hold; t_balls / t_chars / t_rooms (2 / 7 / 57 snapshots) replay per segment (stripped, they
  desynced at frames 227 / 168 / 315); the 128K ROM 1's keypad code is listed, not compared. Demonstrated: 9 of 9 in
  sync, 39,222 frames, no MISMATCH. Pin removed; `auto` runs it.
- [local: a store can be a NOP] Replacing one store with NOP keeps instruction counts and the lockstep; a watch at the site still checks the store's would-be effect.
- [local: an XOR plot needs no state] Follow every call with the sprite: an erase names the place it is already.
- [local: read the sister engine's options again] Knight Tyme's option is off by default, Spellbound's on; the same flag.
- [local: negatives by colour] "Characters paint" went undetected where the character's colour equals the room's; a recording with another colour detects it.

## Technique use
- detect.gameplay-screen-readers: no help: replaced by the lockstep, which compares the whole machine each frame
- optimise.pattern-cache: used: Knight images only

## Results
| Output | MD5 | Status |
|---|---|---|
| out/spellbound.nex (plain) | 656c71c4b2ebb8318f3ad442d70b0ab9 | boot sim OK, reaches play in JNext |
| out/spellbound_sprites.nex | 7bfce53ad408141c0321ea9fcf4a1967 | boot sim OK, replay IDENTICAL, reaches play in JNext and through the real loader; hardware untested |
| out/spellbound.nxc | 474807b17e7b7d9cd3e15e9ffef34c6d | apply byte-exact; through the loader MD5 exact: default, cheats 1+2+3 (83fcfc2b) |
Replay (work/vfinal/): t1, t2, t3, t4, t_over, t_walk, t_rooms, t_chars, t_balls: 39,222 frames, no failure. Unit: 42 figure cases, pool full 124 tiles dropped, patterns capped at 124, window pictures on the ULA: PASS.
Hooks, summed: commits 28,438 (Knight), plots object 67, character 20, smoke 35, smoke ends 35, ball plots 18,626, room builds 111, wipes 6, windows 216. NOP stores ran: A68A/A696/A6A2 113,726 each, 9502 32, 9508 36, 9511 60, 9517 68, 7307/7309 80 each, AB5E/AB63 149,008 each. None never ran. 4,986,828 sprite pixels compared. Most sprites 20, patterns 62. ULA census, every recording: 0 bytes differ from the room's clean copy at the checks.
Negatives (work/neg0-2.log, neg_ch.log): 21 of 21 DETECTED; "characters paint" not on t1 or t_balls, where colours match, but on t_chars.
Sound: JNext WAV plain peak 3584, sprites 3584; not compared by ear.
Speed: hook T 750,593,995 at 28 MHz over 39,222 frames, about 19K of 560K per frame, about 3.4 %. Not measured on a board.
Cheats (spellbound_128.pok, from the archive's (128K) .pok, values unchanged, names shortened): only entries whose bytes match this code; the file's "Infinite Energy", "dark rooms", "gas room", "lift" and its [48K] entries land on text or the middle of other code here and are left out. Simulator on the original: strength held at 70 against 66; time held at 48 against 45. Spell power and the four "their" cheats: effect not measured. Through the loader with 1+2+3, reaching play. Unplayed by a person.

### Results, Enhanced second version (2026-11-03 evening)
| Output | MD5 | Status |
|---|---|---|
| out/spellbound_sprites.nex (default) | 0aa4ea40a7d848b55257a90056d73c37 | unchanged, rebuilt byte for byte after the engine change |
| out/spellbound_enhanced.nex | 76b03bc6f691b7d4d5ebf2a93080f2d4 | boot sim OK with the palette check; recolour route gives the same file |
| out/spellbound.nxc | f9204e9ee74220ebf8cf4040bfd1055f | apply byte-exact: default 0aa4ea40, Enhanced 76b03bc6, cheats 1+2+3 + Enhanced 5b410903; the real loader gives the same three |
| out/spellbound.prev.nxc | 6dec9cb8ee3ccd397b3db5163de32d86 | the first Enhanced, as the owner played it |
Enhanced replay (work/vfinal3/): all 9 recordings, 39,222 frames, no failure; commits 28,438, object plots 67, character plots 20, smoke 35, ball plots 18,626, room builds 111, windows 216, palette ink checks 28,560, every NOP store ran. Negatives: 22 of 22 again after the change (work/vfinal3/neg0-2.log), palette 7 of 7 (work/vfinal3/neg_palette.log). Outline census with the map: 117 figure frames, 4,070 pixels, 0 missing, layer equal to the model for every room figure. Unit tests pass. Hook T +1.5 % over default. JNext: the three .nex reach play; Enhanced frames in rooms 5, 20, 23, 25, 28, 32 beside the old set in out/spellbound_fix.png.

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
- Name: spellbound_magic_knight (module, record, profile, .asm, this file); spellbound_dizzy is another game. The pilot's
  clone (runs/spellbound/nexclash, d7abd1c + 4e0793b..abea59b) called it spellbound. RECORD, the colour map paths and
  the detector (is_spellbound_magic_knight) renamed; the hook bytes are unchanged (asm2profile --check IDENTICAL).
- Shared code the clone changed: nextboot.boot's raster line (3 lines, for the set-up's picture hold). Not carried into
  nextboot: the engine has _boot, today's nextboot.boot with that model, for its own boot check only.
- Ported as in Knight Tyme: rom3() from nextboot.system_rom3 (NEXCLASH_NEXT_ROM); its own alt_image kept (the previous-
  build negative needs the ROM3 fill); load_colours reads coloursheet's form (recolour guard).
- Enhanced: the pilot's work/enh.json (5e0237a9) is docs/profiles/spellbound_magic_knight_enhanced.json, a data file of
  the record; auto builds spellbound_magic_knight_enhanced.nex from it. The pilot's v1.py / v2.py / neg.py /
  enh2/neg_palette.py / ut.py are now auto: both sets on every recording, the 23 negatives (t1 1400 frames, then
  t_balls, then t_chars), the 7 palette negatives, unit tests on t1's first 500 frames.
- New defaults: whole alt ROM image already written by the build (altrom 0x2000-0x4000 + altrom_low); record pin
  `rom_paths: skipped` until the fix below. Output as approved. Evidence then (2026-11-04, NextZXOS ROM modelled):
  `nextboot.rom_paths([spellbound_magic_knight_sprites.nex], [t1.rzx], z80=...)`: rom_paths (line 160) -> boot (line
  351) `RuntimeError: boot did not reach PC 26627 (at 53426)` (the set-up's line wait; no frame of t1.rzx is replayed).
  The plain .nex (no hold) replays t1.rzx through it to frame 2109, so these recordings replay; only the boot fails.
- How it runs in today's tree: rebuild `python nexclash.py auto --no-nxc spellbound_magic_knight.z80 --no-record -o
  OUT`; verify `NEXCLASH_MAINTAINER=1 NEXCLASH_REFERENCE=<specnext/reference> NEXCLASH_NEXT_ROM=<enNextZX.rom> python
  selftest.py --game spellbound_magic_knight --verify --stamp` (18 locksteps and the negatives in worker processes).
- Results (2026-11-04, this tree, stamped): published v1.1 .nxc (e1fefc34) --bare = default 379e61b0, Enhanced 3a824f3a
  = the rebuild (plain 656c71c4). Lockstep IDENTICAL, default and Enhanced, all nine recordings, 39,222 frames
  (commits 28,438); unit PASS; negatives 23/23, palette 7/7 DETECTED; recolour guard OK; boot OK with the palette check.

- ROM path check (2026-11-04, refactor-romcheck; pin removed): `nextboot.rom_paths` on plain 656c71c4, default
  379e61b0, Enhanced 3a824f3a, NextZXOS ROM modelled: all nine recordings in sync, 39,222 frames; default and Enhanced
  every byte the game runs as recorded (the keypad code at 0x386E- listed, 62 bytes); plain: NextZXOS's IM 1 bytes
  0x004B-C differ (reported only); tail never read before written. Rebuild MD5s unchanged. `selftest.py --game
  spellbound_magic_knight --verify` (not stamped) PASSED with the check inside auto (226 s).

## Hardware checklist
1. The tape's picture held until a key or 5 s, then the menu; Z down, SPACE; PLAY GAME.
2. Knight, characters, objects, smoke and balls as sprites with their outline; scenery keeps its colours (no repaint).
3. SPACE: window, hand pointer, text; figures under it gone, back after.
4. Enhanced (menu): the Knight in grey armour, every character by its parts.
5. Music plays; a room change doesn't stutter it.

## Stage log
- 2026-11-03 stages 0-3 (pilot, unattended); Enhanced second version the same evening.
- 2026-11-04 import into nexclash (phase 7, group 2): renamed, record, stamped verify; 0 user rounds.
- 2026-11-04 ROM path check fixed for this game (raster line, segments); record unpinned; 0 user rounds.

## Friction
- reuse: [local: rebuild and boot model are today's shared code; the raster line model is the engine's copy of the boot]
- retries: [local: the first verify failed the recolour guard (map form); fixed in the engine before the stamped run]
- environment: [local: needs NEXCLASH_NEXT_ROM=runs/altrom_audit/rom/enNextZX.rom]
- hand-rolled: [local: _boot is a copy of the shared boot with three lines more, kept in the engine by the import rule]
- scratch: [none: no scratch scripts kept]
