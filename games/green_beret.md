# Green Beret (Imagine, 1986; 48K) - engine `green_beret` (pilot game: unattended, no hardware)

## Next session
Stage 4. The owner played 1.2 on a KS3. The Spectrum grey ring and the combined Enhanced colour set have emulator coverage. Both await a physical Next test.
Inputs: pilot run folder (green_beret.z80 md5 c1a76349, work/reference/green_beret/*.rzx)
Start with: hardware checklist below; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `detect.gameplay-screen-readers`, `detect.tracked-unit`, `patch.runtime-colour-map` (recipe and results: docs/records/green_beret.json)

## Current colour choices

The normal build produces the plain conversion, Spectrum sprites and Enhanced sprites. Both sprite choices have a tape-loading-screen variant. The patch menu offers one Enhanced set. It combines the coloured stage intros with the owner’s arcade painting.

Spectrum uses swatch 15 for the one-pixel grey ring, RGB333 444 (9-bit word $124). The 1.3 patterns used swatches 1 and 2 for all 22,686 opaque pixels. Four-connected exterior pixels touching black in any of eight directions get the ring. Padding preserves the 1,221 ring pixels beyond the source rectangles. The original plotters still run and retain the original gameplay data. All 134 isolated figures match the rule, including mines and shots. All 27,716 opaque Enhanced pixels and nine hardware palettes match the owner’s approved build.

## First Enhanced intro build (1.3 test, 2026-11-27)

Menu option 8 starts off. In this earlier intro-only test, the default loading build was `b65abbdf8cb470307ee527b69a2f0205`. Enhanced loading was `915f4ee12d950aaf1961a4030a651261`. Both retain the tape menu and the gameplay sprite treatment from 1.3.

The screen uses scenery tiles. The renderer reads one brick at $77A0 and eight prisoner tiles at $77F0..$782F. The four gameplay plotters had zero hits during the first intro. A bank-7 tilemap holds 1,280 map bytes and eleven 32-byte patterns. The second ULA palette lets the original brick reveal, text masks and four shadow columns show through. The message uses the arcade's teal and stage names use the orange STAGE label. The stage table at $A304 supplies all four names.

The tile clip advances eight pixels at each original attribute-column update. This keeps stale bitmap bits in the unrevealed area black. The entry at $A21D takes 1,862 T. The column at $6658 takes 429 T. The exit at $A4AE through the next table read takes 272 T. All three match the original. The exit restores the normal display before the HUD wipe at $A4DE. In OverSpec, all four stage displays matched the expected 256 × 192 pixels. Six 320 × 240 samples outside the intro matched the 1.3 build. Both colour choices passed the four recordings, each covering 84,810 input frames and 32,810,944 gameplay picture-pixel comparisons. Enhanced also passed the 28 column checks and all three deliberate display faults. Evidence and the playable menu are in the pilot run `green_beret/enhanced-captives`.

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
Tail: 54 bytes at 0x8342 in both builds, put back before the game starts (restore_tail, Alien 8's method): the tail jumps to the alt ROM image's free span after the register block (0x38B8 plain, 0x3BCF sprites), which copies a backup over it and runs the tail's register restore again. That scenery-buffer row is NOT written before read: the screen copier (0xA9C7) shows it before the first draw at the start of play, so the old builds showed the tail's bytes for 0 to 26 frames (median 11, gb_nocheat; the snapshot holds zero there). rom_paths' tail proof (2026-11-04) caught it on 2026-11-23; work/tailtest.py compared RAM at checkpoints and missed it. No span is write-first in all four recordings. The plain build carries an alt ROM (Sinclair's) for this. Booted to the game PC 0x8273: plain RAM equals the snapshot, the sprite build differs only at the hook sites. First choice 0x9400 was graphics of stage 4: the stage-4 recording's scan caught it.
Colour route: Spectrum stores the padded patterns in pages 28 onward. Page 27 maps the source address to the pattern and its on-screen origin. Enhanced keeps the arcade colour planes and per-cache-entry palette offset. Its 15 opaque swatches per group include swatch 15 for opaque grey. Both sheets use a darker grey canvas for transparent pixels.

## Painting sheets

Build both choices with `python nexclash.py auto GAME.z80 --no-record --nex -o OUTPUT`. The owner's 5,225-entry painting is the Enhanced default in `docs/profiles/green_beret_arcade_colours.json`. Export its 1:1 sheets with `python -m nexclash.green_beret_art GAME.z80 OUTPUT`.

Import the edited PNG with `python nexclash.py recolour OUTPUT/green_beret_enhanced.nex EDITED.png --layout OUTPUT/green_beret_enhanced_PAINTING_SPRITES_layout.json --game green_beret`. Substitute the actual build filename when the snapshot has a different name. Keep each PNG beside its layout. Use the refreshed pair and painted NEX for the next edit.

## Defaults taken (a human would have decided these)
1. Every figure a sprite, from every caller of the four plotters. 2. Scenery, HUD, text on the ULA. 3. Depth: plot order, all sprites over all scenery. 4. Colours: figures have none of their own (ink black, body the cell's paper). Default chosen as Cobra: bright white body, black dark pixels; nothing painted. 5. No menus over the play area; GAME OVER is a ULA box in the sky, figures stay frozen as sprites.
ALWAYS-ASK, decided here: solid: follows the mask everywhere, so in the sky (y < 82), where the original has no mask, bodies are opaque white rather than see-through. Bullets and mines: mines as sprites with body; bullets dark only. The weapon shot (0xAB60) stays on the ULA: behind figures here, in front in the original; its body is the cell's paper. CLOSE CALL for a human.

## Lessons
- [local: padded sprite edge] Flood the exterior on a padded raster. The four plotters include black pixels on source boundaries. Isolating each emitted hardware figure catches lost margin pixels and palette bank errors on frames the recordings seldom draw.
- [local: stage intro] The name is selected at $A1FF before the wall is built. The stage-4 recording starts after that selection and retains MISSILE BASE. Set $FFDF to 3 before $A1FF to see PRISON CAMP. The first HUD wipe is inside $A46A. Returning from that routine is too late to switch the display back.
- [local: start screen] A snapshot saved after the tape's screen was overwritten loses what the original shows behind
  its menu; the build can put the tape's screen back in screen memory at the start (the boot check sees it through the
  patch's apply, the replay never touches it) and the .nxc shows it while patching (build_screen=nex).
- [deferred Open: reconsider when a second game's survey misses a plotter that a pixel-vs-sprite check finds] [kb lesson.survey-misses-plotters] The survey's routine table missed the mine plotter and the small plotter's order; a comparison of original pixels and sprites found both, by frame.
- [kb lesson.redirect-slot-2-scratch-screen: a plot that keeps running into a scratch page] Redirecting slot 2 keeps every register and the timing with almost no hook code: no padding, no register model. Works where the game does not read the screen for logic and the ISR stays out of slot 2.
- [kb lesson.prove-free-memory-by-access-scan: a scan on one stage is not enough for a tail] 0x9400 looked untouched until the fourth stage's recording.
- [doc LEARNINGS 2.2 Memory proofs] The scenery buffer looked written-before-read by a RAM-at-checkpoints test, but the copier puts it on screen before its first draw. The import carried a stamp from before the tail proof, so the 11-04 census never saw this game.
- [local: my error, nothing general to change] `dec l` between CP and JR NZ made every cache lookup hit: use `dec hl`, which keeps the flags.
- [kb lesson.reach-states-by-poke: stage poke] 0xFFDF poked just after the start reaches a later stage; the display's STAGE shows 01.

## Friction
- reuse: [none: the engine came in whole from the pilot clone]
- retries: [none: the rebuild gave the published d982d5ae first time]
- environment: [none: the record's sprite MD5 still named the build before the edge trim; corrected on import]
- hand-rolled: [none: nothing written by hand in the import]
- scratch: [local: dropped] 2026-11-23: gb_tailspace.py (bytes no recording reads before writing; the tool gap is BRIEFING C2 #46) and gb_tailglitch.py (frames from the tail's first read to its first write; result in Build design).

## Technique use
- detect.gameplay-screen-readers: helped. detect.tracked-unit: helped. patch.runtime-colour-map: helped, simplified to a keep plane.

## Stage log
- 2026-11-27: Combined the two Enhanced treatments, carried the approved map unchanged, and added the Spectrum ring. Read the engine, art and intro modules and the hooks together to reconcile setup addresses, plane formats and verifier assumptions.
- 2026-11-03 stages 0-3 in one session (pilot, unattended), about 1 h, ~55 tool calls, 0 user rounds.
- 2026-11-23 maintenance: the full re-verify for the Codex review PR failed the tail proof; restore_tail in both builds, record MD5s, re-stamped.

## Results (stamped 2026-11-23, `selftest.py --game green_beret --verify --stamp`, NEXCLASH_MAINTAINER=1; simulation only)
Builds (restore_tail, automap off): green_beret_sprites.nex bdfaa782be7651d631fb1eabd2b51598, green_beret.nex 0679156534b3372bfb2280262b39bcb1; boot OK. ROM paths COMPLETE, pass: both builds, every recording, every ROM byte the game runs as recorded, tail put back before the game starts. First stamp 2026-11-03 (462c599c, before the edge trim and the tail proof); a first try then failed on 4 pixels (margin wrap, frame 19032 of gb_stage4), and the verifier counts wrapped bytes since.
| Recording | Frames | draw | plot | plot2 | mine | small (outside draw) | wipe | Picture pixels | Verify |
|---|---|---|---|---|---|---|---|---|---|
| gb_nocheat | 16,779 | 991 | 3,061 | 41 | 59 | 312 (32) | 14 | 1,346,040 | IDENTICAL |
| gb_cheat | 26,019 | 8,065 | 34,185 | 1,196 | 4,059 | 1,917 (20) | 14 | 14,539,816 | IDENTICAL |
| gb_weap | 12,013 | 3,575 | 13,850 | 310 | 1,368 | 358 (8) | 10 | 4,883,792 | IDENTICAL |
| gb_stage4 | 30,003 | 9,890 | 40,316 | 1,169 | 4,385 | 1,532 (4) | 2 | 14,386,232 | IDENTICAL |
Every hook ran. Allowed differences are counted in the report, not failed: sky pixels above line 104, holes the small plotter erases, margin-wrap bytes. So "IDENTICAL" covers registers and memory but the screen and AF' after a mine plot, and the picture below line 104 apart from those two named exceptions.
Unit PASS (geometry at the edges for all four plotters, cache, hide, slot guard, colours). Negatives (2026-11-03) 16 of 16 DETECTED: 15 on gb_weap to frame 6000, "wipe keeps sprites" on gb_cheat to frame 14000, since gb_weap has no wipe with sprites up in that span (it was MISSED there). Two ("plots reach the ULA", "plot end leaves slot 2 mapped") were detected by the replay crashing on a bad opcode, not by a comparison. Negatives ran on the same hook code as the stamp; only verifier reporting changed after.
JNext 1.1.104 headless: both builds reach play, and stage 2 with trainers 1 and 7 (png/green_beret_jnext.png). Sprite-only layer: jn/s3000lay.png. Same schedule: game counter 53 in 400 frames in both builds, cold cache; same scroll at frame 14000. One sample, not a timing proof. Hook cost, modelled: about 47K T at 28 MHz per draw on gb_stage4.
Colour route: recolour on a throwaway painting 1.3 s; JNext showed it (jn/painted.png). Not the default.

## Hardware checklist for the 1.3 test build
1. Boot: control menu; 1, six keys, Y, stab. 2. Figures stay white and black across cyan, white, red scenery; no attribute squares on them. 3. Sky: bodies white above the scenery. 4. Weapon shots behind figures. 5. Stage screens, game over, restart: no stray sprites. 6. Speed against the plain .nex. 7. The first frames of play: no stray pixels in the scenery (the old tail showed there).

## Open
- 1.3 (2026-11-27, owner's KS3 round on 1.2): no white edge (the edge rule drops 1.0's 1 px ring too: every body
  pixel outside the outline is transparent) and the game's menu on the tape's loading screen again
  (green_beret-loading.scr in screen memory at the start, and in green_beret_sprites_loading.nex so the .nxc shows it
  while patching). Waiting on the owner's KS3 test. 1.2 played on the KS3 2026-11-27, good.
- Stage 3's end (helicopters) was reached by cheat, not finished by the bot; the true end of the game unreached. Boss paths of stage 4 not reached.
- Physical KS3 test of the Spectrum ring, the Enhanced sprites and the intro-to-play transition. The stage 4 boss and the ending still need recordings.
- 2026-11-27: 1.3: edge ring removed, tape loading screen at the start + _loading build; quick replay of gb_weap and gb_cheat (3,000 frames each) IDENTICAL, units PASS (106 edge-rule figures).
