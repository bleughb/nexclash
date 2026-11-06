# Nightshade (Ultimate Play The Game, 1985, 48K) - engine `nightshade` (batch game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: imported into nexclash 2026-11-04 (ported from Jon Attree's .nxc work, 2026-11-04);
selftest --verify --stamp PASSED in this tree; JNext only, never on a Next.
Inputs: specnext/reference/nightshade/ (nightshade.z80 = archive "[a][a].z80", md5 7b4e8280; a1, a2, rec1, rec2 .rzx;
nightshade.tap = archive "[a][a].tap" for the loading screen). Pilot run folder: runs/nightshade.
Start with: the end-to-end run of the refactored pipeline (pilot NEXCLASH-CHANGES.md, "Final step"), from "Import" below.
Published .nxc: none yet. The owner-approved candidate is runs/nightshade/out/nightshade.nxc b8c3754c (round 6, no
version field), held for the end-to-end run; publish as v1.0 (or v1.1 after the end-to-end, as the owner decides).

## Inputs
Archive "Nightshade (1985)(Ultimate Play The Game)[a][a].z80", md5 7b4e8280896d7ff34b93e83ddba9d01c: 48K, stopped in the
title menu's tune (PC 0xC68B, DI, IM 1). The plain release (md5 2e445cac) stops at PAUSE in the BASIC loader with the code
still scrambled (RLD + LDIR at 0x5B80); its .nex does not leave the PAUSE in JNext, and a patch from it would carry the
decoded game, so it is not used. No 128K release exists. Keys: menu 0 start, 5 directional control; keyboard rows
A-ENTER walk, Z-V turn, B-M fire.

## Clash check (owner: clash; measured)
No menu option changes the drawing. Filmation II composes a mono buffer (0xE5C6, 24 bytes a row, 112 rows bottom-up, 22
columns shown) and an attribute buffer (0xF046), blitted by 0xE148 / 0xE1AD. Figures have no colour of their own: they show
in the scenery's attribute (white floor, cyan walls); the hero's 2 x 4 cell box (0xC898 from 0xBEC4) paints his health colour
(table 0xC065 by 0xBBF3: white, yellow, green) over whatever is behind him. Kind A. At every blit (work/clash_check.py):
a1 44.8 % of figure plots span more than one ink, 9.7 % of visible figure pixels (65,021 of 671,717) in another colour than the
figure's own; rec1 36.2 % / 8.5 %.

## Design
The game's plot is kept: every byte of game memory as the original's. Hook 0xE45E (LD (0xBBAE),SP, after the clip) runs
the game's own plot loop 0xE4C9 a second time into a zeroed scratch buffer in Next page 26 (slot 1 during hooks) and keeps
the figure's ink, offset, size, type. Hook 0xE200 (CALL of the blit): each figure's ink AND the final buffer -> 4-bit 16 x 16
sprites over the ULA, rows past 111 and the hidden columns 22-23 left out, a figure left of the window (offset -2) placed
by its real columns. Colour: bright white (the floor's ink), the hero (records 0xBC8E, 0xBC9E) his health colour. Hook 0xBEC4:
the hero's box is not painted (registers as 0xC898 leaves them). Hook 0xE59D (the screen clear): sprites off.
Every hook leaves R as the original would (the game reads R at 0xC1F4, 0xC5C2, 0xDA61, 0xDDF4 for random numbers).
RAM stubs 0x5B4F-0x5B76 after the start-up tail (0x5B00-0x5B4E); keep_printer_buffer puts them back after NEXLOAD.
Outline: none added; the game's own mask already draws a black edge round every figure, which the ULA still shows.
Enhanced (off by default, no .256 exists): row bands per figure group from the top (ENH_GROUPS in nightshade.py), one painted
palette at offset 1, the hero at offset 8 + health colour so his tunic still shows his health. Every graphic 0x02-0x97 was
drawn with the game's own plotter (work/enumg.py, png/allg.png); contact sheet before / after png/enh_sheet.png.

## Results (2026-11-04, simulation and JNext only)
| Build | MD5 |
|---|---|
| out/nightshade.nex (plain) | e4d954de899563af241cb8db84114654 |
| out/nightshade_sprites.nex | 60d29bd0157552f8b1970d0289eaae24 |
| out/nightshade_enhanced.nex | dbef8cd145e40bf268d032d32cf9a0fd |
| out/nightshade.nxc | b8f43c35fd457f1d92b6395cab5677c7 |
Replay (work/v1.py, default and Enhanced): a1 9010 frames, a2 9028: IDENTICAL; figure hook 4817 / 4709, blit 1776 / 1765,
hero box 1776 / 1765, clear 1 / 1, list full 0. Earlier recordings from the derived menu state (rec1, rec2) also IDENTICAL.
Negatives 11 / 11 DETECTED (work/nega.log). Boot check OK, with and without NEXLOAD. JNext: plain, sprites, Enhanced reach play,
scenery at the same place at frames 500 and 700 of one walk in plain and sprites. Real loader (work/nxcrun.py, copy of
card_test10.img): default, Enhanced, Enhanced + Infinite Lives MD5 exact with apply.

## Open
- Coverage: town streets and doorways only; interiors, weapons, bosses, the end not reached.
- Loading screen not added. Colour sheets / RECOLOUR not made (palette table only).
- Cheat Infinite Lives sets the counter to 3 at each loss (as the .pok does); Alt lives and Infinite Energy did not hold in
  the simulator and are left out; the weapon slots need a value and are left out.

## Stage log
- 2026-11-04 stages 0-3 + Enhanced, one session (batch, unattended), about 2.5 h, 0 user rounds.
- 2026-11-04 import into nexclash (phase 7, group 2): auto, loading screen in the engine, record, stamped verify; 0 user rounds.

## Round 2 (2026-11-04, coordinator's asks)
- Loading screen added: [a][a].tap's 6,912-byte block (all three tapes alike, md5 758792b8), runs/nightshade/loading/mk.py
  with Rambo's stub: bank 5's screen area holds it, entry bank 23 restores bank 5, 250 frames or a key. Real loader on a copy of
  card_test10.img: shown at frames 3624-3704; at the original start registers, MMU and RAM 0x4000-0xDFFF equal the build
  without it (0 bytes differ); Enhanced differs in 134 bytes (its palette). out/nightshade.nxc 2f0258d0 (prev b8f43c35).
- Enhanced repainted by parts (nexclash/nightshade_paint.py), replacing the bands: each graphic classed from its own
  ink and mask (outline, fill, inner detail, enclosed regions; holes filled only where the type asks: faces, mouths, eyes,
  never the gaps of a cloak or a swirl), codes 1-7 = ink + 2 plane0 + 4 plane1. The two planes are stored in the game's
  graphic format in banks 15-, turned to the mirrored orientation by the game's own flip routine, and run through the game's
  own plot loop at each figure with its clip and shift, so a flip or shift cannot misplace a colour (bit 7, rows reversed,
  never occurs at a plot; such a figure would keep the plain colour, counted). Hero: hood and cloak grey, face skin, tunic
  in his health colour. Records moved to page 28 at slot 0 (interrupts off). Planes are in both builds; the set changes
  71 bytes. Replay IDENTICAL a1 / a2, default and Enhanced (every figure painted: 4817 / 4709); 12 / 12 negatives;
  real loader exact: default a94ebbb5, Enhanced a64a6a6e, Enhanced + cheat edb4c795; loading screen: 0 of 40960 bytes
  differ from a build without it. out/nightshade.nxc 4b7ebce4. Sheet png/enh_sheet.png, play png/enh_play.png.

## Round 3 (2026-11-04, owner: "super blinky between frames")
- Cause (JNext headless, one PNG per video frame, work/blinkrun.sh, frame log of 0xE200 / 0xE203): the old blit hook
  switched every sprite at 0xE200, then the game's own blits took 295 lines (0.95 frame) at 3.5 MHz, bottom-up. For the
  1-2 video frames between them the new sprite lay over the old ULA figure (the figure is also drawn in the ULA, in white
  on the floor), so each animation step showed a merged blob: frames 401, 407-8, 413-4, 419-20 = exactly the frames from
  a commit to the blit's end (png/blink_before_monster.png). Default and Enhanced alike (Enhanced: white old legs through
  the painted ones). The pattern slots were also rewritten in place while shown (no double buffer), a smaller effect.
- Fix (asm h_commit, now in a second code block at 0x3700 of the hook page): patterns go to the half of the 4-bit pattern
  memory no sprite shows (0-63 / 64-127, flipped each frame; 64 tiles a frame, never exceeded on the recordings), the
  attributes to a table; the hook waits until about the time the original's blits would end (WMIN 232 lines from its
  start) and for the beam on lines 132-278 (60 Hz 230), below the play area (rows 16-127), runs the game's own two
  blits (0xE148, 0xE1AD) at 28 MHz with the registers and SP the original's CALLs see (43 lines), then sends the
  attribute table in one burst, and returns to 0xE206 with R (55 M1 from 0xE200, mod 128), SAVESP and the stack word
  0xE206 as the original. Game logic byte-exact; game memory including the screen compared at 0xE206.
- Model checks added: the screen is final before the first sprite attribute write of a blit hook; no pattern upload
  into a pattern a shown sprite uses; a model beam answers NEXTREG 0x1E / 0x1F reads in hooks.
- Results: replay IDENTICAL, default and Enhanced, a1 / a2 / rec1 / rec2 (work/vf_*.log, vfe_*.log): figure hook
  4817 / 4709 / 5711 / 5504, blits 1776 / 1765 / 1945 / 1947. Negatives 15 / 15 DETECTED (work/negf.log), new: switch
  before the blits, one pattern buffer, R off after the blits. JNext 300 frames of play (work/blinkstats.log): one
  play-area change per game frame (62 / 62 default and Enhanced; old build 144 / 57 and 129 / 57; plain 94 / 52, its own
  tear), fast blits start on lines 132-277 and the switch ends by line 7, 0 of 212 in the play area. Time 0xE200 -> 0xE206:
  mean 465 lines (old build 591, original 295; the rest is the pattern build, as before), so the game runs a little
  closer to the original's pace than the build the owner played.
- out/nightshade.nxc 9cfac0dd (prev 4b7ebce4 kept as out/nightshade.prev_4b7ebce4.nxc, older b8f43c35 as .prev.nxc):
  apply exact, sprites 1cf6b276, Enhanced a74b8a68; real loader on a copy of card_test10.img exact for default,
  Enhanced, Enhanced + Infinite Lives (738b43be); TAP1-clone nxc.py: --bare 1cf6b276 / Enhanced a74b8a68, menu .nex
  f37ef16e shows the menu and starts the game in JNext. Strips: out/nightshade_fix.png, png/blink_*_before_after.png.
- Open: real hardware unseen; the line numbering (NR 0x1E / 0x1F, line 0 = top pixel row) and 28 MHz blit time are
  JNext's. At 60 Hz the pace estimate counts 264 lines a frame; 48K timing (312) is off by a line a frame, harmless.

## Round 4 (2026-11-04, owner: Enhanced redesign by the CPC's parts)
- Ask: redesign the optional Enhanced set. Jon: the Amstrad CPC version, "although i dont love the colour choices it
  should where the separation of clothing items are": the CPC gives the part boundaries, our palette the colours. No white
  outlines or edge highlights. Studied (local only, never published): refs/nightshade_cpc/cpc_01..20, the status panel
  (hero, skeleton, reaper, monk, ghost large) and the play areas (horned demon, spiky head, fire demon, slug, domes).
- nexclash/nightshade_paint.py is now v3; v2 is frozen as nightshade_paint_v2.py. The default build carries the v2
  planes (unused there) and the v2 offsets table, so the default .nex stays byte-identical (1cf6b276); the Enhanced build
  carries v3 (same plane sizes, so the same plane table; the hook page and code are unchanged).
- Hero (CPC: hood / face / bare arms / short belted tunic / bare legs / feet): per-graphic part maps in the stored
  orientation (HERO_UP: hood row, face box, arm boxes, collar; HERO_LO: hem row, boot row), flipped with the planes by the
  game's own routine (all 176 mirrored planes checked to be mirror images). Mail hood (silver-grey), face skin with its
  gaps shaded, skin arms and legs, tunic (torso and skirt) in his health colour white / yellow / green, leather belt
  (the black waist band under the torso) and boots, silver buckle on front views, a dark red collar trim. The skin
  shades sallow then sickly with his health; the mail stays silver.
- Families (one palette each, features contrasting, no rims: an edge pixel takes its part's colour): ghost pale
  blue-white, wisp tail darker, red eyes; mad monk brown robe, skin face, pale rope; reaper violet-black robe, bone
  skull, steel blade; skeleton bone, red eye sockets; gremlin green, red maw, yellow-green feet; slug green; spiky head
  orange with gold spikes and feet, glowing mouth; fire demon orange with gold flame tips, glowing mouth; horned demon
  and crowned imp red hide, bone horns or crown points (thin ink in the top rows), leather feet, gold eyes; jellies mint
  with a darker crescent and base; items: bible red and gilt, crucifix gold, mirror steel and glass, hammer steel head
  and wooden haft, other pickups leather; shots gold; swirls and sparkles pale blue. Families sharing a palette offset
  share its codes, allocated by colour (4 ink and 3 hole colours an offset).
- Silhouettes: every painted pixel lies in its graphic's ink or mask, ink codes only on ink (work/v3/silhouette.py);
  a see-through gap stays see-through (the ghost's eyes as in v2).
- Sheet png/enhanced_v3_sheet.png (v2 beside v3, 4x, over black and over cyan / yellow brick, the hero composed at his
  three health colours). Results: replay IDENTICAL default and Enhanced, a1 / a2 / rec1 / rec2 (work/v3/logs/v*.log),
  hooks figure 4817 / 4709 / 5711 / 5504, blits and hero box 1776 / 1765 / 1945 / 1947, clear 1 each, every figure
  painted in Enhanced. Negatives 16 / 16 DETECTED (work/v3/logs/neg_*.log; margin columns over the whole of a1), new:
  hero part maps dropped. JNext: no-blink check 62 changes / 62 blits, switch 0 of 210 in the play area
  (work/v3/blinkstats.log), strip png/enhanced_v3_strip.png; real loader on a copy of card_test10.img exact for
  default 1cf6b276, Enhanced b006e03f, Enhanced + Infinite Lives 9c89426b; TAP1 nxc.py --bare 1cf6b276 / b006e03f,
  menu .nex b543b1bf: menu, Enhanced on, play (png/enhanced_v3_menu_play.png).
- out/nightshade.nxc 8983d5d7 (prev 9cfac0dd kept as out/nightshade.prev_9cfac0dd.nxc); the Enhanced set is now
  19152 bytes in 5 banks (was 4167 in 2), since the planes differ from the default build's.
- Open: bosses, interiors and most monsters seen only on the sheet; the part maps for side and back hero frames
  (2F, 26, 27) are read off the pixels without a CPC view of those frames; real hardware unseen.

## Round 5 (2026-11-04, owner played 8983d5d7: "this look awesome!"; "the back of his helmet is the wrong colour")
- Cause: the back-view part maps (16, 20, 21, 22, 23) ended the hood at row 12 and the three-quarter-back 26 at row 12,
  so the hood's lower back (rows 10-11, above the diagonal fold line across his back) took the tunic's health colour.
  Fixed: hood down to row 10 (back views) and row 11 (26); the tunic starts under the fold line. Front views (collar
  line), 2E, 2F and 27 were already right. Skin by health unchanged (owner's question pending via the coordinator).
- Mirrored copies: the sheet now draws every hero pair mirrored from the build's own flipped planes, at the three
  health colours (png/enhanced_v3_sheet.png, "checked"); back-view crops at 4x over black, stored and mirrored,
  white / yellow / green: png/enhanced_v3_backviews.png. JNext back views in play: png/enhanced_v3_back_jnext.png.
- Results: replay IDENTICAL default and Enhanced, a1 / a2 / rec1 / rec2, hooks as before (figure 4817 / 4709 / 5711 /
  5504, blits and hero box 1776 / 1765 / 1945 / 1947, clear 1 each, every figure painted); negatives 16 / 16 DETECTED
  (part maps dropped included); no-blink 62 changes / 62 blits, switch 0 of 210 in the play area. Default .nex still
  1cf6b276; Enhanced 2706282f; real loader exact default, Enhanced, Enhanced + Infinite Lives (581efc01).
- out/nightshade.nxc 8ffb02c6 (prev 8983d5d7 kept as out/nightshade.prev_8983d5d7.nxc). Note: nexclash-patch's
  nxc.py (changed 12:39 by someone else) now writes the menu .nex by default; pack checks use --bare.

## Round 6 (2026-11-04, owner and Dean Woodyatt after 8ffb02c6)
- Asks: collar the hood's grey (Jon); "the run before coloured the bottom of the helmet the colour of the tunic. the
  sleeve has the same issue" (Jon); "You can tell the AI is obsessed with attribute blocks and doesn't recognise the
  pixels for the arms / sleeve border" (Dean). The maps cut parts by row bands and boxes, not along the drawn lines.
- Hero maps redone by drawn regions: each 4-connected ink region the artist's mask lines close off takes one part
  (seeded per graphic, work/v3/comps.py lists them): hood regions mail, face and forearm/hand regions skin, the torso
  region with its sleeves tunic, the skirt region tunic, leg regions skin, foot regions leather. A region is split only
  where its drawn shape changes: the back views' shoulder band (rows 10 and up, row 9 up to the sleeve's vertical line)
  mail; 16's raised arm along the arm strip's edge lines; 2E's chin; legs that run into their boots at the ankle's
  narrowing. Collar mask line and the back shoulder band in the coif's mail (no red left on the hero).
- Checked every hero pair stored and mirrored at three health colours (png/enhanced_v3_hero_all.png, 4x; back views
  png/enhanced_v3_backviews.png; sheet png/enhanced_v3_sheet.png); JNext back and front in play
  png/enhanced_v3_back_jnext.png.
- Results: replay IDENTICAL default and Enhanced a1 / a2 / rec1 / rec2, hooks as before; negatives 16 / 16; no-blink
  62 / 62, 0 of 210 in the play area. Default 1cf6b276, Enhanced 37f97001; real loader exact default, Enhanced,
  Enhanced + Infinite Lives (25f13ef0); TAP1 nxc.py --bare exact. out/nightshade.nxc b8c3754c (prev 8ffb02c6 kept as
  out/nightshade.prev_8ffb02c6.nxc; the held collar-only build as out/nightshade.held_b7773e4e.nxc, never released).

## Import (2026-11-04, refactor phase 7: ported from Jon Attree's .nxc work)
- From runs/nightshade/nexclash (clone of d7abd1c, commits 9a016fb..f6c8577): nexclash/nightshade.py, nightshade_paint.py
  (Enhanced v3), nightshade_paint_v2.py (frozen v2: the default build carries its planes, so the default .nex stays
  byte-identical), asm/nightshade_hooks.asm, docs/profiles/nightshade.json, this file. The clone changed no shared code
  (only the atomic-switch card's examples, not carried over). Three own modules, not one: the record lists them all.
- Added for the repo: `auto` and `unit_tests` (ENGINE_CONTRACT; the clone drove verify from work/ scripts), and the loading
  screen, which the pilot added after the build (runs/nightshade/loading/mk.py, sjasmplus on PATH): its stub is now
  MODULE ldscr in asm/nightshade_hooks.asm (blocks lstub, lfinal: byte-equal to the pilot's stub.bin), and
  `add_loading` writes the file exactly as mk.py did. The screen comes from the tape beside the snapshot
  (`find_screen`: a .tap / .scr whose 6,912-byte block has md5 758792b8); without one the build has no loading screen
  and its MD5 differs from the approved one. `loading_check` compares the file with its base and runs the stub on a
  model (no key; a key at frames 40-60) to page 20's 0xC000 with bank 5, registers, SP, stack word, MMU and 0x243B as
  the base starts. nextboot.boot ignores the entry bank, so the boot check runs on the base .nex.
- New defaults: no alt ROM (RAM stubs + Next pages), R already kept, tail 0x5B00 proven by the ROM path check: nothing to
  pin. The record has no "pin".
- How it runs in today's tree:
  - rebuild: `python nexclash.py auto --no-nxc nightshade.z80 --no-record -o OUT` (the .tap beside it): plain e4d954de,
    nightshade_sprites.nex 1cf6b276 (base f10e5820), nightshade_enhanced.nex 37f97001 (base 0d852aa3), under a second.
  - verify: `NEXCLASH_MAINTAINER=1 NEXCLASH_REFERENCE=<specnext/reference> NEXCLASH_NEXT_ROM=<enNextZX.rom> python
    selftest.py --game nightshade --verify --stamp` = auto with --rzx a1 a2 rec1 rec2: 8 replays (default and Enhanced)
    and 16 negatives in worker processes (about 3 min), then nexclash.py's ROM path check (350 s on this machine).
  - .nxc: `nexclash.py auto` without --no-nxc packages the sprite build (nxcout); the approved .nxc was made by
    nexclash-patch's nxc.py from the two .nex (runs/nightshade/work/v3/pack.sh) with the .pok's Infinite Lives.
- Results (2026-11-04, this tree, stamped): approved .nxc b8c3754c `--bare` = 1cf6b276 default, 37f97001 Enhanced: the
  rebuild equals both. Replay IDENTICAL: a1 9010 frames (figure hook 4817, blits 1776, hero box 1776, clear 1), a2 9028
  (4709 / 1765), rec1 9010 (5711 / 1945), rec2 9028 (5504 / 1947), default and Enhanced, every figure painted in
  Enhanced. Negatives 16/16 DETECTED. Boot OK with and without NEXLOAD; loading stub OK both ways.
- ROM path check (NextZXOS ROM3 modelled, md5 8c34d957): every build is a plain-ROM build (the Next's own ROM3 runs), and
  192-231 ROM bytes the game runs or reads in each recording differ from Sinclair's (0x0550-0x06A7: LD-BYTES / SAVE
  area; reported, not a fault by the check's rule). JNext ran the game on NextZXOS's ROM with no fault seen; still a
  question for the end-to-end run (an alt ROM image would make those bytes Sinclair's).

## Hardware checklist
1. Loading screen from the tape, a key or 5 s, then the title tune and menu; 0 starts.
2. Hero and monsters as sprites over the scenery's colours; the hero in his health colour (white, yellow, green).
3. No merged blobs at each animation step (the blink fix): figures switch with the scenery.
4. Enhanced (menu option): hero by parts (mail coif, skin, tunic in his health colour, belt, boots); monsters painted.
5. Rooms change cleanly; no sprites left after a screen clear; game over and a new game.

## Lessons
- [local: the pilot added the loading screen after the build with its own script] An approved build made of the
  engine's output plus a post-step is rebuilt only if the post-step is in the engine: stub source in the .asm, the screen
  from the tape beside the snapshot, a model run of the stub.
- [local: Nightshade's verifiers ran from work/ scripts] The clone had no `auto` / `unit_tests`; the negatives were
  replays of broken builds, so `unit_tests` here runs them (1500 frames each, the margin one the whole recording).
- [deferred Open: reconsider when the end-to-end run reaches the ROM path stage] The ROM path check reports 192-231 ROM
  bytes per recording that differ on NextZXOS's ROM3 (0x0550-0x06A7) in a build with no alt ROM image.

## Technique use
- patch.display-atomic-switch: used: the blit hook runs the game's blits and switches the sprites with them (round 3)

## Friction
- reuse: [local: rebuild, boot check and ROM path check are today's shared code; only the loading wrapper is new, kept in the engine]
- retries: [local: the stub model first read line values above 255 (NR 0x1F holds the low 8 bits); fixed before the run]
- environment: [local: NextZXOS's ROM for the ROM model is runs/altrom_audit/rom/enNextZX.rom; set NEXCLASH_NEXT_ROM]
- hand-rolled: [local: tape block reader (find_screen) in the engine; Knight Tyme's import carries a .tzx one]
- scratch: [none: no scratch scripts kept; the import's checks are in auto]
