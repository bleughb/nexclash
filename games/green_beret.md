# Green Beret (Imagine, 1986; 48K) - engine `green_beret` (pilot game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended; simulation and JNext; never run on a Next.
Inputs: pilot run folder (green_beret.z80 md5 c1a76349, work/reference/green_beret/*.rzx)
Start with: hardware checklist below; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `detect.gameplay-screen-readers`, `detect.tracked-unit`, `patch.runtime-colour-map` (recipe and results: docs/records/green_beret.json)

## v1.0 for the .nxc (2026-11-06, pilot runs/green_beret/nexclash2, refactor-final ecabb13)
Owner, after playing the INF1 build (462c599c) in JNext: "the white edges on the enemy needs to be trimmed back closer to
the characters outline, then thats ready to push."
- **Edge.** The white body is the original's mask (mask 0, gfx 0 shows the cell's paper). On the enemies the mask reaches
  2-4 px past the drawn outline, mostly behind them (a wedge or cape the original showed in the paper colour, unseen on
  matching paper). Rule (`trim_pixels`, figures of 0xA78F of 12+ lines): a pixel that is not dark, lies outside the
  figure (4-connected to the image's edge through non-dark pixels) and is more than 1 px (8 neighbours) from every dark
  pixel is transparent. Inside the outline and the 1 px ring around it nothing changes, so the ring that keeps a
  figure off dark scenery is the original's. Applied as the colour map's transparent bits (`trimmed_map`), merged under
  any painting, through the existing plane (`ovapply`) on upload; planes only for images whose shown body changes:
  56 images (enemy runners, the white leaper, the X jumper, the prone figure 2 px). The player's own frames are
  unchanged (his mask is already 1 px). Not the 8-line weapons the player carries (0xCD54 / 0xCE54): the bar between
  0xCE54's ends is the tube, mask only. Mines (0xAE40) keep their mask (2 px above the spikes).
- **Speed.** Hooks latch the game's clock (NR 7 bits 1:0 through 0x243B / 0x253B) and write it back at exit
  (`spd_in` / `spd_out`, card patch.restore-speed); before, every exit forced 3.5 MHz.
- **Alt ROM.** refactor-final's whole image (Sinclair's ROM from bank 47 + the hooks): no NextZXOS ROM3 byte is
  copied, so the v2.10 ROM3 trampolines (2026-11-06-v210-altrom-fix) do not apply.
- **R.** Not kept by the hooks, and not needed: the game reads R only with LD A,R followed by a test of the sign
  (bit 7, which the ISR sets with LD R; instruction fetches never change it). Shown by work/v1/rtest.py: every
  recording replayed with R's low 7 bits randomised at every hook site and update gives the same RAM at every update.
- Verifier: the picture check counts the trimmed pixels (the original's mask erased them; the build shows what is
  under them) only where a plot of a trimmed image put them; a unit case per figure image (106) against the rule;
  the every-site clock matrix (52 cases); negatives "edge rule left out" and "exit forced to 3.5 MHz".
- **Results (2026-11-06, simulation and JNext 1.1.104 headless; pilot runs/green_beret/work/v1).** Builds: plain
  f4d4e3d4, sprites d982d5ae. Replay IDENTICAL on the 4 recordings (84,814 frames, 91,412 figure plots; 310,485 trimmed
  pixels allowed where a trimmed plot put them; no plot of a trimmed graphic with another mask). Units: 106 figure
  images against the rule, 52 clock-matrix cases, the rest as before. Negatives 18 of 18 detected (work/v1/proof_neg.json).
  R test EQUAL on all 4 (283,838 randomisations). Pace (10 trials a scene, probe 0xA38C, lockstep on lives 0xFFE3 and
  stage 0xFFDF): quiet +0.00%, busy +0.09%, sound +0.06% (single trials 0 to +0.21%); no limiter: the loop waits on the
  ISR, so the build is never faster. Port 0xFE writes 5-7% fewer than the original (beeper loops end at the interrupt,
  hook time comes out of them). Flicker 300 frames clean; 15-minute soak clean. 26.11 and v2.09 card copies, Browser +
  loader: /tmp/NEXCLASH.NEX = d982d5ae on both, play reached, the same frames on both.
  .nxc: pilot out/green_beret_v1.0.nxc (= out/v1/Green Beret (1986)(Imagine)/...[a2][a2].nxc), MD5 975489b8.
- **Open.** Title screen on the menu (the 128K file has it): not done; that file is another snapshot (layout, signature,
  sites to re-check), not a small change. Trainers carried from the INF1 build, not re-run in JNext this session.

## Inputs
Snapshot: archive "Green Beret (1986)(Imagine)[a2][a2].z80", md5 c1a76349d08289810323bae0e62a9102. 48K, at the control menu, PC 0x8273 in RAM, IM 2, EI, SP 0xFEFB, no BASIC, ROM used only as harmless data reads (0x0000, 0x0100, 0x0200: erases at an unset address).
Why not the plain "(Imagine).z80": it stops in BASIC at PAUSE 0 (PC in ROM, md5 486eefea), which a .nex cannot resume on ROM3 (docs/LEARNINGS.md). ZXDB filecheck returned 502 for every MD5 at the time, so the listing of [a2] is unconfirmed; a 128K release exists, "(128K).z80", b742f799, ZXDB entry 0002134 from the pilot's candidates, same game with AY: not converted.
Keys: 1 keyboard, then any six keys (these runs: Q A O P M N for up, down, left, right, stab, shoot), Y at HAPPY, stab at STAB TO START.
Recordings (no Fuse, work/lib.py + rec_*.py, biased random keys; cheats only in the RZX snapshots):
| Recording | Frames | Cheats | Reaches |
|---|---|---|---|
| gb_nocheat | 16,778 | none | stage 1, deaths, game over, restart |
| gb_cheat | 26,018 | lives, immunity | stages 1-3 up to the end of stage 3's run |
| gb_weap | 12,012 | + weapon, ammo | stages 1-2, weapons, shots, pickups |
| gb_stage4 | 30,002 | + stage poke 3 | the prison camp stage |

## Clash check (work/clash_check.py, gb first run d4, 20,001 frames)
Plots 25,485. 44.3 % of figure plots span more than one attribute. Ink pixels 3,495,540: 0 % non-black: figures are black ink. Body pixels 3,673,643 (mask 0, gfx 0) show the cell's paper: 44.1 % of plots show their body in two or more colours (bright cyan, white, cyan, red, green, yellow). Figures never write attributes.
Kind: between A and B. Figures have black ink and leave attributes alone, as B, but their bodies take the scenery's colours crossing cells, like Cobra (49-57 %). Owner's verdict: clash. No colour option in the menus (only key choice). Build.

## Rendering model
Loop A37E: wait on R bit 7 (set by the ISR's LD R,255), A386/A389 in-place scroll of the sky scenery (0xAB18: reads the screen, each byte := the next), A38C blit (0xA9B9, DI, LDI chain from the buffer 0x8000-0x87FF, lines 104-167, 28 columns), A38F CALL 0xA5FE figures, A392 CALL 0xC21A, logic, A3B0 score, A3E9 EI. About 2 TV frames per loop.
| Plotter | Site | Draws | Data |
|---|---|---|---|
| 0xA78F | 0xA7DF | player, enemies, explosions etc | 4 bytes x 2N lines, gfx via SP, mask via BC, preshifted 4 phases, cell-aligned x; y < 82 ORs with no mask |
| 0xA8BA | 0xA8E8 | small masked objects | 2 bytes x 8 lines, (mask, gfx) words, 4 phases |
| 0xAFA5 | 0xAFD8 | bullets | 2 bytes x 3 lines, OR only, erases its old image first (leaves holes in fresh scenery: an original glitch) |
| 0xAE40 | 0xAE5D | ground mines (called inside 0xA5FE, after the figures) | 3 bytes x 6 lines, mask + gfx, line 162 |
Left on the ULA: scenery, HUD, text; 0xAB60 (the 8-byte x 16-line weapon shot, drawn after the frame end, over figures in the original, under them here); 0xADB2 (opaque 4-byte stage-1 scenery strip, lines 88-111).
Dropped: a figure at column 29+ wraps its last bytes to the far side a row down, in the original; at column 31 that reaches visible column 2 for a moment (frame 19032 of gb_stage4). The sprite clips at x 239 instead.
Readers of the screen, `scan --writers`: the plotters' own AND, the scroll, a wipe, the attribute effects; nothing decides on pixels (verify compares all memory).

## Build design
The original plot code still runs, with its screen writes redirected: each plot site maps Next page 26 at slot 2, so 0x4000-0x57FF land in a scratch screen; the plot's end unmaps. So a plot leaves every register as the original and takes the original's time; only hook time adds. The one exception: the mine plotter leaves its last screen read in AF', proven dead on every event by running on for 12,000 instructions with both values (verify's dead_af).
Sites: top of asm/green_beret_hooks.asm, SITES_ORIG in the module. Code 772 bytes in alt ROM image 1 at 0x386E, 492 in page 26. State in page 26 at 0x5800-0x5FFF: cache keys, stamps, class table, BUF; ISR touches none of it. Interrupts are off in 0xA5FE.
Sprites: 4-bit 16x16, up to 2 x 2 per figure. Cache 32 entries of 4 patterns, keyed gfx, mask low, lines; the entry idle longest goes, never one on show (age < 2). Frame end hides the slots not plotted; the two screen wipes (0x64F4, 0x64E6) hide all. Clip x 16-239 (margin columns are black on black).
Tail: 54 / 80 bytes at 0x8342: scenery buffer, written before read; running the game with FF there changes only the 6 untouched margin bytes in it (work/tailtest.py). First choice 0x9400 was graphics of stage 4: the stage-4 recording's scan caught it.
Colour route: docs/COLOURS.md. Palette 1 white, 2 black, 3-15 Spectrum colours. Keys: graphics byte. Sheets: `sheets/`. Plane per painted image: per line 16 colour + 16 keep bytes in pages 28-51; index in page 27. Applied on upload.

## Defaults taken (a human would have decided these)
1. Every figure a sprite, from every caller of the four plotters. 2. Scenery, HUD, text on the ULA. 3. Depth: plot order, all sprites over all scenery. 4. Colours: figures have none of their own (ink black, body the cell's paper). Default chosen as Cobra: bright white body, black dark pixels; nothing painted. 5. No menus over the play area; GAME OVER is a ULA box in the sky, figures stay frozen as sprites.
ALWAYS-ASK, decided here: solid: follows the mask everywhere, so in the sky (y < 82), where the original has no mask, bodies are opaque white rather than see-through. Bullets and mines: mines as sprites with body; bullets dark only. The weapon shot (0xAB60) stays on the ULA: behind figures here, in front in the original; its body is the cell's paper. CLOSE CALL for a human.

## Lessons
- [deferred Open: reconsider when a second game's survey misses a plotter that a pixel-vs-sprite check finds] The survey's routine table missed the mine plotter and the small plotter's order; a comparison of original pixels and sprites found both, by frame.
- [local: a plot that keeps running into a scratch page] Redirecting slot 2 keeps every register and the timing with almost no hook code: no padding, no register model. Works where the game does not read the screen for logic and the ISR stays out of slot 2.
- [local: a scan on one stage is not enough for a tail] 0x9400 looked untouched until the fourth stage's recording.
- [local: my error, nothing general to change] `dec l` between CP and JR NZ made every cache lookup hit: use `dec hl`, which keeps the flags.
- [local: stage poke] 0xFFDF poked just after the start reaches a later stage; the display's STAGE shows 01.

## Friction
- reuse: [none: the engine came in whole from the pilot clone]
- retries: [none: the rebuild gave the published d982d5ae first time]
- environment: [none: the record's sprite MD5 still named the build before the edge trim; corrected on import]
- hand-rolled: [none: nothing written by hand in the import]
- scratch: [none: no scratch scripts added]

## Technique use
- detect.gameplay-screen-readers: helped. detect.tracked-unit: helped. patch.runtime-colour-map: helped, simplified to a keep plane.

## Stage log
- 2026-11-03 stages 0-3 in one session (pilot, unattended), about 1 h, ~55 tool calls, 0 user rounds.

## Results (stamped 2026-11-03, `selftest.py --game green_beret --verify --stamp`, NEXCLASH_MAINTAINER=1; simulation only)
Builds: green_beret_sprites.nex 462c599ceff785748e568a2ce5a47e9f, green_beret.nex f4d4e3d43e47102af66fb3a7e6e022ab; boot OK. A first stamp failed on 4 pixels (margin wrap, frame 19032 of gb_stage4); the verifier now counts wrapped bytes; the build did not change.
| Recording | Frames | draw | plot | plot2 | mine | small (outside draw) | wipe | Picture pixels | Verify |
|---|---|---|---|---|---|---|---|---|---|
| gb_nocheat | 16,779 | 991 | 3,061 | 41 | 59 | 312 (32) | 14 | 1,358,024 | IDENTICAL |
| gb_cheat | 26,019 | 8,065 | 34,185 | 1,196 | 4,059 | 1,917 (20) | 14 | 14,663,688 | IDENTICAL |
| gb_weap | 12,013 | 3,575 | 13,850 | 310 | 1,368 | 358 (8) | 10 | 4,942,552 | IDENTICAL |
| gb_stage4 | 30,003 | 9,890 | 40,316 | 1,169 | 4,385 | 1,532 (4) | 2 | 14,549,184 | IDENTICAL |
Every hook ran. Allowed differences are counted in the report, not failed: sky pixels above line 104, holes the small plotter erases, margin-wrap bytes. So "IDENTICAL" covers registers and memory but the screen and AF' after a mine plot, and the picture below line 104 apart from those two named exceptions.
Unit PASS (geometry at the edges for all four plotters, cache, hide, slot guard, colours). Negatives 16 of 16 DETECTED: 15 on gb_weap to frame 6000, "wipe keeps sprites" on gb_cheat to frame 14000, since gb_weap has no wipe with sprites up in that span (it was MISSED there). Two ("plots reach the ULA", "plot end leaves slot 2 mapped") were detected by the replay crashing on a bad opcode, not by a comparison. Negatives ran on the same hook code as the stamp; only verifier reporting changed after.
JNext 1.1.104 headless: both builds reach play, and stage 2 with trainers 1 and 7 (png/green_beret_jnext.png). Sprite-only layer: jn/s3000lay.png. Same schedule: game counter 53 in 400 frames in both builds, cold cache; same scroll at frame 14000. One sample, not a timing proof. Hook cost, modelled: about 47K T at 28 MHz per draw on gb_stage4.
Colour route: recolour on a throwaway painting 1.3 s; JNext showed it (jn/painted.png). Not the default.

## Hardware checklist (nothing here has run on hardware)
1. Boot: control menu; 1, six keys, Y, stab. 2. Figures stay white and black across cyan, white, red scenery; no attribute squares on them. 3. Sky: bodies white above the scenery. 4. Weapon shots behind figures. 5. Stage screens, game over, restart: no stray sprites. 6. Speed against the plain .nex.

## Open
- Never run on hardware. Stage 3's end (helicopters) was reached by cheat, not finished by the bot; the true end of the game unreached. Boss paths of stage 4 not reached.
- A human's answers to "Defaults taken". The owner's painting.
