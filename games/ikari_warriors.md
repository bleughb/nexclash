# Ikari Warriors (Elite Systems 1988, 48K form) - engine `ikari_warriors` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: imported into `refactor` 2026-11-04 (phase 7); stages 0-3 and six colour
passes done in Jon's run folder; never run on a Next or in CSpect; JNext only.
Inputs: specnext/reference/ikari_warriors/ (ikari_warriors.z80 md5 54ad66af, 8 scripted .rzx, sheets)
Start with: the hardware checklist below; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `optimise.pattern-cache`

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04: the pilot run's clone (pilot runs/ikari_warriors/nexclash,
576b020..11930f8 on d7abd1c) brought onto `refactor` 884d31a. Published .nxc: **Ikari Warriors v1.0**
(github.com/jattree/nxc, patch md5 e1305b46; Jon Attree; credit Dean Woodyatt / NexClash). `nxc.py --bare` of it
gives default e740ae71 and Enhanced 22be808b: `auto` builds both byte for byte (plain 2d56c304).
- Moved in as it was: nexclash/ikari_warriors.py, asm/ikari_warriors_hooks.asm, docs/profiles/ikari_warriors.json
  and ikari_warriors_edges.json (the default's seams / edges, fifth pass), the record. No shared code changed.
- Pinned: `"pin": {"altrom_fill": "rom3"}`. The hooks are in the alt ROM (0x2400-0x3017); the owner approved the
  build made with the fill before 2026-11-04. Today's default (whole image) gives sprites 7b0c16fa: a rework, not
  this build. The start-up tail passes today's check.
- Moved into the engine from the run folder: the Enhanced build (work/enh2/mkenh6.py: `build_enhanced`, table
  work/enh2/colours6.json = docs/profiles/ikari_warriors_enhanced.json, the owner's sixth pass) and the engine
  negatives (work/neg.py: on ik_cheat1, the line-table one on ik_att). verify runs default and Enhanced on all 8
  recordings (the old record listed 4).
- Moved in: the colour-set checker that proved both approved builds (work/enh2/venh5.py + seams.py: `set_check`,
  `default_patterns`, `set_patch`; verify() takes its compose). The engine's own picture check fails on these builds
  (picture! on every recording: no outline, nothing outside the black edge), so `auto` replays each recording three
  times: the first default (IkariPatch(colours={})) for the classing patterns, then default and Enhanced through
  set_check. Its negatives on ik_2pw: 4 default + 8 Enhanced. Not moved: 7 Enhanced negatives that need the run
  folder's old colour tables or the 17:00 module (colours5 / colours6 neg tables, fourth and fifth pass, OLDPKG), and
  storecheck5.py's static pass over every frame; their results stand for these bytes (games file "Sixth pass").

## Inputs
Snapshot: archive "Ikari Warriors (1988)(Elite Systems)(48K-128K).z80", md5 54ad66af6678df22a9d4443e3d04aadb, ZXDB 0002450 (from eye-check-candidates; the filecheck lookup returned 502). v1 48K snapshot, PC 0x0038, DI, IM 1, SP 0xFFEA, loading screen with a key wait. 128K forms seen, not used: +3 .dsk, plain .tap / .tzx are 48K-128K.
Keys: any key leaves the screen; player 1 menu: 5 (cursor joystick: 5 left, 6 down, 7 up, 8 right, 0 fire), toggle key SPACE; player 2 menu: 4 (Kempston), toggle ENTER; 1 starts one player, 2 two. C+V+B abort, 6+B pause.
Recordings (no Fuse, scripted): ik_play1 random keys, no cheat; ik_gameover stands still to GAME OVER; ik_cheat1 and ik_bot2_1 closed-loop north, archive .pok lives / immunity / fuel / ammo / grenades in the RZX snapshot; ik_2p two players.
No menu option changes the drawing: control selection only.

## Rendering model
Back buffer, exactly MMU slot 6: 8K circular, 32 bytes a line, origin (0xE460), scrolls 2 lines a step. Attributes: 1K circular at 0xE000, origin (0xE462). Window 22 x 21 cells at screen column 5, row 2. Blit 0x62B2, 74.5K T, per game frame. Game frame about 200K T, no frame sync, DI in play (all 121 interrupts of every recording fall in the loading screen).
Main loop: logic and scenery tiles (0x9803), K5, K8, K3, K1 x 7, K6, K1 players, K4, K2, blit, then the erases in exact reverse. Buffer readers in play: the plotters, their saves and the blit only (scan, full list); logic reads the attribute buffer (terrain), never pixels.
Figures: K1 0x6D0E masked 3 x 18 with 4 rotations (and an AND-only variant, and wading); K2 0x67C5 bullets, masked 2 x 10; K3 0x6980 XOR 3 x 24; K4 0x6B8D dots, XOR 2 x 2 pixels, cancels itself on an odd line; K5 0xF845 pick-ups, opaque 2 x 14; K6 0xF76A heavy objects, 4 x 24, edges masked; K8 0x6879 debris, XOR 2 x 8 from ROM bytes 300 / 1020 (ROM read), also XORs an attribute into the attribute buffer (stays: it is on the ULA and logic reads it). K7 0xF026, stipple: permanent scenery, logic phase, stays.
Torn lines: K2 K3 K5 K6 K8 step two lines at a time and test the carry only on the second, so across a 256-byte boundary part of the figure lands 8 lines higher. An original glitch; the sprite is whole. Verify places those lines as the original does when it compares.

## Clash census (work/clash.py, ik_cheat1, at each blit)
9,506 K1 plots in view: 7.5 % over more than one attribute, 6.5 % over more than one paper. Ink pixels not black 0.65 % (blue 6,871, red 503, of 1,131,075). Opaque non-ink pixels: 46 % of figure pixels, in the cell's paper. Figures never write attributes except debris. Kind B with some of A: black figures, see-through nowhere much; the owner's verdict is "clash; black figures over colour". Numbers and eye agree that the figures are black; the owner's call on building stands.

## Design (defaults, unattended)
The game's own code runs unchanged, every game byte stays as the original's; only the blit's source changes.
| Site | Original | Hook |
|---|---|---|
| 0xEBAA | CALL 0xF8C8 | copy the window to page 27, phase on, then the original |
| 0xEBC5 | CALL 0x62B2 | slot 6 = page 27, 7 MHz, the blit |
| 0xEBC8 | CALL 0x6711 | slot 6 back, commit, then the original |
| 0x6D0E 0x67C5 0x6980 0x6B8D 0xF845 0xF76A 0x6879 | plotters | log the figure; a new image goes to a pattern |
| 0xEB13 0xEC0C 0xF214 0xAB7C | leaving play | sprites off |
K1 is captured by running the game's own body twice on page 28 (backgrounds FF, 00); its registers are saved and restored around that, IY too (the body writes it; DI). The others read their stream.
Hooks in alt ROM image 1, 0x2400-0x2D19. Page 26 at slot 4 while a hook runs. Cache 32 images, 4 patterns each, 32 x 32. Log 100. Sprites ordered as plotted. Clip = the window. Tail 0x5F00, a stale code copy never read or written (scan on all recordings).
Colours: ink black; opaque non-ink pixels take the paper of the cell under the figure's centre, through palette banks (bank = paper + 8 x bright, index 1 in each bank). Indexes 2-15 are fixed. So a figure no longer splits at a cell edge and ink no longer turns blue over water.
XOR kinds are drawn black: a sprite cannot invert.

## Results
| Output | MD5 | Status |
|---|---|---|
| ikari_warriors.nex (plain, tail 0x5F00) | 2d56c304bcb21619d8402d64804fef75 | boot OK, reaches play in JNext |
| ikari_warriors_sprites.nex | d6a6fce258b1949448e725b88c800dab | boot OK, reaches play in JNext and through the real loader; lockstep below; hardware untested (v1, d0e7d8b5, kept as ikari_warriors_sprites_v1.nex) |
Lockstep (work/v1.py): the original under the RZX, the patched build in the Python simulator fed the original's IN values. At every commit: all memory 0x5B00-0xFFFF, all registers but R / T / MEMPTR, paging, the attribute area, pixels outside the window, and ULA + sprite layer against the original's screen, pixel by pixel.
Results, whole recordings, no failures: ik_play1 4,829 frames 1,446 commits; ik_gameover 12,612 / 1,134; ik_cheat1 8,815 / 2,853; ik_bot2_1 16,879 / 6,286; ik_2p 6,877 / 2,004; ik_att (attract, then play) 5,025 / 925; ik_tank 11,986 / 3,817. 18,465 commits. Hook counts in ik_cheat1: e_pre, e_bl, e_post 2,853, e_k1 11,332, e_k2 2,209, e_k3 980, e_k4 5,762, e_k5 370, e_k6 815, e_k8 5,536. No cache entry taken while on show. Max 69 sprites, 46 figures.
Negative controls, all DETECTED: blit from the figures, clean copy short, K1 registers off (lost sync), dots dropped, sprites a line low, debris attributes left on the ULA, line table fix off. e_ab runs outside the lockstep's sync points: work/u3.py ran 16 of them from the original's state, memory, registers and attributes equal at return, screen differing only at lines 144 and 146. Colour map: 40,256 pixels right, map left out detected; rotation table 74,624 pixels against the game's graphics, 0 wrong.
Hide hooks: e_h2, e_h4 ran in lockstep on ik_gameover with no sprites left; e_h1 ran in JNext only; e_h3 (level end) was never reached by a recording; all four unit tested from a real state (work/u2.py).
One allowance: F bits 3 and 5 after the blit (its last LDI copied clean scenery, not a figure), counted, overwritten by the next flag-setting instruction, later memory equal.
Speed: hooks 421K T a game frame at 28 MHz, about 70K in 3.5 MHz terms, 35 % of a game frame; worst frame 2.9M T (485K in 3.5 MHz terms), on a burst of new images. The 14 MHz blit gives back about 56K. Estimate from the simulator; not measured on a board.

## Results in today's tree (`selftest.py --game ikari_warriors --verify --stamp`, 2026-11-04, after the import)
Rebuild = recorded: plain 2d56c304, sprites e740ae71, Enhanced 22be808b (= the .nxc v1.0's default and Enhanced);
recolour guard OK. Verify, per recording, default and Enhanced each IDENTICAL through the colour-set checker:
ik_play1 4,829 frames / 1,446 commits, ik_cheat1 8,815 / 2,853, ik_bot2_1 16,879 / 6,286, ik_2p 6,877 / 2,004,
ik_2pw 7,841 / 2,517, ik_att 5,025 / 925, ik_gameover 12,612 / 1,134, ik_tank 11,986 / 3,817 (20,982 commits);
96,698 images checked; enemy faces checked in Enhanced 3,302. Negatives: colour sets 12/12 on ik_2pw, engine 7/7.
Stamped verified 2026-11-04.

## Second pass (owner's findings on v1)
- Release: no 128K .z80 exists. Both archive .z80s are 48K-format; this file holds the game's AY code (0xB6F0, 0xC14E, writing 0xFFFD / 0xBFFD with no machine check: 1,378 calls before play in ik_play1 and ik_att, none during play, work/ay4.py), at the same offsets as the +3 disk's. The Next has an AY, so this file is the 128K game. The only other forms are tapes and disks.
- Loading screen: the snapshot's bank 5 is byte-identical to the tape's 6,912-byte screen (md5 4e023c22), on show until a key. Nothing to add, no stub.
- Attribute writers in play (work/phases.py, work/wrcall.py, work/attrw.py, three recordings): 0x5800-0x5AFF: the blit 0x6361-0x638B, and 0x60B4 in the HUD printer 0x608D (callers 0x7179, 0x7196, 0x71C4 via 0xEE8F, 0xEE9B), 0 of 69,912 in the window. 0xE000-0xE3FF: 0x97CB tile routine 0x9733 (scenery, logic phase) and 0x68CC debris 0x6861 (draw and erase). The debris toggle stays in game memory, as logic reads it; the blit reads a clean copy (ATTC). In the sprite build no window attribute changes except by scrolling: 0 cells in place over 2,412 still commits (work/scrollrem.py).
- Enemies: no plotter misses a hook. Every buffer writer in the draw phase belongs to a hooked plotter (work/phases.py). A missed one could not clash anyway: the blit shows the copy made before the first plot, so it would vanish and fail the picture check. The inconsistency was ours: V_FO skipped outline and fill for every K1 frame from 57 up, meant for the ripple (57), so the bunker soldiers (58-62) had none. Now only 57.
- Foliage: figures took the paper under them, dark green, so black ink on green over black and green scrub. Bodies on green terrain now take the bank of sand yellow (0x40 / 0xC0 -> 0x60), with the white outline. The AND-only wading frames (16-23) keep a black fill with cleared pixels in yellow (I_DET).
- The dashed line, at y = 146 with its partner at y = 144: the game's own. The blit's 168-entry line table sits at 0x5B00, over KSTATE (0x5C00-0x5C07), so once the ROM's IM 1 keyboard scan has run, entries 128 and 130 hold 0x00FF: those lines go to ROM and are never refreshed. Original, plain and v1 all show it. It lasts into a game started from attract, where the two lines stay blank. Fixed in the sprite build: all four blit sites run on a private table in page H (e_bl, e_ab), operand restored afterwards, so no game memory differs. The recordings before ik_att all went straight into play and never saw it.
- XOR figures: a sprite cannot invert, so K3 and K4 pick by bank: black, yellow over blue ink, white in foliage. K8 stays red.
- Tank: the "IN" object is the parked tank, K6 hull with K1 frames 49-56 as the gun. ik_tank steers onto one and the object goes, but no tank is seen driven.

## Enhanced colours, passes 1-4 (2026-11-03; consolidated at the import, full text in the run clone's games/ikari_warriors.md)
Owner's ask after his test: players apart from enemies at a glance (red headband player 1, blue player 2, enemies in a
contrasting uniform). Painted, no .256; menu set `Enhanced`, off by default.
- Roles: players share graphics with enemies, so K1's colour base is chosen by object in hook code after the hooks
  (`enhanced_patch`): enemy 0xB700 + 36 f; player (flag 0x80) 0xAD00 + 36 f (K5/K6's keys, so those stay default);
  player 2 (object 0xE5A7) AND-only 16-23 0x92C0 + 36 f; 16-23 drawn the normal way 0x9524 + 36 f; player 2 = bit 1 of the
  cache key. The AND-only plotter's rotation codes (0x6D99 0x6E80 0x6E75 0x6E8D, table 0x6E30) differ from the normal ones:
  the Enhanced code maps them. Masks by object type (ix+8): 0x6FBE for 4 5 12 13 28 29 36 37, else 0x6E9E.
- Paint (pass 3 rule, kept): only the body, a non-ink pixel with the figure's ink left and right and above and below; K1's
  mask blob beyond the drawing is the game's paper border, painting it leaked colour (the owner's "leak", pass 2). Players
  skin, dark trousers, band on line 1; enemies uniform (steel blue 0x6E), dark trousers (faces: sixth pass). Frames 49-57
  (tank gun, ripple) default; wading 16-23 AND-only: cleared pixels are the drawing, lines 0-12.
- Pass 4 (owner: no outline, "none of the yellow edge outside of the original character black outline"): uploadn's .o3
  (0x2EB5) LD (HL),15 -> LD (HL),0, the ring transparent by index; ext_det: V_DET 0 on every K1 frame but the ripple, so
  the paper border is transparent. enhanced_patch(outline=True, border='paper') rebuilds pass 3 exactly.
- Checks then: venh.py -> venh3.py (the picture classed by the default's pixel, each image against the default image of
  its key), storecheck.py (static, every frame and rotation). Their final form is venh5.py, now `set_check` (Import).
- Speed (simulator, 3.5 MHz terms a game frame, game ~200K): default hooks 80.8K on ik_2pw, Enhanced 105.7K; ik_cheat1
  55.3K vs 68.6K: the colour lookups at image upload. Not measured on a board.
- Builds of the passes kept in the run folder: out/ikari_warriors_enhanced.prev2-5.nex; PNGs out/ikari_warriors_fix*.png.
- Unpainted by design: tank gun 49-56 and the K6 hull, pick-ups, bullets, XOR figures, debris. Never seen in a recording:
  frames 19, 59-62 (painted anyway), a player drawn the normal way in 16-23 (would take enemy colours), the 0x88 mask path.

## Fifth pass: both builds, seams closed (owner on 80466c62, 2026-11-03)
Owner: "can you see that line through the player and enemy character on the left side?", then "same on the non enhanced
version, also the non enhanced version still has the outline". Byte-for-byte rule for the default lifted by the owner, Ikari
only (other games keep their outlines). Plain 2d56c304 unchanged.
- Seams: one or two pixel channels between parts of a figure (gun and arm, arm and body), open to the outside at one end. The
  enclosure rule called them outside, so once the border went they showed the background as a line. Now a seam (work/enh2/
  seams.py: a run of at most 2 non-ink pixels in a line or a column with ink at both ends, not already enclosed by ink) is
  inside, and the inside is ink, seams and what they enclose in line and column. 46 frames have seams (1,094 pixels over the
  Enhanced store's colour bases, 613 in the default's).
- Default sprite build (edge_patch, used by build()): the outline byte, V_DET 0 on every K1 frame but the ripple, the seams black
  through the colour route (docs/profiles/ikari_warriors_edges.json, 501 entries, 0xB700 + 36 f, frames 0-56 and 58-62), K5/K6
  colour keys off. Its own colours otherwise: the hook's fill gives the enclosed body the paper, as before. e740ae71
  (d6a6fce2 kept as out/ikari_warriors_sprites.prev4.nex; IkariPatch(colours={}) still rebuilds it).
- Enhanced: seams take the colour of a 4-next body pixel, else black (work/enh2/paint4.py); the tank gun's seams black.
  9ac1d501 (2a713a69 kept as out/ikari_warriors_enhanced.prev4.nex).
- Checks (work/enh2/venh4.py, MODE=default or enhanced), each K1 image on show against the approved default's pattern of its key:
  default ink 2, seams 2, enclosed paper, outside 0, no 15; Enhanced as the fourth pass with seams painted. Static over every
  frame (storecheck5.py): 0 painted pixels outside the closed silhouette, 0 seams left open, 0 enemy skin, both tables.
- Verify: default and Enhanced each IDENTICAL on all 8 recordings, 20,982 commits; hooks on ik_cheat1 e_pre/e_bl/e_post 2,853,
  e_k1 11,332, e_k2 2,209, e_k3 980, e_k4 5,762, e_k5 370, e_k6 815, e_k8 5,536. Negatives on ik_2pw, all detected. Default 4:
  the old default d6a6fce2 (65,954 outline, 106,288 outside, 12,180 seam), outline kept, paper edge kept (41,113), seams open
  (12,180). Enhanced 13: the 11 before plus seams open (12,180 seam pixels) and the fourth pass 80466c62 (12,180 seam pixels left open).
- Speed (simulator, 3.5 MHz terms a game frame, game 201K): default 104.0K on ik_2pw, 67.4K on ik_cheat1 (the approved default
  80.8K, 55.3K: the seam lookups at image upload); Enhanced 105.8K, 68.6K as before. Plain has no hooks; the 14 MHz blit gives
  back about 56K against it. Not measured on a board.
- JNext through the Browser and loader: default and Enhanced output = apply (6209cf29, 3c1c0954). out/ikari_warriors_fix4.png:
  default old and new, Enhanced old and new, JNext and same-commit simulator scenes (sand, jungle, water), the owner's two
  cases enlarged, and every frame with a seam before and after.

## Sixth pass: enemy faces (owner on a8713418, 2026-11-03)
Owner: "everything else is good, non enhanced and enhanced"; "the enemies face maybe should be pink as well". Enhanced only;
plain 2d56c304 and default e740ae71 rebuilt byte for byte.
- Face (work/enh2/face.py), the players' face rule minus the band: body pixels on head lines 0-4, not a checker hole (all four
  neighbours ink, two or more diagonals body: helmet or uniform dither); AND-only wading frames: the cleared head pixels on lines
  0-4 not next to the outside (the head's light ring stays the uniform). Every enemy frame has one (3 to 27 pixels; 61 and 62,
  never seen in a recording, take wide bands at the top). A seam next to a face takes the uniform. Table work/enh2/colours6.json.
- Check (work/enh2/venh5.py), each enemy image on show: the face from the approved default's pattern, every face pixel skin,
  no skin elsewhere. ik_cheat1: 466 enemy images, 4,021 face pixels.
- Verify: IDENTICAL on all 8 recordings, 20,982 commits; hooks as before. Negatives, all 15 detected, new: enemy without a face
  (708 images; the fifth pass), skin on all of an enemy's head lines (52 pixels outside the face).
- Speed unchanged: ik_2pw 105.8K, ik_cheat1 68.6K (simulator, 3.5 MHz terms a game frame).
- Enhanced 22be808b (9ac1d501 kept as out/ikari_warriors_enhanced.prev5.nex). JNext, real loader, Enhanced on: output = apply.
  out/ikari_warriors_fix5.png: every frame before and after (enemy and player rows), play frames at the same commit, JNext.

## Defaults taken (a human would have decided)
1. Every figure a sprite, all 7 plotters. 2. Scenery, HUD, text and the stipple on the ULA. 3. Depth: the plot order, sprites over all scenery. 4. Body colour: the paper under the centre, yellow in place of green. A new look on green terrain, for the owner to judge. 5. XOR figures by bank, as above; debris red. 6. White outline and fill on K1 but the ripple; none on K2, K4 (small), K3, K8 (not solid), K5, K6 (K6 fills its 32 pixels, so has no room). 7. Controls and tail choice as above.

## Colour route
sheets/ in the run folder; `nexclash.py recolour` works (test painting: banks 13-15 only, 1,757 entries, seen in JNext). Paintable: K1 except wading and the AND-only variant, K5, K6. Not paintable: K2, K3, K4, K8. Index 1 is "the paper under the figure". Nothing painted by default.

## Lessons
- [local: a buffer that is exactly one MMU slot lets a page swap do the work] Blit from a second page and run plot bodies on a third with no code change.
- [local: LDI's flags 3 and 5 depend on the byte copied] A blit whose source changes differs there; check the bits are dead rather than masking all of F.
- [local: the picture check found an original glitch] Torn lines came up as a mismatch, explained by the plotter's carry test.
- [local: a clean copy need not exist in the game] The moment before the first plot of a frame gives one, when the erases are exact reverse order.
- [local: stack writes by a hook show in lockstep] A hook that CALLs on the game's stack changes dead bytes; the hide hooks were made stackless.
- [local: this engine's default changed route at the fifth pass] observed (import, 2026-11-04): recolour() still checked
  a build against IkariPatch(colours={}), so it refused the approved default (edge_patch, e740ae71) and the
  recolour guard caught it. Now it checks against edge_patch() and paints over the edge table; no build changed.
- [local: this engine's builds since the fifth pass need their own picture classing] observed (import, 2026-11-04):
  the first full verify failed picture! on all 16 runs; the approved builds had been verified by venh5.py, which
  replaces compose(). Now in the engine.
- [local: the approved builds came from run-folder scripts] observed (import, 2026-11-04): the clone's record held the
  first-pass MD5s (d0e7d8b5); the .nxc's default and Enhanced came from work/enh2/mkenh6.py. Moved into auto.

## Technique use
- detect.gameplay-screen-readers: helped: no logic reads the buffer's pixels.
- detect.tracked-unit: helped: one call draws one whole figure.
- optimise.pattern-cache: helped: 32 images, none taken while on show in any recording.

## Hardware checklist
1. Loads to the loading screen; SPACE, 5, SPACE, 4, ENTER, 1 starts. 2. Figures scroll with the scenery, no lag beyond a frame, nothing outside the window. 3. Jungle edge: no half green figure. Water: pick-up boxes solid. 4. Speed against the plain build. 5. GAME OVER: no sprites left on the title.

## Stage log
- 2026-11-03 stages 0-3 in one session (pilot, unattended), under 90 minutes, 0 user rounds.
- 2026-11-04 import into `refactor` (phase 7, group 3): Enhanced build and negatives moved into auto, recolour fixed,
  pinned; rebuild = .nxc v1.0 byte for byte; full verification stamped. 0 user rounds.

## Friction
- reuse: [none: the engine needed no shared helper to rebuild its bytes]
- retries: [local: the recolour guard caught a stale check in this engine] one rebuild failed until recolour() followed the fifth-pass default.
- environment: [none: the pinned sjasmplus gave the profile's bytes]
- hand-rolled: [none: no scratch tool kept]
- scratch: [none: the colour-set checks stay in the run folder, named under Import]

## Open
- Hardware, CSpect: never run. Level end (0xF214 site) never reached; only level 1 up to the second bunker, no tank driven by the player seen in the recordings' frames.
- ROM bytes at 300, 1020, 1090, read by debris and stipple: the card's enNextZX.rom ROM 3 and 48.rom are the same there (compared); no real Next run.
- Scenery colour: attributes scroll in 8-line steps while pixels scroll in 2-line steps (2,270 of 2,853 commits are off a cell line), so colour edges jump against their pixels. It is the game's scenery, on the ULA. Sprites cannot fix it; it would need the scenery on Layer 2.
