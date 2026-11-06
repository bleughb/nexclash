# Rambo - First Blood Part II (Ocean, 1985, 48K) - engine `rambo` (batch game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: imported into `refactor` 2026-11-04 (phase 7); stages 0-3 done unattended
in Jon's run folder; never run on a Next or in CSpect; JNext only.
Inputs: specnext/reference/rambo/ (rambo.z80 md5 3eb7a65e, play1 / north1 / mix2 .rzx by script, rambo_loading.scr)
Start with: the hardware checklist below; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04: the batch run's clone (pilot runs/rambo/nexclash, d6d820b..11a5c51
on d7abd1c) brought onto `refactor` 884d31a. Published .nxc: **Rambo v1.0** (github.com/jattree/nxc, patch md5
33e91835; Jon Attree; credit Dean Woodyatt / NexClash). `nxc.py --bare` of it gives default 9ebfe9c8 and Enhanced
c2395f02: `auto` builds both byte for byte (rambo_sprites.nex, rambo_enhanced.nex; plain 434a8477).
- Moved in as it was: nexclash/rambo.py, asm/rambo_hooks.asm, docs/profiles/rambo.json, the record. No shared code
  changed. New defaults: rambo has no alt ROM hooks (stubs in RAM, page 26 at slot 1) and its start-up tail passes
  today's check, so the record has no pin.
- Moved into the engine from the run folder, where they ran after `auto`: the Enhanced build (work/final2.py:
  `build_enhanced`) and the loading screen (loading/mk.py + loading/stub.asm v2: `loading_nex` and the `ldscr`
  blocks ld_head / ld_tail of asm/rambo_hooks.asm). The pinned sjasmplus 1.24.0 assembles them to the bytes of the
  run's stub.bin (1.23.1). The screen is game data (the archive [a][a].tap's 6,912-byte block, md5 f045fa38): never
  in this repo; specnext/reference/rambo/rambo_loading.scr, listed with the record's inputs so selftest stages it
  beside the snapshot. Without it `auto` says so and writes both builds without the screen (f6e64fc9 / 071f11c9).
- verify now runs the Enhanced build on every recording as well (it ran in work/blackink.py before).

Techniques: `detect.buffer-layout-producer`, `detect.gameplay-screen-readers`

## Inputs
Snapshot: archive "Rambo - First Blood Part II (1985)(Ocean).z80", md5 3eb7a65e19c9ffa82a49654d31a41886. 48K, one load. ZXDB lookup: 502, tried once, so "listed in ZXDB" is not established.
Stopped at PC 0xFFFF, IM 2, I = 0x39: the vector is 0x39FF/0x3A00 = FF FF in the ROM, then 0xFFFF = JR with its offset from ROM 0x0000 (0xF3), to 0xFFF4. `inspect` warns "handler in ROM": BRIEFING C2 #35, a false alarm here.
Keys: any key leaves the title; S start, ENTER takes the name, any key starts the life; I left, P right, Q up, Z down, N fire, A weapon. Menu: P players, L skill, C controls.
Recordings (no Fuse, scripted): play1 random keys, no cheat, game over and menus. north1, mix2: the archive .pok's infinite lives + immunity (27401, 27402, 30263, 38841) in the RZX snapshot, random walks mostly north. heli (work/heli.py): a recorded state with 0x73A4 = 6 and a scenery object of type 0x2E moved onto Rambo, so the game's own 0x9618 builds its helicopter; hand-made, not a state a player reaches this way.

## Clash check (owner's list: judged by eye, clash; measured anyway, cheap)
No menu option changes the drawing (P, L, C only). Kind A. Each object paints one attribute box over its whole size, and the last one wins: Rambo crossing the river paints a yellow block in it, and a soldier beside a bush turns it. north1, every 4th blit: 11.3 % of figure pixels (40,866 of 362,650) show in another colour in the original, 164,296 scenery pixels recoloured by figure boxes.

## Rendering model: back-buffer composer with a display list; scrolling is not a problem
Black paper, all scenery is objects: the world scrolls by moving objects, so no pixel scroll exists to fight.
Records of 10 bytes down from (0xFF2D), count 0xFF2C: flags (7 y signed, 6 x signed, low bits a frame), type, x, y, y high, 3 more, descriptor pointer.
Descriptor, 12 bytes: first, last, 2 more pointers, height, width, rotation, size. 130 of them, found by shape. Rows stored bottom up; y counts up from the bottom.
0x83D1 walks the list once a game frame (about 3 TV frames): type -> attribute at 0x87AF, box onto the list at 0xFE00 (count 0xFF4F), then plot: types >= 0x42 rotate the graphic in place to x & 7 (0x800F / 0x8633), then OR into the 20 x 192 linear buffer at 0xC000 (0x8052 whole, 0x8670 clipped). 0x8093 paints the boxes, EI, waits for the interrupt plus a count (the IN or OUT at 0x8119 is the sound), DI, 0x814A blits with LDI.
Readers: the buffer only by the plots, the blit and the menus' wipes; no collision reads it (they use coordinates). The ISR is 5 instructions at 0xFFF4; interrupts are off at every plot and blit (verify counts it).
ROM: the game's random numbers read ROM 0x0000-0x1FFF (0x74A4) and a fade reads 0x0000-0x6BFF as masks, so the alt ROM route is out: stubs in RAM 0x5D80-, hooks in Next page 26 at slot 1 during a hook only.

## Patch plan
detect.buffer-layout-producer and detect.gameplay-screen-readers: answered by the disassembly and `scan --writers`. No card covers a display-list split; design from table 4 "back-buffer composer".
| Site | Original | Hook |
|---|---|---|
| 0x8052 | LD A,(IX+9) | type >= 0x40: a sprite from tiles, no plot, its box off the list; else the original |
| 0x8670 | LD A,B / LD (0x8698),A | the same, clipped path |
| 0x813E | LD HL,0xC000 | commit: attributes in one burst, spare slots hidden, other pattern set next |
| 0x8093 | LD A,(0xFF4F) | an empty list now possible: skip the painter (DJNZ would run 256 times) |
| 0x6C8F, 0x7600, 0x74B3 | clear / wipes | NEXTREG 0x15 and 0x69 off; the next commit turns them on |
| 0x8EB4 | LD IX,0x79AE | a life starts: commit, so the portraits show during the tune; Layer 2 stays off, the play area is black ink on black then |

## Build design
Sprites: 16 x 16, 4-bit tiles, empty tiles left out, made at build time from the unrotated graphics, all 130 descriptors, in banks 14-; 64 patterns a frame, two sets. A figure's X adds its rotation, so no re-rotation at run time. Colour: palette offset = the game's type colour, pattern nibble 15 = that colour, 1-14 fixed paint colours. Clip window 160 x 192, so the panel and edges stay the game's.
A descriptor outside the table, or no pattern left, runs the original plot: counted ("fallback"), zero in every recording. The table is 136 descriptors: 130 by shape, and the six helicopter parts at 0xDAA4-0xDAE0 whose size byte is not h x w. Without those six the helicopter stayed on the ULA, in no recording then.

## The owner's changes (from play, 2026-11-03)
Outline: people and helicopter bodies get a black outline, enclosed gaps black, in nibbles the picture check treats as not ink (0, 5, 8, 14). Dust, shadows, rotors, explosions and shots have none.
Portraits: the 0x7634 XOR plot still draws them on the screen; four opaque 16 x 16 tiles in patterns 60-63, slots 120-127, cover each place, shown if a row through its middle on the screen is non-zero, read at every commit. verify compares each against the original's screen at every blit and life start. Green frame and face no longer share cells.
Enhanced (off by default; the same layout, 35 bytes differ: palette, a flag in the stub bank, 2 in the hook page): sprite palette blocks by the game's colour give Rambo skin, red headband, olive trousers, soldiers helmet, skin, uniform. Rows and sides by hand in `_band` and `image_pixels`, one rule per facing, shading on lower right edges. Facing comes from replaying each direction key (work/dirprobe.py): the first attempt had front and back swapped. Dirt: `dirt_tile()`, a fixed-seed generator, 160 x 64, four 9-bit browns, in Layer 2 banks 20-22; ULA paper black (16, 24) becomes E3; layer order S U L. Black ink stays solid: no blit in any recording has black ink pixels in the play area (work/blackink.py). The panel is black in Layer 2 and the portraits keep their white face and green frame in both sets, so the panel is the same in both: JNext frames compared, no pixel differs.
The dirt is pinned to the scenery (owner's ask, 2026-11-03: he saw it move at a different pace). The game moves every object by the steps it copied at the top of the frame, and adds the same steps to 0xFF2F (y, 2 rows) and 0xFF33 (x, 8 pixels) at the end of that frame's logic, so those lead the objects by one game frame: each commit uses the values of the commit before, and a change larger than a step (a new life) takes effect at once. x scrolls too, over a 256 x 64 tile that wraps both ways, Layer 2 clipped to the 160-pixel play area. Timing: the commit runs about 60 lines into a frame and the blit finishes early in the next, ahead of the beam (T-states from the interrupt measured on north1, work/blittime.py), so the new picture first shows from the next frame's top line. The commit arms the copper (WAIT line 0, MOVE 0x16, MOVE 0x17, HALT, run once), which changes the scroll there. A first try (a dead session's) set it with a stub at the blit's end, 0x8176: that is still 34 lines into the next frame, and its stub RAM ran past 0x5E60, which the game writes after a game over, so play1 broke at the hide stubs. The copper needs no RAM; the stub area is again byte-identical to da0501c. The stub sets NR 0x12-0x14, 0x16-0x18, 0x1C, 0x70, 0x71, the Layer 2 palette, since .nexload and the menu leave what they leave.
Loading screen: from the archive's tape ([a][a].tap, 6,912-byte block, three releases hash alike), loading/mk.py: bank 5's screen area holds it in the file, new bank 23 is the entry bank with bank 5's own bytes and the stub of runs/altered_beast v2, 250 frames or a key.

## Verify (what it checks)
The real patched game on a Python simulator beside the original (C simulator, RZX): the original's IN values fed in order, except 0x8119, whose result is discarded and whose count depends on the wait. Frames by the recording's fetch counts, hooks not counted, resynchronised at every event, because the music's IN order depends on the interrupt's place.
At every blit: all RAM but the screen, buffer, attribute list, its count, patch and dead stack; live registers (BC, IX, IY, SP, I, IM, IFF, BC', DE', HL'; AF, DE, HL, AF' are dead there); the patched list is the original's minus the figures; original buffer = patched buffer | sprite pixels, bit for bit; sprite colours are figure colours. At hide sites: sprites off. Also: no figure reaches the ULA plot, no jump into a patched instruction, ROM unwritten, interrupts off at hooks.
Unit: every descriptor through the game's own 0x83D1 at edge positions. Negatives: broken builds on the real recording.

## Defaults taken (a human would have decided)
1. Every object of type >= 0x40 a sprite: Rambo, soldiers, shots, arrows, explosions, helicopters. Type < 0x40 stays on the ULA, including 0x3E, a small blue object that may move. 2. Scenery, text on the ULA; the portraits are sprites. 3. Depth: sprites over all scenery, plot order among them; the game has no depth, only OR. 4. Colours: the game's own by type by default. 5. Explosions white as the game's table says, and they no longer tint the river.

## Hard limits
Scenery still clashes with scenery (a rock in a bush), as the original. Left-clipped figures draw at rotation 7 as the original does, a small jump at the left edge.

## Results in today's tree (`selftest.py --game rambo --verify --stamp`, 2026-11-04, after the import)
Rebuild = recorded: plain 434a8477, rambo_sprites.nex 9ebfe9c8, rambo_enhanced.nex c2395f02 (= the .nxc v1.0's
default and Enhanced); recolour guard OK; hook profile = pinned sjasmplus. Verify: play1 20,245 frames / 1,638 blits,
north1 15,025 / 4,315, mix2 20,011 / 5,735: default and Enhanced each IDENTICAL, fallback 0; unit 1,224 cases PASS;
negatives 17/17 detected. Stamped verified 2026-11-04. Before the pin the same run failed only on the new ROM path /
start-up tail check (record pin note): play1's end-of-game fade, 0x6CA9, frame 6094, reads 78 tail bytes from
0x5B01 and 176 printer-buffer bytes as AND masks for the screen; north1 and mix2 never reach it. Cosmetic, in the
fade only; the approved build kept, the fix is the owner's call (Open).

## Results (`selftest.py --game rambo --verify --stamp` and work/fullverify.py, 2026-11-03; simulation and JNext only)
| Output | MD5 | Status |
|---|---|---|
| rambo.nex (plain, tail 0x5B00) | 434a84778881e230d0c930677abad0b4 | boot sim OK |
| rambo_sprites.nex (base, the stamped build) | f6e64fc99ad2aa56fcb59e5c9a1582fb | boot sim OK |
| out/rambo_sprites.nex (base + loading screen) | 9ebfe9c8a88d3b2ca1fa9067e3abf2d5 | real loader, reaches play in JNext; hardware untested |
| out/rambo_enhanced.nex (the Enhanced set + loading screen) | c2395f02f504d4f38ccc2e0d12973b44 | real loader, reaches play in JNext; 35 bytes differ from the one above |
| Recording | Frames | Blits | Figures | Fallback | Hides | Sprites shown | Verify |
|---|---|---|---|---|---|---|---|
| play1 (random keys, no cheat, game over, menus) | 20245 | 1638 | 5784 | 0 | 13 | 21510 | IDENTICAL |
| north1 (cheats, north) | 15025 | 4315 | 17337 | 0 | 4 | 41172 | IDENTICAL |
| mix2 (cheats, wandering) | 20011 | 5735 | 23706 | 0 | 4 | 56954 | IDENTICAL |
| heli (hand-made state, not in the stamped set) | 12000 | 3197 | 15234 | 0 | 0 | 39876 | 2 blits differ, the rest IDENTICAL |
heli's 2 blits are the boarding frames at an x that is not a multiple of 8: the rotor graphic (0xDC30) has no spare column, so the original's rotation wraps its tips to the left of the next row (work/hv2.py lists the bytes: col 9 in the original, col 14 in the sprite, 5 columns, its width). The original's glitch; the sprite draws the tip where it belongs. No logic there, all RAM and registers still agree.
The same four on the Enhanced build (work/blackink.py): the same results; life starts 6, hides 21; black ink pixels in the play area at a blit: 0, in all 14885 blits.
Hook counts, play1 + north1 + mix2 + heli (work/counts.py): site 0x8052 99551 (figures 56030), site 0x8670 24801 (figures 6031), blit 14885, painter 14885, hide 0x6C8F 8, 0x7600 12, 0x74B3 1, life start 6.
Portraits at the 14885 blits: both 817, one 487, none 13581; changes 2 (play1, losing lives, no cheat). The infinite lives poke leaves them undrawn, as in the original.
Never ran in a recording: the painter's empty-list branch, both fallbacks. work/edge.py ran them directly on the first build.
Unit PASS: 1224 cases, figures 1012, fallback 0, all 136 descriptors. Negatives 17/17 on the real recording (work/fullverify2.log), the dirt ones: still in y, still in x, one step ahead, registers swapped in the copper list, copper waits for line 100, copper never started; earlier 12: row low, pixel right, colour lost, box kept, figures stay on the ULA, commit never runs, hide does nothing, figures over the panel, dirt stays still, Layer 2 on during the life tune within 2500 frames; plot side effect lost, portraits read the wrong row over the whole recording.
Loading screen (loading/run4.py, real .nexload from the Browser, control without the screen): timeout 254 frames, key 9 frames after the press; at the original start registers and mapping as the control, 0 of 40960 bytes differ over 0x4000-0xDFFF; Enhanced differs in the 33 bytes of its set.
Real loader (work/nxcrun.py, copy of card_all.img, chosen in the Browser): output MD5 exact for default, Enhanced, Enhanced + cheat 1; all reach play.
Enhanced figures checked frame by frame on png/enh_h.png, enh_blue.png, enh_heli.png, enh_white.png, and in play: convincing, so it is on the menu.
A bug only the real route showed: Layer 2 on during the tune before a life gave black silhouettes on the dirt. Now off, with a check and a negative.
Dirt in JNext, one screenshot per frame over 1190 frames of the Enhanced build walking north, east, west, north and south (work/jrun.py, work/jlock.py: dirt located in its tile by runs of 10 pixels, in four bands; scenery by its green pixels). Before (da0501c): of 237 frames where something moved, the dirt moved with the scenery in 0: y one frame early and split mid-picture in 101 frames, x never. After: 136 of 136, largest gap 0, no frame split. out/rambo_fix.png. In replay every blit checks each scenery object against the dirt (work/lock.log method): offset 0 on play1, north1, mix2, heli, long1.
Speed: not measured. Hooks run at 28 MHz and skip the figures' plots; no real-machine timing.
Colours: sheets in the run's sheets/; a painting of one byte changed bank 14 only and reversed exactly. Not the default.

## Hardware checklist (nothing here has run on hardware)
1. Boot the .nex: Ocean title, tune, Hall of Fame, menu. 2. S, name, ENTER, a key: yellow Rambo, green soldiers. 3. Cross a river: no yellow or green blocks; a shot's explosion stays white. 4. Figures at the panel, left, top and bottom edges: cut off cleanly, none over the panel. 5. Lose a life: sprites off at PRESS ANY KEY. Game over: none on the Hall of Fame. 6. Speed and sound against the plain .nex. 7. Interrupt vector: the game relies on FF FF at ROM 0x39FF and 0xF3 at 0x0000: JNext agrees, the board not tried.
Hardware risk review (PLAYBOOK 6b): DivMMC: hooks at 0x2000-0x2200 and RAM, not 0x3D00-0x3DFF. Interrupts: off at plot and blit, counted; hide sites NEXTREG only. Raster: commit is just before the blit, not beam-synced beyond the game's own wait.

## Open
- The end-of-game fade (0x6CA9) masks the screen with 0x5B00-0x5BFF, which holds the start-up tail and NEXLOAD's
  printer buffer in the .nex, zeros in the original: a slightly different fade pattern, never seen. A fix (tail
  elsewhere, keep_printer_buffer) changes the approved bytes: a v1.1 for the owner to approve.
- Coverage: score up to about 3900. Figure types reached in recordings from the start 40-46, 4B, 4C; 4E, 4F, 52 (helicopter) only from the hand-made state; not reached 47-4A, 4D, 50, 51, 53, the prison camp's figures: their tiles exist and pass unit cases, the frames were looked at on sheets, never seen in play. The bots stop at river rows (world position 0x33E, 0x53E, 0xA3E).
- A human's answers to "Defaults taken".
- Trainers from the .pok: infinite lives and immunity drove two recordings; No enemy, All weapons unplayed.

## Lessons
- [local: only this game's stack and table are this direct] demonstrated: a display list with an object type gives the figure / scenery split in one comparison, and scrolling costs nothing when the world is objects on black.
- [backlog C2 #35] observed: `inspect` warns "IM 2 handler in ROM"; the handler is RAM at 0xFFFF through the ROM's FF block.
- [local: needed because this game's music takes its timing from interrupts] demonstrated: running the patched game beside the original on fetch counts with hooks left out keeps interrupt-driven code in step; T-state frames do not.
- [local: a hook must keep what the next instruction uses] observed: the blit's BC is B from its own LD and C = 0 left by the wait; the first commit lost C and the blit ran off its table. Found by lockstep at once.
- [local: this game's flag] observed: a flag saying "x signed" also goes with small positive x; the first hook took it for negative, 3 frames in 55,000. Only the picture check would find that.
- [local: the script follows this game's recording format, run folder only] demonstrated: a recorded state as a .z80 + the same patch gives a JNext frame of any scene with no keys: work/scene.py.
- [deferred Open: reconsider when a maintainer reviews the batch] observed: `selftest --verify` leaves the verify report in its temp folder only; the stamped numbers were read there.

- [local: display-list descriptors found by shape] observed: a shape test on 12-byte descriptors missed six with a wrong size byte; the fallback hid it, since nothing reached them. A hand-made state using the game's own trigger found them in minutes.
- [local: figure frames] demonstrated: replay each direction key and read the hook's descriptor counts before painting: guessing front from back by shape was wrong, and a head that should be hair got a face.
- [deferred Open: reconsider when a maintainer reviews the batch] demonstrated: a colour change's trouble can be outside play: black ink on black paper is hidden until the paper is see-through, as in the tune before a life.

- [local: this game's approved build had two steps outside the engine] observed (import, 2026-11-04): the published
  .nxc held the Enhanced set and a loading screen that only run-folder scripts made; the record's outputs were the
  engine's alone (4f8330c6, stale). An import compares against `nxc.py --bare`, not the record, and moves such steps in.
- [deferred Open: reconsider when a second game needs a build input that is not a recording] observed (import,
  2026-11-04): a record has no input kind for game data a build reads (a tape's screen); it is listed with the
  recordings, which only staging reads, and the engine finds it beside the snapshot by name.

## Technique use
- detect.buffer-layout-producer: helped: named the question; the disassembly answered it.
- detect.gameplay-screen-readers: helped: `scan --writers` gave the proof.

## Stage log
- 2026-11-03 stages 0-3 in one session (batch, unattended): about 75 min, about 50 tool calls, 0 user rounds.
- 2026-11-03 the owner's changes: outline, portraits, Enhanced, loading screen. Finished by a second session.
- 2026-11-04 import into `refactor` (phase 7, group 3): engine as it was + Enhanced and loading-screen steps moved in;
  rebuild = .nxc v1.0 byte for byte; full verification stamped. 0 user rounds.

## Friction
- reuse: [local: rambo's loading stub is a copy of runs/altered_beast's v2] the same stub came in with Jet Pac (bank 13) in this import; a shared helper is the maintainers' call.
- retries: [none: the port rebuilt the approved MD5s first time]
- environment: [none: pinned sjasmplus gave the run's 1.23.1 stub bytes]
- hand-rolled: [none: no scratch tool kept]
- scratch: [none: import scripts stayed in the session scratchpad, nothing for tools/probes/]
