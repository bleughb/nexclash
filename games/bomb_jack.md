# Bomb Jack (Elite Systems, 1986; 48K) - engine `bomb_jack` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended; never run on a Next or in CSpect.
Inputs: the pilot's run folder (bomb_jack.z80 md5 08e760e8, recordings work/reference/bomb_jack/*.rzx)
Start with: hardware checklist below on a real Next (JNext passes, work/jn.sh); then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `detect.gameplay-screen-readers`, `detect.tracked-unit` (recipe and results: docs/records/bomb_jack.json)

## Inputs
Snapshot: archive file "Bomb Jack (1986)(Elite Systems).z80" (ZXDB 0000617), md5 08e760e82721540898b57b8a1f277659. 48K, PC in ROM PAUSE with the
loading screen up, IM 0, then USR 0xC14B. It reaches the game: any key -> menu, 1 -> level 1.
Keys: N left, M right, Q jump, A down (menu K, the default). No Fuse and no human: recordings from `nexclash.py record --script`:
- bj_play: search bot (work/bot.py: greedy depth 2 over held keys), no cheat: level 1, three deaths, game over, title, high scores.
- bj_random: random held keys, no cheat: power ball up, game over.
- bj_pow1, bj_pow3: the bot, also chasing balls and coins; layouts 1 and 3, 9 lives. pow3 reaches power mode.
- bj_lvl01-12: the bot, 2,200 frames per layout, 9 lives.
Cheat snapshots (work/mkcheat.py, embedded in the RZX, never built): the real game at level 1 with data pokes only: layout and background
counters, lives 9, one bomb left and Jack on it, so the game clears the level and loads layout k itself.

## Snapshot facts (PLAYBOOK 0b)
`inspect`: loader state, IM 2 from 0xC177 with I = 0x39: the vector is read from ROM 0x39FF-0x3A00 (FF FF), JR at 0xFFFF -> JP 0xC38C at 0xFFF4.
Those two bytes sit in the alt ROM's free range (see Lessons). 0x5B00-0x5FFF holds graphics, copied from 0x7300 by 0xEB81 at boot: no tail there.

## Rendering model (PLAYBOOK 2): masked plots from a clean copy
Screen copy at 0x6000 (screen address + 0x2000), taken by 0xD98F at level start. Everything drawn in the IM 2 handler, DI at 0xC38C.
| Thing | Plot | Into | Notes |
|---|---|---|---|
| 11 objects (Jack 0, ball 1, coin 2, enemies 3-10) | 0xD929 loop -> 0xD9B5 per object, descriptor 62121.. | ULA only: (copy AND mask) OR gfx; old box = copy | state 0 off, 1 move, 2 first plot, 3+ erase |
| bombs (24) | 0xE582 from 0xD6E3 (level), 0xC860 (lit, top 6 rows); 0xE646 restores (0xC68B collected) | ULA and copy | x bits 1-2 pick the lit frame |
| score labels | 0xE582 from 0xC6C4, 0xE646 from 0xC742 | ULA and copy | |
| platform tiles | 0xD789 from 0xD8A8, 0xD8CF, 0xD8F5: 8x6, overwrite | ULA only, before the copy is taken | level start only, 15 tiles |
| scenery, HUD, text | 0xE6F6, 0xE9F4 | ULA | |
Graphics: 96-byte blocks, 16 rows x 3 (mask, gfx) pairs, odd rows right to left, x AND 6 picks one of 4 blocks (shifted and animated by hand, so not plain shifts).
Attributes: no figure ever writes one. In all 12 layouts every play-area cell has ink 0, so every figure, bomb and platform is black ink + the local paper as its fill.
Readers: lockstep proves no logic depends on figure pixels on the ULA (0xD998 copies the screen only with no figure up).

## What clash this game has, and what the build does about it (the coordinator's question, on the owner's observation; answered plainly)
The game has no attribute clash in the usual sense: nothing changes a colour cell for a figure. It avoids that by giving up figure colour. What remains is block-edged fill: a figure,
bomb or platform shows each cell's paper in its fill, so its fill changes colour at cell edges, and figures have no colour of their own. See "Census" in Results.
- Removed: block edges on figures, bombs and platforms (fill is one colour per sprite).
- Added, not clash removal: figure colours. This is most of the visible change: red bombs, blue Jack. They are this session's choice.
- Not touched: the scenery is drawn in cells and keeps its block edges (the pyramid's edge, the sphinx). A sprite build cannot change that; it needs a painted Layer 2 sheet from a human.

## Colours (docs/COLOURS.md route; owner: match the arcade, screenshot supplied through the coordinator)
Sprite palette, indices 1-15, fixed (`PALETTE`); patterns = kind default + colour map, key G<address of the graphics byte> or T<tile byte>, bit = pixel. Sheets from the snapshot, every block and tile (`python -m nexclash.bomb_jack sheet`); `RECOLOUR` rewrites bank 11 only unless the patterns' dedupe changes (bank 12's two tables). The painted sheet is a script's work on a copy of the PNG (work/paint_arcade.py), not a person's: COLOURS.md says pixel art is the user's, and this is a stand-in. No colour knowledge in the engine.
Painted: Jack (blue head rows, red body, white legs; face white inside, outline black), walkers (white, black visor), bombs (yellow fuse, red, white highlight, dark red outline), platforms (yellow to orange by row, upright ones by column, rounded ends transparent), flyers (grey, red inside: read from the picture, unsure). Unpainted, defaults, guesses for the owner: saucers, birds, balls, coins, stars.
Falls short of the arcade: scenery unchanged, cyan sky not blue, no backdrop or border, 200 labels black on the ULA; a painted band is by row, so slanted Jack frames colour less well; 16 pixels and 15 colours; pattern memory is full at 128 of 128: a painting that needs more is refused.
Results: recolour took 0.47 s; bomb_jack_sprites_painted.nex 2fc51340db2620faea38d42ed029e75d, bank 11 only differs from the base build. JNext: gameplay, png/jnext_painted_vs_arcade_f1600.png. Replay verification ran on the base build; the painted build was not replayed (route: colours only).

## Patch plan (STANDARD 4-5; cards opened: 2)
detect.tracked-unit: one 0xD9B5 call moves one figure (one 96-byte block); one 0xE582 call one bomb. detect.gameplay-screen-readers: nothing decides on ULA pixels.
No card covers "run the plotter on a blank figure": design from table 4. patch.scratch-redirect rejected: the routine needs no redirect, only other graphics.
patch.xor-overlay-keep-ula idea used for bombs and tiles, without XOR: the ULA keeps them and a solid sprite covers exactly those pixels.

## Start-up (found in JNext after the first PROVEN, 2026-11-02)
The snapshot is in the middle of BASIC line 1: PAUSE 0, CLS, RANDOMIZE USR 49483. The ROM the .nex selects (ROM3) comes from NextZXOS, and in JNext's copy 6,423 bytes differ from Sinclair's: 0x1B3A-0x1B5E are 3B (DEC SP), 0x1B5F C7 (RST 0), so STMT-RET at 0x1B76 is gone. Trace (jn/t3.x, jn/m4.log): key -> 0x1F53 -> 0x1B76, DEC SP.. -> RST 0 at 0x1B5F. Plain: NextZXOS resets (jn/plain.log). Sprites: same RST in the alt copy, hang at 0x3BEF, title stays. RAM at 0x1F3E = snapshot, tail bytes aside; SP is 0x6EB8, not the top 16K; IM 0 takes RST 0x38 correctly: those suspects are excluded.
Fix: both builds write the WHOLE alt ROM image, Sinclair's 48K ROM (`altrom_low`, Cauldron's method) and restore the printer buffer NEXLOAD overwrites. The game itself, after USR, runs only ROM bytes that are the same in both (work/romcov.py).

## Build design
e_mov (0xD94B): sets the object's two sprites (24 pixels wide: left + right pattern), points (62130) at a blank block (mask FF, gfx 00) minus the variant offset, runs the game's own
0xD9B5 on it, restores (62130) and (64985). The ULA gets the copy's bytes in both boxes, same path, same work, so timing moves only by the hook's time. Unknown graphics: left alone, the original plot stays on the ULA.
Bombs, tiles: 0xE582 / 0xD789 run as original, one sprite on top. Bomb collected: hide. 0xEC21: all off, layer off, tile counter 0. 0xC362: layer on. 0xC457: layer off during GAME OVER.
Memory: alt ROM image 1 whole: Sinclair's ROM + hooks at 0x386E-0x3C68 (0x39FF-0x3A00 kept FF), banks 12; hook byte 0x6E40 and tail 0x6E00 in the copy: `scan` shows first access is the write at 0xD998 (work/scan_tail.log). Patterns in bank 11, at most 128 (the build refuses more).
Slots: tiles 0-63, bombs 64-87, figures 88-109: the game's own order. A layout has up to 55 tiles seen; past 64 a tile stays on the ULA.

## Defaults taken (a human would have decided these; PLAYBOOK 3c, not asked in this pilot)
1. Every figure a sprite: objects, bombs, platforms. Default, extended to platforms when the coordinator asked, relaying the owner's observation.
2. Scenery, HUD, score, text, score labels stay on the ULA. Default.
3. Depth: game's own order. Default. Figures no longer cut each other: the original's later plot erases the earlier figure's overlap, sprites show both.
4. Colours: NOT the default. The default (cell ink) is black everywhere, so on the coordinator's instruction (not the owner's) figures got own colours, chosen by this session without a human, now the build's defaults:
   Jack blue/white, flyers magenta/white, walkers purple/white, saucers green/black, balls yellow/black, birds dark green/white, bombs red/black, coins yellow/black, stars and tokens white/black, platforms black/grey (ink/fill).
   The owner's only colour instruction: match the arcade (see Colours).
5. Menus: PLAYER n START and GAME OVER: sprite layer off while up (default 5), so on GAME OVER the figures disappear; bombs and platforms show from the ULA.
ALWAYS-ASK, decided here: solid figures (mask 0 pixels solid in the fill colour); original's one-frame ROM garbage at each spawn (state 2, pointer 0x2710 etc.) kept on the ULA; figure kinds from the sheet, by eye.
Skipped: knowledge refresh `git fetch` (pilot rule); colour sheets and recolour not built.

## Verify (what it checks)
Per site, original vs patched from the same state: all registers but R / T / MEMPTR (at 0xD94E also A, F, B, C: they end on the last graphics pair; see Lessons), memory outside the ULA,
dead stack and the hook byte. Figures: every screen byte the original wrote = copy + the object's sprites; patched ULA = copy; first plot of each block and x: the same run on a copy of all ones, which separates
solid from see-through pixels. Bombs: plot unchanged, sprite pixels = the plot. Tiles: sprite = the 8x6 tile. Palette offset 0, figures and tiles; pixel colours are not checked by replay, the opaque shape is (shapes in `patch.shapes`, tied to the colour patterns by a unit case). Other sprites untouched. Interrupts off at every site.
Lockstep: the whole patched game next to the original, on the recording's fetch counts and IN values, hook instructions uncounted. Every frame: registers (BC, BC' free, counted), all RAM outside the ULA pixels (hook stack bytes and
the hook byte aside), picture: patched ULA + sprites = original ULA; a difference must lie inside a figure's box (the original's later plot, restore or fuse plot cuts the figure until its next plot; the sprite stays whole), or in a frame ending inside the clear or the reveal. Frames ending inside a plot: picture not compared.
Unit: every block x edge positions (all ones and all zeros copies), move paths, slots, states, unknown graphics, coin swap, bomb frames and pointer guard, tiles, setup, IM 2 vector. Negatives: broken builds, on the real recording.

## Results
Stamped run 2026-11-02 (`selftest.py --game bomb_jack --verify --stamp`; simulation only). Builds: bomb_jack_sprites.nex 83823fa5df548b36cb59835a9d25f0d0, bomb_jack.nex dd0c73d33d6e8eddc71195d5e95783ce; boot OK on Sinclair's and a foreign ROM3. Per recording: work/stamp_report.txt.
16 recordings, 52,185 frames, all Verify IDENTICAL, all Lockstep IDENTICAL.
Hook counts: plots 156,120 (unknown graphics 63: the spawn frame, left on the ULA), erase 13, bomb plots 10,928, tiles 1,846, collected 96, clears 66, shown 62, GAME OVER 3. No hook never ran. Figure pixels compared 29,757,164.
Lockstep pictures, 52,169 frames: 41,183 bit-identical; 10,754 differ inside figure boxes only (cause: see Lessons); 141 end inside a plot, 91 inside the clear or reveal (not compared or mid-copy). BC or BC' differ at 2,254 frame ends with no effect on anything else.
Unit PASS: every block x edges 376, move paths 50, tiles 90, bomb plots 48, slots 11, unknown graphics 9, states 4, bomb collected 2, pointer guard 2, state 0, clear, level shown, coin swap, setup, IM 2 vector 1 each.
Negatives on bj_play, 17 broken builds: all DETECTED (per build: work/stamp_report.txt). GAME OVER's runs on the whole recording, the others on 2,300 frames. An 18th, the image left to the system ROM3, by the boot check.
Graphics blocks shown by replay: 78 of 94 as figures, 3 as bombs; 13 unit cases only.
Speed: hooks 3,974-14,547 simulated T per frame by recording, about 0.9-3.5 % of a frame at T / 6, estimated; no real-machine timing.
Census, 12 layout recordings (the original's picture): bombs on a paper edge 52 of 288; horizontal platform runs 22 of 134; figure frames 24,195 of 81,591. Those are the block edges the build removes. Scenery edges are not counted and stay.
Evidence PNGs: run folder png/ (software render of ULA + sprites).
JNext 1.1.104, the first emulator run (work/jn.sh, work/play_*.jds, work/lv.jds; png/jnext_*.png viewed): both .nex reach gameplay with ENTER then 1. Sprite build also played to deaths, level restarts, GAME OVER, title and high scores (no stray sprites, layer off over GAME OVER), and layouts 3, 5, 8, 9 by memory pokes. Random keys only; no comparison of frames against the plain build; speed not measured. Not hardware.

## Hardware checklist (nothing here has run on hardware; item 1-3, 8 passed in JNext)
1. Boot the .nex: loading screen, key, menu, 1 starts: PLAYER 1 START on the ULA, no sprites until the level shows.
2. Interrupts run: the game moves at all. It takes its IM 2 vector from the alt ROM at 0x39FF, kept FF FF: a build that loses it hangs at once.
3. Level 1: figures, bombs, platforms in their colours, whole; platform over the pyramid's edge one colour.
4. Speed and sound against the plain .nex. Figures walk behind nothing: all in front of bombs and platforms, as the original.
5. Bomb collected: sprite goes, 200 label appears on the ULA, goes. Lit bomb fuse animates. All 24: next layout, no stray sprites.
6. Power ball: enemies change; kill one: it goes. E and B coins correct, both ways round.
7. Blue-sky layout 5 and layout 8, with the most tiles: all platforms sprites, no missing tiles.
8. Death, lives gone: GAME OVER: figures vanish while it is up. Title and high scores: no stray sprites.
9. One-frame ROM garbage at each spawn: as the original, on the ULA.
Hardware risk review (PLAYBOOK 6b): BASIC and ROM ISR now run from the alt ROM with RST 0x18, 0x20, 0x28 and 0x38 fetched: DivMMC automap on those entries on a real core is untested (BRIEFING DivMMC). DivMMC: hooks at 0x386E-0x3C68, not 0x3D00-0x3DFF. Interrupts: never on at a site. Up to 55 tile, 24 bomb, 22 figure sprites: per-line limit not measured. Raster: sprites and ULA are not synced to the beam, as the original. Stack runs through alt ROM during the plot (POPs of the blank figure), interrupts off. MAME: not tried; no emulator run at all.

## Open
- Never run on hardware or an emulator with sprites: composition is modelled, not observed.
- A human's answers to "Defaults taken"; a person's painting of the sheet, in place of mine.
- Scenery keeps its block edges; only a painted Layer 2 could change that.

## Lessons
- [local: found by looking] observed: while moving to one palette, a constant left in the tile hook gave platforms an unset palette offset; both verify and my check passed (it compared the same constant); only the JNext picture showed it. Pixel colours need a picture from an emulator, not only shape checks.
- [local: only this game's plot reads its graphics from one pointer] demonstrated: when a masked plotter restores from a clean copy, pointing it at a blank figure keeps every path, timing and erase, removes the figure from the ULA, and needs one 96-byte table.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: I = 0x39 puts the IM 2 vector in the alt ROM's free range; the first hooks overwrote it and the per-site verify still passed, because sites run with interrupts off. Only the whole-game lockstep caught it. Any IM 2 game with I in 0x38-0x3C is exposed; the patch should refuse it and `isr` could flag it.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: the game swaps graphics in RAM (0xD917, coin images): patterns built once from the snapshot went stale on one layout only; found by the per-event pixel check on the 14th recording. Limit: other runtime rewrites of graphics are not excluded for the 16 blocks never seen.
- [local: a default that does not fit] inferred: the colour default (cell ink) gives black for everything here, so it would only remove block edges; the visible gain of this build is mostly added colour, on the coordinator's instruction, and that is not clash removal.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: `nexclash.py auto` with an engine's negatives can run past a shell timeout with its output still in a pipe; run it detached with a log, as LEARNINGS says.

- [local: this game's plots run from a clean copy] demonstrated: figures cut each other in the original, sprites do not: of the bytes that differ inside figure boxes, 90 % (bj_lvl09) and 88 % (bj_play) lie under two figures' boxes; the rest seen are bomb restores and fuse plots cutting a figure, and the reveal. Only these two recordings were classified (work/classify.py).
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: the first stamped run failed on my own negative, which stopped before GAME OVER in the recording: check a negative's site count on its frame range before the long run.

- [doc docs/LEARNINGS.md §1.3] observed: LEARNINGS 1.3 and BRIEFING C2 #5 already warn that ROM3 is NextZXOS's; I copied Chuckie's hook-range image and PROVEN stood on replays that run Sinclair's ROM. A snapshot with PC in ROM or a BASIC line still to run needs the whole image; `inspect` shows that state and nothing connects the two. Plain builds need it too: `survey`'s plain .nex does not have it. Sharpened in LEARNINGS.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: `nextboot.check` compares the state at the snapshot's PC, so a start-up that fails after that PC passes it; only a run in a Next model shows it. A JNext run to gameplay is cheap (under 30 s headless) and caught what 52,185 replayed frames could not; the process has no such step before stage 4.

## Technique use
- detect.gameplay-screen-readers: helped: named the question; the lockstep answered it.
- detect.tracked-unit: helped: one call, one figure, confirmed by the per-event check.

## Stage log
- 2026-11-02 stages 0-3 in one session (pilot, unattended): stage 0 6 min, stage 1 7, stage 2 41, stage 3 42 (two stamped runs, 18-19 min each), 0 user rounds, one coordinator message relaying the owner's report on colours.
