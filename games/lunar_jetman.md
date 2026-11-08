# Lunar Jetman (Ultimate Play The Game, 1983, 48K) - engine `lunar_jetman` (unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-04 (record lunar_jetman, stamped); pace about +0.4% after
the 2026-11-08b pattern pool, R kept as the original's (below); JNext only, never on a Next.
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
- The nine figure XOR stores, the nine screen reads before them (XOR (HL), 2026-11-08b) and the three colour painters
  are NOPs, one byte for one (the plot code still runs; R unchanged: one M1 for one).
- Hooks (alt ROM 0x386E-, 799 bytes): h_new at 34558 and h_tnew at 34958 (the setups' LD C,0 / RET) show the object's
  current image as sprites; h_clr (34431, the state clear: only when something is drawn, since 2026-11-08), h_eo
  (34368), h_teo (34383) hide them; h_cls (34011, the whole-screen pixel clear) and h_msg (46433, the missile warning,
  which prints over the play area) hide every sprite.
- Images precomputed at build time for every graphic in both tables (222 figure graphics, 22 truck graphics): 4-bit,
  ink, enclosed paper filled (a darker shade of the figure's own colour; trucks black), a one-pixel outline outside
  the silhouette (white; black for a white figure; none under 12 ink pixels). Figures 2 x 2 tiles at (x - 1, top - 1);
  trucks 5 x 2. Pages: 26 state (caches, graphic lists, the pattern pool, tile ids, the objn table), 27 index (graphic
  & 0x1FFF -> id + 1), 28-31 trucks, 36-49 figures; the state page at slot 4 and an image page at slot 5 only inside a
  hook (the ROM IM 1 handler uses slots 0 and 2, the game's stack is at 0x5Exx; both back on pages 4 / 5 before any
  return). Patterns: one pool of all 128 shared by tile content (2026-11-08b, below). Sprites: trucks 0-19, object n
  20 + 4n (figures in front of the rover). Palette offset = the object's ink + 8 * bright (IX+7) at each draw.
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
- Pace: about +0.4% on the replay, up to +1.8% in the quietest third of updates (2026-11-08b): what is left is per-call
  fixed cost (h_clr's test and R fix for 10 objects an update, the speed switch at the caller's clock), not uploads.

## Lessons
- [doc docs/ENGINE_CONTRACT.md §Module names] The contract's `verify(patch, rzx, stop, ...)` is a module function:
  the pilot's work/verify.py ran from sys.argv with module globals, so the import made it one function (closures).
- [local: inputs beside the snapshot] The build reads three files that are not recordings (the start state, the tape
  screen, the Spec256 Jetpac): they ride in the record's recordings list, md5-checked and staged beside the snapshot.
- [local: a loader snapshot] Step it with a key held to the decrypter's jump; the .nxc carries the difference.
- [local: a missing reference input] Three refactor sessions skipped this game because "Jetpac.256 is not in the
  references", but the file was on the machine (a Spec256 download, the record's md5). Search by the record's md5
  before skipping a verify.
- [local: message screens wipe figures] A message screen printed over the play area wipes figures without the clear routine: find every
  routine that overwrites the play area (who.py: screen writers per frame) and hide sprites there.
- [card patch.restore-speed §Failure lookup] A hook with no speed switch at all, run for every object every update
  (h_clr), cost about 7% where the hooks that switch cost 2-6%: count calls per update before trusting "small" hooks;
  skip the call when the game's own state says there is nothing to do (IX+10 = 0).
- [local: pace not in lockstep] The game takes LD A,R (0x9466) for its randomness and runs its frame tasks on interrupts,
  so JNext runs of two builds play different games (port 0xFE writes 106 against 179): pace by seed varies -25% to +18%.
  The replay pace (the recording on both sides) is the like-for-like figure; JNext over 8 seeds is the cross-check.
- [local: verify from the title] A recording that starts mid-game leaves the sprite model and the figure model empty
  while the screen has figures; start every recording at the title, cheats poked into the start state.
- [card optimise.pattern-cache §Probe and stop] Simulate the cache on the hook call log before building it: a per-slot
  tile cache (each object its own patterns) saved 60% of figure tile uploads, a pool shared by content 97% (p1: 7,055
  against 162 misses; 48 distinct graphics in 4,532 draws). The card's probe 2 (distinct images in the worst scene)
  says the same: the working set was a third of the pool.
- [local: profile the hook by routine] After the uploads, the T per routine (assembler symbol file, simulator) showed
  the pool's own bookkeeping (acq) and the attribute writes as the next costs, not what was guessed; the profile picked
  each next step (register acq, port 0x57, the truck memo: 66% of h_tnew calls repeat the last placement).
- [local: a negative the recordings cannot reach] The `evict` negative passed the 700-frame replay (the pool never fills
  that early): a table-full case needs its own driven check (the pool check), as the rules say; run every new negative
  once before trusting the list.
- [local: ROM-resident hooks] The alt ROM leaves 1,150 bytes for hooks (to 0x3D00 less the register block): code that
  runs only with the state page mapped (the pool, placement, objn, list search: 326 bytes) moved there (asm ORG 0x8900,
  profile block stcode, put in by the build); the ROM keeps 914 bytes. Check the size after every assemble.
- [card patch.preserve-r §Use / do not use] An existing engine whose game takes R for randomness (LD A,R 0x9466) gets
  R kept in its first rework: read R at a fixed M1 count from the site, set it at a fixed count before the return; the
  verifier's "R to add at <hook>" counter gives each constant from a run with K = 0 (all eight matched the count by
  hand). Cost: about 48 T a call on h_clr's 3.5 MHz path (+0.5%), paid back by NOPing the screen reads whose results
  only fed NOPed stores (-1.4%), proved by a plot check (registers with R and memory equal at the line routine's end).

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

## Hooks restore the caller's CPU speed (2026-11-07, shared engine refactor)
- h_new / h_tnew read NR 7 at entry, keep it on the stack (no RAM for a latch in the alt ROM) and write it back; the
  verifier enters each hook at 3.5, 7, 14 and 28 MHz in turn and checks the exit clock (negative `speed35`).
- The verify needs Jetpac.256 (md5 95d29dd6) beside the snapshot.

## Pace (2026-11-08): h_clr hid at 3.5 MHz with a loop, every update, for every object outside the window
- Cause: the state clear 34431 runs every update for every object outside the window (about 10 calls an update); its
  hook hid 4 sprites at 3.5 MHz after a subtract-24 loop: about 950 T a call, some 7% of the original's update.
- Fix: h_clr at the clear's entry 34431 (4 bytes checked, continues at 34435); nothing drawn (IX+10 = 0) passes
  straight on; otherwise hidefig at 28 MHz with the caller's speed kept. objn without a loop; uploads by OUTI.
- Verifier: the replay pace per game update (0x9ED2): the original's time on the recording and the T the build adds
  (each hook pair patched minus original, its 28 MHz span at T / 8, the NOPed instructions' saving); auto prints "Pace".
- Replay pace +13.7 / +14.4 / +14.0% (p1-p3, main aca1c90c) -> about +4.3% (5c53849e; table in the next section);
  JNext 8 seeds (not in lockstep, see Lessons): mean +17.05% -> +4.15%. Stamped; loader run on a private card copy.

## Uploads (2026-11-08b): one pattern pool shared by tile content; R as the original's
- Cause: after 2026-11-08 pattern uploads were about 70% of h_new's added time (p1: 17,436 figure tile uploads in 4,532
  draws, 60% of them bytes the pattern already held); only 48 figure graphics are drawn on p1, but each object had its
  own four patterns and re-uploaded every animation frame.
- Pool: every 128-byte tile of both image sets has a 16-bit content id (455 figure, 265 truck tiles; FTID / TTID).
  All 128 patterns are one pool in the state page: WHERE (id -> pattern), PCACHE (pattern -> id), OBJP (4 patterns per
  object, 10 per truck: 128 entries), REFS (entries naming a pattern). A new graphic releases the object's entries (rel)
  and takes a pattern per tile (acq): one holding the tile, else the next round robin pattern no entry names, uploaded
  (image page at slot 5). An object keeps its patterns until its next new graphic, hidden or not, so a free pattern
  always exists. p1 uploads 19,516 tiles -> 681.
- Also: attributes by port 0x57 (pattern bytes precomputed by acq); a truck placed as last time (graphic, x, y,
  columns) is not rewritten (2 in 3 h_tnew calls on p2; hides clear the memo); the truck list searched only for a new
  graphic; objn by table (OTAB). Code that runs only with the state page mapped (326 bytes) lives in page 26 at 0x0900
  (asm ORG 0x8900, profile block stcode): the alt ROM keeps 914 of its 1,150 bytes.
- R (card patch.preserve-r): every hook reads R at a fixed M1 count from its site and sets it (rfix, bit 7 kept) at a
  fixed count before its return; constants R_NEW .. R_CLS in the asm (the verifier's "R to add" counter with K = 0
  equals the count). Cost: about 48 T a call on h_clr's 3.5 MHz path (+0.5%); paid back by NOPing the nine XOR (HL)
  screen reads before the NOPed stores (A only fed the store, flags overwritten before any test; one M1 each; -1.4%).
- Shared code: none changed. hlib_pcache / hlib_commit / hlib_dma keep tables and DMA packets at fixed addresses in
  hook RAM; these hooks are in the read-only alt ROM. hlib_pace: not needed (no frame sync, the build is not faster).
  DMA (docs/DDMA.md): not used: uploads are now about 5% of the added time (at most about 0.1% to gain), interrupts
  stay on in IM 1 through the hooks (a burst can cover the ULA interrupt pulse), and the replay cannot time DMA.
- Verifier: R compared at every hook and IM 1 (hooklib.CMP_R); a plot check from every 32nd screen read to AND 7
  (34299), original against build, registers with R and memory outside the bitmap equal; slot 5 and port 0x57
  modelled; a pool check after the replay (2,500 random calls over all 222 graphics and the rover frames, the pool full
  and churning: every shown sprite shows its graphic's tiles). New negatives: `tid` (tile ids moved), `evict` (a held
  pattern reused; the 700-frame replay alone never fills the pool), `r1` (R one off), `xorlive` (INC L NOPed too).
- Replay pace, all / quiet third / busy third (default):

| recording | 1.0 (published 46348868) | 1.1 (8bd7ab74) | pool, R not kept (ed8f6108) | this (2fdd4986) |
|---|---|---|---|---|
| p1 (1,466 updates) | +13.47 / +16.88 / +11.67% | +4.23 / +4.12 / +4.52% | +1.15 / +1.33 / +1.20% | +0.37 / +0.80 / +0.31% |
| p2 (4,161) | +14.13 / +19.84 / +12.26% | +4.35 / +4.97 / +4.69% | +1.27 / +1.91 / +1.27% | +0.57 / +1.74 / +0.33% |
| p3 (4,289) | +13.71 / +18.20 / +12.08% | +4.34 / +4.81 / +4.72% | +1.20 / +1.71 / +1.24% | +0.43 / +1.36 / +0.29% |
- Enhanced, this build: p1 +0.40 / +0.79 / +0.35%, p2 +0.61 / +1.76 / +0.39%, p3 +0.46 / +1.38 / +0.34%. 1.0 measured
  with this verifier on the published hooks (its fixed exit clock fails the speed check; the pace still counts). JNext,
  8 seeds (not in lockstep: interrupts land at other points in each build): mean +2.18% (median -1.00%), seeds -11.3%
  to +17.9%; 1.1 +4.15% (+6.12%).
- Sprites 5c53849e -> e5876b54, sprites_loading 8bd7ab74 -> 2fdd4986, enhanced c0453b9c -> 999da186,
  enhanced_loading ad21539c -> b8062918; plain unchanged. selftest --verify --stamp: p1-p3 default and Enhanced
  IDENTICAL with R compared (22,090 frames, 155,561 hook calls), unit PASS, negatives 23/23.

## Techniques
Techniques: `patch.whole-altrom-image`, `optimise.pattern-cache`, `patch.preserve-r` (docs/records/lunar_jetman.json)

## Friction
- reuse: [local: the loading hold is the same stub as Starquake's and Robin's, one copy per engine]
- retries: [local: the detector missed the decrypter state; it now decrypts first]
- environment: [local: needs NEXCLASH_NEXT_ROM=enNextZX.rom; full verify ~80 min detached]
- hand-rolled: [local: the script verifier wrapped into verify() by a scratch converter]
- scratch: [local: 2026-11-08b's probes (hook call log, pool simulation, per-routine T profile from the assembler's
  symbols) stay in the pilot's work-20261108b, outside the repo]

## Technique use
- patch.whole-altrom-image: helped: altrom 0x2000-0x4000 + altrom_low keeps NextZXOS ROM3's IM 1 out of the hooks.
- patch.preserve-r: helped: R read and set at fixed M1 counts in all eight hook paths (own rfix: no hook RAM before the
  state page is mapped); the counter "R to add at <hook>" gave each constant.
- optimise.pattern-cache: helped: content keys (tile ids built at build time) over one pool of all 128 patterns, own
  copy (the library needs hook RAM at a fixed address; these hooks are in the alt ROM): figure tile uploads -97% on p1.

## Stage log
- 2026-11-04: imported into the repo (refactor phase 7): rebuild = the published v1.0, full verify stamped. 0 user rounds.
- 2026-11-08: pace: h_clr at the clear's entry with a skip, hides at 28 MHz, objn without a loop; replay pace in the
  verifier; full verify stamped. 0 user rounds.
- 2026-11-08b: uploads: one pattern pool shared by tile content, attributes by port 0x57, the truck memo, objn table;
  R kept and compared, the screen reads NOPed; pool check, plot check and negatives tid / evict / r1 / xorlive in the
  verifier; full verify stamped. 0 user rounds.
