# Altered Beast (Activision 1989, 128K) - engine `altered_beast` (pilot game; 1.1 published)

## Next session
Stage 4. Version 1.1 was published on 2026-11-27. Enhanced 1.2 (player two and the enemies painted, own palette banks) is stamped (4 recordings, both modes).
The next hardware check is the two-player palette and the wolf flash on KS3. The scroll options and tape wait remain open.
The source snapshot and four recordings are in `reference-local/altered_beast`. The 1.2 builds, before/after comparison,
two gameplay renders and editable sheets are in the pilot's `runs/altered_beast/art-enhanced2/`.

Techniques: `optimise.pattern-cache` (recipe, owns and results: docs/records/altered_beast.json)

## Inputs
Snapshot: archive "Altered Beast (1989)(Activision)(128K).z80", md5 9df49e056fdf38a2f6da21fc4dfbf34f. 128K, title menu, PC 0x91DF in RAM, IM 2 (I 0xFD -> 0xFEFE: JP 0x88FF menu, 0x5F80 in play), 7FFD = 0: ROM 0 selected, never run or read (ROM reads in the replays are only SkoolKit's memory[0] at each interrupt).
No BASIC involved: both builds start at the menu; JNext confirms it.
Keys: SPACE starts (menu default E: Sinclair 1): 6 left, 7 right, 8 duck, 9 jump/up, 0 punch. ENTER at the menu adds player 2 (default Sinclair 1 too; Sinclair 2 by D / I ..).
Recordings (no Fuse, scripted, work/m128.py because `record` is 48K only):
- ab_first: random keys, no cheat. ab_walk: walks right only, no cheat: game over and the tape wait.
- ab_level: archive .pok pokes 61330 / 61350 (infinite energy, lives) embedded in the RZX snapshot: the whole level, power-ups, beast form, boss, boss's death, level end.
- ab_2p: two players, same pokes.

## Hard limit: level 1 only
Banks 3, 4, 6 are empty in this snapshot and bank 7 nearly so. Game over and level end call the game's own tape loader (0xFF7D -> 0xFE4C; edge loop at 0xFED0 reading port 0x7FFE), which waits for ever: no tape in a .nex. Plain and sprite builds alike (observed in the simulator; screen stays, keys do nothing). Levels 2-5 are not reachable from this file and are unconverted-untested; a level loaded later would run through the same hooks.
Game over: the GAME OVER banner goes to the ULA, the last sprites stay as they were, and the game stops there. There is no route back to the title.

## Rendering model
Back-buffer composer. Buffer pixels (23332) (0x7814 up, moves one byte per scroll step), stride 32, attributes (23334); clean copies at (23954) = buffer + 0x18C0, (23956) = attributes + 0x3A0 (constant over every recording). Main loop: AE3F HALT, AE40 CALL 0x60EB blit (rows 0-18 columns 2-29, row 19 7 lines columns 9-26), AE43 CALL 0x6DE4 buffer := clean copy (columns 2-29 only: margins are stale), logic, plots.
Figures are CELL aligned, both axes. Record: flag 0 = empty, 1 byte; else flag, 8 graphics, attribute, 10 bytes. Plot entry CE36; loops 0xD036 (stored), 0xCEEB (mirrored via table 0x6A00); mask = table 0x6900[g]: a horizontal 2-pixel halo around ink, empty bytes transparent. Rows clipped to 40 <= y < limit (self-modified 60, 57, 56). 0xD1B9 / D210: opaque kind, W bytes x (IX+25) lines, attributes at data + 144 (graves). Second parts through D0D9 re-enter the same loops.
Attributes are the figure's own per cell and overwrite the scenery's cell whole: that is this game's clash. 0xCF84: type 6 with (IX+26) -> attribute 7 (hit flash, from frame ~610 in the recordings). 0xCFBC: type 64 with (23325) -> 4 and 5 swapped (player two's colours; only in ab_2p). The attribute address is worked out with the column as 8 bits unsigned, so a figure off the left edge paints attribute cells 7 rows below itself in columns 28-29: an original glitch, gone in the build.
Readers: the buffer only by the plotters and the blit; the screen only before the first blit (frames 2-398: menu and intro; `scan --writers` readers list, work/srd.py).

## Clash census (before building)
work/census2.py: cells where a figure's attribute differs from the scenery's and scenery ink shows through: ab_first 60.5 %; whole level 57.1 % of 179,400 figure cells in view, 700,541 scenery pixels recoloured, worst frame 194 cells (boss scene). No colour or graphics option in the menu: control choice and players only. The owner's eye and the numbers agree.

## Design (defaults, unattended)
Keep everything the original does; only the blit's source changes. The buffer keeps the figures, so no game memory differs but the screen.
| Site | Original | Hook |
|---|---|---|
| 0xD036 / 0xCEEB | LD A,(23939) | log the figure, then the original |
| 0xD1D8 | CALL 0xD210 | log the opaque figure, then the original |
| 0xAE40 | CALL 0x60EB | pointers := clean copies, blit, pointers, HL and (23296) put back; then commit |
| 0xAFED / 0xB046 | LD HL,(23334) | end of level: the two routines that write attributes straight into the buffer (yellow curtain, rows 0-16, columns 21-28): set a flag, then the original |
Curtain: found by the attribute model at frame 16,420, not by looking. With the flag set, e_bl exchanges that rectangle between the buffer's and the clean attributes around the blit, so the blit shows it and the clean copy is whole again at return. A first version copied it after the blit: JNext showed it flicker, since the blit takes over a TV frame. Figures inside the rectangle keep their cell colours on the ULA during those seconds. Static search of every LD (23334) / (23332) / (23954) / (23956): no other writer.
Hooks in alt ROM images 0 and 1 (setup as Target Renegade). Page H = 26 at slot 4 while a hook runs; hook stack in H. Interrupts stay on: the in-play ISR 0x5F80 never touches slots 4 or 5 (work/isrslots.py, 2,333 entries). Commit after the blit, so sprites change as the finished scenery is on show.
Sprites: 16x16 4-bit, tiles over 2x2 cells, empty tiles none. Cache: 32 entries, 128 patterns, keyed by stream, kind, mode, size, visible rows, 4 data bytes; if no idle entry exists an entry on show may go (counted). Clip window x 16-239, y 0-151. Colour store: pages 28-67, 8 bytes per address 0x6000-0xFFFF, mapped at slot 5 only for the read.
Dropped: figure cells in row 19's 7 lines (below y 151), and pixels that wrap round the buffer's margin in the original (a figure at column < 0 or > 31 leaks to the far side a line up). Counted by verify.

## Results
| Output | MD5 | Status |
|---|---|---|
| altered_beast.nex (plain, tail 0x5DD3) | 3a40cd83e14bad535b3f147708b2284e | boot sim OK, reaches play in JNext (pilot 0dc7a02b before the interrupt fix and automap off) |
| altered_beast_sprites.nex | edea9ecd09412d385fc67cb8d28458bb | 1.1: 4 RZX IDENTICAL (32,291 frames); 1.0 was 87afba14 (hook code 6 bytes shorter); KS3 1.0 plays |
| altered_beast_enhanced.nex (1.1) | a64bc996659bf73a54aba1483e8c435c | 4 RZX IDENTICAL against its map; palette negatives 4/4; 4,870 map entries |
| altered_beast_enhanced.nex (1.2) | 758514afbb7ba14c315ff682befed834 | 8 palette banks, 7,922 paint entries, 524,800 bytes |

2026-11-27 run (selftest --verify): every recording against both sprite builds IDENTICAL (ab_first 2,727, ab_walk 7,024,
ab_level 16,526, ab_2p 6,014 frames); broken builds on the recordings 16/16 (1,500 frames: the hit flash first comes at ~610;
600 missed the hit and player-two controls); unit tests on each build, map negative 3/3, mode negative 24/24.
Tail: 0x5DD3-0x5E02 untouched, 0x5E03-0x5E32 write-first (scan, ab_first and ab_walk). No game ROM use.
Speed: hook T per game frame 59-120K simulator T at 28 MHz, about 10-20K at 3.5 MHz, against a game frame of ~340K T (4.8 TV frames). JNext, plain against sprites from the same state, cold cache, 400 frames: best match of the game's variables at 13-15 TV frames behind mid level, 19 at the boss: 3-5 %. Level-end head: 5 game frames lost, since its visible rows change each step. Matches are approximate (23-24 of 501 bytes still differ).
Colours: sheets in sheets/; recolour run on a test painting (Boss group's clear pixels black), 1.3 s, not the default: out/painted/, png/decision_boss_solid_jnext.png.

## Defaults taken (a human would have decided)
1. Every figure a sprite, including graves and thrown effects. 2. Scenery, HUD, text on the ULA; the GAME OVER banner stays ULA. 3. Depth: the game's plot order, sprites over all scenery. 4. Colours: the game's own cell colours, no painting; a figure cell with mixed colours keeps them. 5. See-through: the game's mask as it is, no solid fill, no extra outline; stone shows through empty graphics bytes as in the original. Graves stay opaque with black paper as drawn. CLOSE CALL, the boss: the old clash made him look dense because stone in his cells took his colour; as sprites stone shows through his empty bytes and he looks thinner. Painting his clear pixels black fills him: png/decision_boss_solid_jnext.png (plain | default | black-filled test). 6. Intro screen, title and lightning handled as the game draws them: only the plotter's figures convert.

## Player recolour and HUD (owner's round, 2026-11-02)
Boots: the green is in the game's own data: attribute 04 in the sprite records' lower cells (stored in the snapshot, e.g. frame 0xB926 rows 5-6), not picked up from the grass; the plotter overwrites the cell with it.
Two paintings, `recolour` only, nothing here is the default: A solid fill black + boots black with grey highlights (pure black vanished on the dark ground); B bright yellow skin + bright red tunic + dark red boots and hair (sprite palette has no skin tone: nearest usable), dither dots in shade colours. No outline added: the mask already gives a black side halo; painting edge pixels would thin him. Painters: paint/ in the run folder (regions by hand per body frame).
HUD: panel art 0x98BD (18 x 32 lines, copied once by 0x6D1A), digits 0x6358 (printed over the whole cell by 0x5FD3), lives 0x6218 / 0x62B8. Text merges because dither dots share the text's cells. Smallest fix: data only, dots with no horizontal neighbour cleared in the text and digit cells, no code, no ink change. Labelled build altered_beast_hud_sprites.nex; `recolour` works on it too. Lockstep: both replays' whole 128K identical every frame on all 4 recordings, HUD lines masked.

Owner's choice: the game's colours + the HUD fix: altered_beast_hud_sprites.nex c9e01815. Paintings dropped.
Digit check, cleared up: with a player out of lives the game flashes PRESS FIRE (0x6C80) and CREDITS n (0x6CB0, digit from (30402)) over his score cells, frames 5589-6152 of ab_walk, 422 frames, longest run 162. Same in the unedited game. No score difference: the check assumed those cells always hold digits. It now accepts exactly those blocks' bytes. HUD left: these two message blocks keep their dither, as the original.

## Next interrupt fix (2026-11-21, Tang board)
Crashed on the Tang board at the menu's first change (~8 s), plain build too, clean or dirty start: PC 0, SP 0x0002.
Cause: the three interrupt handlers (0x5F80 play, 0x88CC, 0x88FF menu) open EI; EXX; EX AF,AF'. The next interrupt can
be accepted after EXX, 37 T after the acknowledge starts. A 128K's /INT lasts 36 T; the Next core's lasts longer. Measured
on the board with a test handler: at 128K timing it re-enters when sampled 38 T after the acknowledge, not at 42 (48K
timing: 34 yes, 38 no). So every interrupt ran the handler twice, the frame's work overran, and an interrupt came with
bank 1 paged for the music (its 0xFD00 IM 2 table is zero): JP 0. OverSpec takes one interrupt per frame and never shows it.
Fix, every build (INT_SITES; PlainPatch for the plain build): EXX; EX AF,AF'; EI, EI 8 T later (45 T). int_fix_check runs
each entry both ways from 40 register states: same registers, interrupt state and memory (a dropped EX AF is caught).
Builds differ from the unfixed ones in those 9 bytes only. Board: unpatched crashes at ~8 s every time; fixed, 45 s of
attract mode (hi-scores, credits, menu) and the smoke pass (dirty start, intro, play, scroll, enemies) clean.

## Enhanced 1.1 colours (KS3 play test 2026-11-26: "wants Enhanced colours")
A colour set (NXC "Enhanced"; the default stays the game's colours): docs/profiles/altered_beast_enhanced.json,
built as altered_beast_enhanced.nex by auto. Colours from Sega's 1988 arcade original (level 1 screenshot):
the hero skin with a red loincloth, blond hair and brown sandals; zombies in purple robes with grey heads;
fire-coloured transformation clouds; wolves pale. First pass (pilot runs/altered_beast/art-enhanced1:
BRIEF.md, REPORT.md, before_after.png), owner to review and clean up.
- Palette: the map's 'palette' may change only entries no figure's cell colours use (PAL_FREE 1, 9, 12, 13:
  blue, bright blue, bright green, bright cyan), now skin, skin shade, brown, orange-gold. A figure the map does
  not paint keeps the game's colours exactly. The setup loads it (boot check: the loaded palette = the map's).
- Hit flash (wolves, mode 1) and player two (mode 2) draw in the game's colours over a map (bout skips the store
  when V_MODE is not 0): painted, both would look like the normal figure. Player two in the Enhanced set is
  therefore the game's colour-swapped centurion (owner to decide if he should be painted too).
- Verifier: unit tests now expect the build's own map (the review note of 2026-11-22), a pixel the map makes
  see-through is left out of the buffer check, the map test runs on the Enhanced build too, a negative takes out
  the mode test, palette negatives (wrong palette loaded, one bit off, a map changing a used entry).

## Enhanced 1.2 colours

Bank zero retains the 1.1 palette and all 63 recorded original-bank poses, including 36 player-one poses.
Player two shares the centurion graphics and has independently editable cobalt cloth, dark hair and brown sandals.
The zombies have purple robes and olive-grey skin. The pale wolves have grey-green shadows and flash solid cream
inside the black silhouette. The sorcerer wears purple. The boss and flying heads use reds, ochre and dark leather tones.

The plot log includes the object type. Sprite attribute 2 selects one of eight 16-colour banks, and the pattern
cache includes the bank. The map keys include both bank and graphics address. A sparse directory fits 33 used
colour pages into the existing 40-page allocation. Complete player-two rows upload four packed bytes directly.
The unbanked assembler output remains the 1.1 default. In the pilot's `art-enhanced2/sheets/`, edit a group's
`PAINTING_SPRITES.png` at native size. Use `recolour` with its matching layout and the Enhanced NEX and sidecar.

On JNext, the 400-frame comparison against plain found the same best offsets for both Enhanced versions
at mid-level, at the boss and in two-player play. The 1,000-frame two-player trace matched all 160 update times.
Holding right for 1,500 TV frames gave 26 eight-pixel scrolls each, every ninth update. Version 1.2 completed
236 updates to 1.1's 237. Timing fixtures preserve the live printer buffer and patch only the in-play interrupt entry.
See the pilot's `art-enhanced2/REPORT.md` for the comparisons and hardware limits.

## Scroll (KS3 play test 2026-11-26: "jerky, needs a scroll speed fix")
Measured on the simulator (work: scratchpad probes beam.py, plots.py, ramcycle.py over ab_level and ab_walk):
- Everything moves in 8-pixel cells: the scenery one cell every 9 game updates while the player walks at the edge
  (the game's own 9-step counter at 0x5DA3, 9 down to 1, sets the phase), zombies a cell every 2-3 updates.
- An update takes 4-7 TV frames (ab_level 4,000 frames: 129 x 4, 294 x 5, 221 x 6, 37 x 7, 2 x 8): the scroll is
  an 8-pixel jump about once a second, at uneven intervals.
- The blit takes 1.5 frames at 3.5 MHz from the interrupt: one torn frame per update (rows above ~23 new), as the
  original. The commit runs after it, so sprites above row ~118 move one frame after the scenery at each step (ours).
Options put to the owner (none built): a steady pace (the work at 28 MHz, a picture every 5 frames, blit and
sprites inside the top border: no tear, no lag, steps stay 8 px); a glide (patch.figure-glide: each 8-pixel move
spread over the next update, scenery by the ULA's hardware scroll split from the panel by the copper); a continuous
scroll across the 9-update cycle from 0x5DA3.

## Lessons
- [local: shared player graphics] Key the stored paint and pattern cache by palette bank as well as graphic. Packing fully painted rows kept the cold two-player uploads within the same update frames as 1.1 on the 1,000-frame JNext trace.
- [local: speed fix] Every hook latches the caller's speed on its own stack page (V_SPD 0x8062) and gives it back
  before leaving it; fxswap too. The verifier turns the entry speed 0-3 at every hook (each about 51 times in 600
  frames); two negatives: 28 MHz left on, 3.5 MHz given back.
- [doc BRIEFING A1] A handler that enables interrupts within ~40 T of the acknowledge runs twice per
  frame on the Next core; a 128K's 36 T /INT hides it, and emulators that take one interrupt per frame never show it.
- [local: coloursheet.choose picks figures by key, so pixels under a second part are on no painting sheet] The painting sheet left pixels of bodies under their head parts unpainted: JNext showed a half-painted standing pose. Painting the whole-figure sheet with `recolour --layout` covers them. Enhanced round 1 (2026-11-27) again left 1,167 hero and zombie pixel positions off the painting sheet (whole heads in game colours): a second pass on the whole-figure sheet, redrawn with round 1's map, is part of every full repaint here.
- [kb lesson.map-palette-free-entries: a map's palette changes only entries no figure's cell colours use] Counting the sheet's colours first showed four entries no level-1 figure uses (1, 9, 12, 13): the Magic Knight PAL_FREE rule gives an Enhanced palette with no change to any unpainted figure.
- [local: a painted figure hides the game's colour cues] The wolves' hit flash and player two are attribute changes; painted, both look like the normal figure, so the hook draws modes 1 and 2 in the game's colours over a map (unit negative: the mode test taken out).
- [local: scroll judder measured before any design] The jerky scroll is the game's own 8-pixel step every 9 updates at 4-7 frames each, plus our commit after a 1.5-frame blit; the game's 9-step counter (0x5DA3) is the phase a continuous scroll would need.
- [kb lesson.clean-buffer-composers: the blit-from-clean-copy needs a clean copy that exists in memory at blit time and a game that reads neither buffer nor screen] Keeping the back buffer intact and redirecting only the blit's source gave identical game memory with one small hook; check for a clean copy first in any composer.
- [kb lesson.recorder-128k-not-in-toolkit: 128K recording stays outside the toolkit in this pilot; BRIEFING C2 #15 already lists analyse / recorder as 48K-only] work/m128.py is 90 lines: Machine with 7FFD paging, banks in save / load. Replays cleanly through rzxplay.
- [kb lesson.snapshot-intake-state: a snapshot's empty banks show the limit of the game before any design] Check which banks are zero at intake: a multiload game on a snapshot is one level.
- [kb lesson.compare-final-frame-with-original: a verifier's model against the real buffer finds what the eye misses] The plot model is compared with the game's own buffer every game frame: it found the level-end curtain, an effect that writes attributes outside the plotters, and the 8-bit attribute address glitch.
- [local: JNext boot-state tests from a mid-game snapshot] A cheat-run state saved as .z80 and built as a test .nex put the boss on screen in JNext in seconds, which key presses alone would not reach.

## Friction
- reuse: [local: the pilot's Altered Beast engine ported as it was, plus INT_SITES]
- retries: [local: the crash was found on the Tang board, not in any simulator: interrupt length is a hardware-only fact (BRIEFING A1)]
- environment: [local: the engine sat uncommitted in a worktree 155 commits behind main; carried onto main and re-stamped there]
- hand-rolled: [none: the interrupt-length check was a board test, recorded in the notes]
- scratch: [none: nothing added to tools/]

## Technique use
- detect.gameplay-screen-readers: helped: no reader of the screen after the first blit, so the ULA may differ.
- detect.tracked-unit: helped: one plot call draws a whole figure or its second part.
- optimise.pattern-cache: helped: the working set fits 128 patterns; a figure whose visible rows change each frame (the descending head) rebuilds each frame.
- patch.scratch-redirect: no help: inverted instead, the blit reads the clean copy and the plotter stays untouched.

## Hardware checklist
0. Tang board 2026-11-21 (fixed build): menu, intro, play and scroll clean, 45 s of attract mode; unfixed crashed at ~8 s.
1. Loads to the menu, SPACE starts; the intro, lightning and the rising figure; player one with Sinclair 1 keys 6-0.
2. Stonework stays grey next to the player and zombies; figures have their colours and no block around them; the graves white.
3. Scroll: sprites stay aligned to the scenery; a figure at the screen's left and right edge clips cleanly.
4. Boss scene, flying heads: no missing figures, no slowdown beyond the plain build.
5. Two players: ENTER at the menu. Game over: banner shows, game stops at the tape loader as the plain build does.
6. Enhanced 1.2 on KS3: compare player one's red cloth and blond hair with player two's blue cloth and dark hair. Hit a pale wolf and check that its cream flash reads against the stone. Check the purple zombies and red boss.

## Stage log
- 2026-11-02 stages 0-3 in one session (pilot, unattended): stage 0-1 25 min, stage 2 30, stage 3 20 (two stamped runs, 7 min each), about 75 tool calls, 0 user rounds.
- 2026-11-27 stage 4 (KS3 round): scroll measured, options to the owner; Enhanced set: palette and mode rules, verifier fixes, negatives on the recordings run by auto, paint rounds 1-2.
- 2026-11-27 stage 4, Enhanced 1.2. Added banked paint, whole-pose sheets and a two-player colour and timing check.

## Open
- Scroll: the owner's choice among the options in "Scroll" (none built).
- Enhanced 1.2 awaits the owner's colour review and a physical KS3 play test. The 1.1 feedback predates this repaint.
- Game over waits for the tape for ever (the original's own loader): back to the title instead?
- Hardware: KS3 1.0 (2026-11-26) and 1.1 (2026-11-27) played. CSpect never run.
- Levels 2-5: tape data. A tape-based 128K route is out of this pilot.
- Row 19 and margin-wrap pixels as above.
