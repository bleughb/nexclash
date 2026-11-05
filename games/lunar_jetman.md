# Lunar Jetman (Ultimate Play The Game, 1983, 48K) - engine `lunar_jetman` (unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-04 (record lunar_jetman, stamped); JNext only, never on a Next.
Inputs: specnext/reference/lunar_jetman/ (lunar_jetman.z80 = the file's state at the decrypter, rzx/s_pre.z80 md5 426084d3;
lunar_jetman_s0.z80 the stepped start; p1-p3; lunar_jetman.scr; Jetpac.256). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom.
Start with: the hardware checklist below. Open: under "Open".

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04 (pilot clone runs/lunar_jetman, base d7abd1c, head 49b8a9e). Published .nxc:
Lunar Jetman v1.0 (md5 f55a30b0, github.com/jattree/nxc), build lunar_jetman_sprites, colour sets default and Enhanced.
Rebuild in today's tree = the approved build: sprites_loading 46348868 and enhanced_loading 62f7e914 = `nxc.py --bare`
(default / `--colours Enhanced`) of the published .nxc on 4fd3f151; also plain 3e5ca390 (from s0), sprites e33f68c4,
enhanced dfeb2cf9 (no loading screen). No pin: the engine writes the whole alt ROM image itself, which the new default
leaves alone.
Moved into the engine (the pilot used work/build2.py, loading/work/mknex.py, pack2.sh and the script work/verify.py):
build() (plain from s0; sprites and Enhanced from the decrypter state, encrypted=True; the decrypter check), the loading
hold (asm `loading` module, SAVEBIN loading / loadend; bank 5's own screen put in at build time), loading_nex(), auto(),
and verify() (work/verify.py as a function, the same checks; its screenshots dropped). Inputs beside the snapshot:
lunar_jetman_s0.z80, lunar_jetman.scr, Jetpac.256 (Jetman's Enhanced suit; the pilot read it from ~/Downloads), listed
with the recordings. The system ROM3 comes from nextboot.system_rom3() ($NEXCLASH_NEXT_ROM; the pilot read
$NEXCLASH_ROM3 or work/rom). Negative "whiteedge" (the images before the no-white change) needs the pilot's
work/lj_before.py and stays there (DETECTED, vlogs3/neg_whiteedge_enh.log). No shared code changed.

## Hardware checklist
Tape screen, a key or 5 s; menu 1 / 3 / 6. Jetman, aliens, bombs, items and the rover solid sprites in their own
colours, no clash with the ground or craters; the missile warning and the play-area clear leave no sprite; game over
and the Hall of Fame; Enhanced from the menu: no white rim, rover wheels dark with light hubs; trainers 1-3.

## Snapshot and start
Archive "Lunar Jetman (1983)(Ultimate Play The Game).z80", 4fd3f151dcf12216cb23618687da04d5, ZXDB 0009372 (eye-check
candidates). 48K only (no 128K release exists). The file stops in the BASIC loader (PC 0x38, PAUSE 0 still to come):
stepped with a key held to the decrypter's JP 0x8000 (printer buffer 0x5B80: RRD over 0x7FFF-0xFBFF), rzx/s0.z80
md5 94791e32. The .nex starts there; the .nxc targets the archive file and carries the difference.
Keys: menu 1 (one player), 3 (keyboard), 6 (start). Play: Q thrust, Z / X left / right, A fire (rows as Jetpac).
Loading screen: the tape's standard 6,912-byte SCREEN$ (block 4 of the .tap), held by the Altered Beast stub method
(loading/work: bank 34, entry bank, bank 5's own bytes put back; nothing else differs).

## Clash (owner's eye: clash; measured on p1, 2,500 frames, work/verify.py counters)
8.9 % of figure plots (218 of 2,455) show pixels in another ink, 3.5 % of figure pixels; figures repaint the cells they
cross (painters 0x8767 / 0x8937: every non-black cell under an object takes its colour), about 62 cells per frame left
in a figure's colour. Kind A. out/lunar_jetman_fix.png: Jetman's legs green inside an alien's cells.

## Rendering model
Cooperative scheduler (0x81E9 main loop, objects 24 bytes at 0x6078 + 24n, n 0-26; 0x6000-0x6077 run on frame ticks).
Two XOR plotters, both erase-and-draw line by line (old image in the alternate registers):
- figures (Jetman, aliens, bombs, items, explosions): setup 34498 (x IX+1, bottom line IX+4, graphic [H, 2H bytes,
  bottom row first] from the tables 47812 / 61054 by IX+0), lines 34255 / 34324 (shift by a self-modified JR), state
  IX+9..15 = what is drawn; 34431 clears it when the object leaves the window; 34368 erase only.
- trucks (0x6090 rover, 0x6180 its other form): setup 34854 (world x - scroll 24698, clipped) / 34979, byte-aligned
  W x H graphic [W, H, data], lines 34790 / 34755; 34383 erase only. Colours 35121: bottom two cell rows 71, above 69.
Screen readers besides the plotters: ground scroll (RRD / RR (HL), rows 176-183), lasers (XOR), 38470 OR, 39158 AND,
the text printer 35311: none branches on a pixel, so no figure collision reads the screen.

## Design
- The nine figure XOR stores and the three colour painters are NOPs, one byte for one (the plot code still runs).
- Hooks (alt ROM 0x386E-, 728 bytes): h_new at 34558 and h_tnew at 34958 (the setups' LD C,0 / RET) show the object's
  current image as sprites; h_clr (34462), h_eo (34368), h_teo (34383) hide them; h_cls (34011, the whole-screen pixel
  clear) and h_msg (46433, the missile warning, which prints over the play area) hide every sprite.
- Images precomputed at build time for every graphic in both tables (222 figure graphics, 22 truck graphics): 4-bit,
  ink, enclosed paper filled (a darker shade of the figure's own colour; trucks black), a one-pixel outline outside
  the silhouette (white; black for a white figure; none under 12 ink pixels). Figures 2 x 2 tiles at (x - 1, top - 1);
  trucks 5 x 2. Pages: 26 state (caches, graphic lists), 27 index (graphic & 0x1FFF -> id + 1), 28-31 trucks, 36-49
  figures; mapped at slot 4 only inside a hook (the ROM IM 1 handler uses slots 0 and 2; slot 4 back on page 4 before
  any return). Patterns uploaded only when an object's graphic changes. Sprites: trucks 0-19, object n 20 + 4n (figures
  in front of the rover). Palette offset = the object's ink + 8 * bright (IX+7) at each draw.
- Enhanced (colour set, off by default, no .256 for this game): Jetman from the Spec256 Jetpac (two of his frames are
  byte-identical with Jetpac's, one byte apart in one; the other frames take the colour of the nearest template pixel,
  mirrored or not, at the best overlap): orange suit, grey pack and visor. Other figures shaded in their own colour
  (light top edge, dark bottom edge, darker fill). Rover: cyan body in three shades, grey wheels, white highlights.
  Fixed entries 6-15 of every palette block; no colourist named.

## Results (2026-11-04, work/vlogs/*.log)
| Output | MD5 | Status |
|---|---|---|
| out/lunar_jetman.nex (plain, from s0) | 3e5ca3908616f76a33f864be57baef95 | boot sim OK, reaches play in JNext |
| out/altrom_fix/lunar_jetman_sprites_loading.nex (shipped default, v1.0) | 4634886880940d0db5e4cee9c1113819 (was e62785e7) | boot sim OK, play in JNext, real loader MD5 exact |
| out/altrom_fix/lunar_jetman_enhanced_loading.nex (Enhanced, v1.0) | 62f7e914c390fcce7477d5efd2423cad (was 5281c6f5) | boot sim OK, play in JNext, real loader exact with cheats 1-3 |
| out/lunar_jetman.nxc | 532c80c030f3995d00142e7d4383c0e8 | apply byte-exact, default and Enhanced |
Import verify (selftest --verify --stamp, 2026-11-04, ROM model NextZXOS ROM3 8c34d957): p1-p3 (22,090 frames)
IDENTICAL default and Enhanced, unit PASS (setup palettes, whole image, rom3_left control), 16 of 16 negatives DETECTED
(p1, 700 frames); ROM paths: every ROM byte the sprite builds run is as recorded, tail never read before written.
Pilot: replay IDENTICAL on p1 (6,000 frames), p2, p3 (8,045 each, infinite lives), default and Enhanced: hooks h_new 30,374,
h_tnew 19,761, h_clr 105,103, h_eo 271, h_teo 4, h_cls 44, h_msg 4; 11,971 interrupts checked, 35,595 object checks.
Negatives 11 of 11 detected. Hook time 3.6-7.6 % of a frame at 28 MHz (sim T / 6); JNext walking pace equal to plain.
The shipped build starts at the file's decrypter; the simulator shows it reaches the verified s0 + sites at 0x8000
apart from 16 bytes (KSTATE, FRAMES, dead stack). Cheats: the .pok's proven entries, written for the rotated code.

## Defaults taken (a human would have decided)
1. Every object the two plotters draw is a sprite; lasers, ground, craters, HUD and text stay on the ULA.
2. Depth: figures over the rover, by object number among figures (the original XORs, no depth).
3. Outline on by default (owner's rule), white; black for white figures; none under 12 ink pixels.
4. Enclosed paper filled with a darker shade of the figure's own colour (items solid in their own colours).
5. The rover's outline and fill black (it is half white); its colours by cell rows, as the game paints it.
6. Enhanced painted by rule, not by hand, except Jetman's colours, which come from the Spec256 Jetpac.

## Open
- Hardware, CSpect: none. Speed on a board.
- Colour changes without a redraw (IX+7 changed between draws) are not followed: 8 in 1,500 frames on p1.
- Not reached on the recordings: the alien base, the missile and its destruction, bombing, the rover carrying items,
  later levels. Their graphics are in the tables, so their images exist and are drawn by the same hooks.
- Evidence record, doccheck, selftest stamp: not done.

## Lessons
- [doc docs/ENGINE_CONTRACT.md §Module names] The contract's `verify(patch, rzx, stop, ...)` is a module function:
  the pilot's work/verify.py ran from sys.argv with module globals, so the import made it one function (closures).
- [local: inputs beside the snapshot] The build reads three files that are not recordings (the start state, the tape
  screen, the Spec256 Jetpac): they ride in the record's recordings list, md5-checked and staged beside the snapshot.
- [local: a loader snapshot] Step it with a key held to the decrypter's jump; the .nxc carries the difference.
- [local: message screens wipe figures] A message screen printed over the play area wipes figures without the clear routine: find every
  routine that overwrites the play area (who.py: screen writers per frame) and hide sprites there.
- [local: verify from the title] A recording that starts mid-game leaves the sprite model and the figure model empty
  while the screen has figures; start every recording at the title, cheats poked into the start state.

## Enhanced, second version (2026-11-04, coordinator's ask: "colourise like the other Ultimate games")
One shared 15-colour palette in every block; every figure painted by its parts (nexclash/lunar_jetman.py FAMILY):
Jetman orange suit (Spec256 Jetpac), cyan visor, grey pack, yellow/orange flame dots; rover blue/cyan body, white top
edge, blue cockpit, yellow chassis trim, grey wheels; each alien family its own body ramp with the paper it encloses and
its small pieces in a contrasting colour; blasts and mines radial yellow/orange/red; sparks white/cyan/blue; bombs red
with a yellow B. Silhouettes, fills and outlines equal to the default (checked per tile at build and in verify).
Replay IDENTICAL p1-p3 Enhanced; Enhanced negatives 5 of 5. Too plain to take features: the spinning green cubes
(types 136-143, solid blocks: shaded only) and the debris dots (88-91, 100, 183).
.nxc b0fde37e86e12eb5b1cb63cf0e17f395 (previous lunar_jetman.prev.nxc 532c80c0); real loader exact, default and
Enhanced + cheats 1-3.

## Enhanced without white (2026-11-04, owner: "a version of the graphics without the white outline")
Owner's rule: no white outline and no white edge highlights on a black play area. In Enhanced the one-pixel outline is
black (palette index 14, OUTLINE, black but apart from BLACK so an outline-only figure tile never equals the rover's
outline-only tile; brown went, the ringed planets' shade is now dark red). White stays only inside a figure (eyes and
pod windows, canister body, blast and spark cores); any white pixel touching the outside is replaced (_no_white_edge).
No family paints ink black any more (it vanished once the rim went): guns, towers and debris light grey with dark grey;
cubes and legged saucers dark green; bug robots, invaders, pods and birds blue; bombs dark red. Small pieces that were
white (cubes, red balls, bombs) are yellow. Rover: cyan top edge in place of white; wheels found per frame (the 22
whole-rover frames, H 27) and painted as a solid dark-grey tyre with light-grey spokes on black; debris and the other
truck-table images light grey. Default build byte-identical (same .nex MD5s). Replay IDENTICAL p1-p3 Enhanced with
the same hook counts; Enhanced negatives 6 of 6 (new: the previous white-outline images left in).
Sheet: png/enhanced_nowhite_sheet.png. JNext strip: png/enhanced_nowhite_jnext_strip.png.

## Whole alt ROM image (2026-11-04, pilot/runs/altrom_audit/AUDIT.md and FIXES.md)
The build now writes all of alt ROM image 1: altrom = (0x2000, 0x4000) from a page of Sinclair's 0x2000-0x3FFF plus the
hooks, and altrom_low = Sinclair's 0x0000-0x1FFF in page 25 (bank 12's upper half, unused before). Before, only the hook
bytes were copied over the stub's first fill, which is NextZXOS's ROM3, not Sinclair's: its IM 1 handler CALLs 0x386E and
its UDG print JPs to 0x387E, both into the hooks, masked only by NextZXOS's DivMMC trap at 0x0038. The verifier now models
the image as the Next fills it (ROM3 from work/.../enNextZX.rom, MD5 8c34d957, then the build's writes); hook_range keeps
the hook bytes for "hook instructions"; rom3_left() rebuilds the previous build byte for byte and is the new negative.
The .nex differs from the previous one only in bank 10's stub (the fill, 15 bytes longer, the code after it shifted) and
bank 12 (the image's page bytes). Emulator only.

## Techniques
Techniques: `patch.whole-altrom-image` (docs/records/lunar_jetman.json)

## Friction
- reuse: [local: the loading hold is the same stub as Starquake's and Robin's, one copy per engine]
- retries: [local: the detector missed the decrypter state; it now decrypts first]
- environment: [local: needs NEXCLASH_NEXT_ROM=enNextZX.rom; full verify ~80 min detached]
- hand-rolled: [local: the script verifier wrapped into verify() by a scratch converter]
- scratch: [none: the converter and test scripts dropped]

## Technique use
- patch.whole-altrom-image: helped: altrom 0x2000-0x4000 + altrom_low keeps NextZXOS ROM3's IM 1 out of the hooks.

## Stage log
- 2026-11-04: imported into the repo (refactor phase 7): rebuild = the published v1.0, full verify stamped. 0 user rounds.
