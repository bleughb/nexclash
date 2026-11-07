# Cobra (Ocean, 1986; 48K) - engine `cobra` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record cobra, stamped); JNext only, never on a Next.
Inputs: specnext/reference/cobra/ (cobra.z80 md5 0268fb4d = TOSEC "Cobra (1986)(Ocean).z80"; cobra_colour_lives,
cobra_colour_all, cobra_mono_all, cobra_colour_nocheat). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card.
Start with: the hardware checklist below. Open: under "Open".

Techniques: `detect.gameplay-screen-readers`, `detect.tracked-unit`, `patch.runtime-colour-map`, `patch.restore-speed`,
`patch.whole-altrom-image`, `patch.pace-limiter`, `optimise.pattern-cache` (recipe and results: docs/records/cobra.json)

## Import (2026-11-05)
Ported from Jon Attree's .nxc work, 2026-11-05 (pilot clone runs/cobra/nexclash, base 1d2faa4, head 625e759). The
owner approved the look of that build in JNext (cobra_sprites.nex befe11d9: white body, black dark pixels, no outline).
Its .nxc was never published; this port is a new build, not a byte rebuild: it takes the new defaults and changes the
hooks' timing, never the picture.
- Whole alt ROM image (patch.whole-altrom-image) in both builds; the plain build carries Sinclair's ROM too.
- Start: the snapshot's own BASIC (below), no stub.
- The caller's speed restored at every exit (patch.restore-speed: spd_in / spd_out, asm/lib/hlib_speed.asm).
- Pace ORIGINAL by the limiter (patch.pace-limiter, asm/lib/hlib_pace.asm) and prepared patterns (optimise.pattern-cache).
- R: the game reads only bit 7 (frame flag); the hooks never write R; the verifier compares bit 7 at every hook.
Published .nxc: Cobra v1.0 (pilot runs/cobra/out/cobra_v1.0.nxc), target the TOSEC .z80.

## Inputs
Snapshot: the TOSEC "Cobra (1986)(Ocean).z80", md5 0268fb4d76200708849269c9747b65ff (the file the 2026-11-02 engine was
proven on; the pilot's tap2sna of "Cobra (Europe).tzx" = TOSEC [a3][a3].tzx was not used). Loader state: BASIC line 5
PAUSE 0 on the loading screen, game in memory, line 6 RANDOMIZE USR 44816. The tape's 6,912-byte screen (TOSEC .tap
block 3) is byte-equal to the snapshot's 0x4000-0x5AFF, so the build shows it from bank 5 and PAUSE 0 holds it.
No Fuse and no human: recordings by work/cobra_rec.py (pilot run folder), biased random keys; cheats only in the RZX
snapshots.
| Recording | Mode | Cheats | Reaches |
|---|---|---|---|
| cobra_colour_lives | COLOUR | lives | round 1: the whole scrolling map, wrapped several times |
| cobra_colour_all | COLOUR | lives, weapons, round end | rounds 1-7, all 3 level types, weapons 1-3, bullets |
| cobra_mono_all | MONO | lives, weapons, round end | rounds 1-6, weapons, bullets |
| cobra_colour_nocheat | COLOUR | none | 3 games to game over, high score entry, menu, restart |

## Start-up
2026-11-02: on NextZXOS's ROM3 the snapshot's stacked 0x1B76 slid into other code, so the first build started at a
key-wait stub (cobra.py START_STUB). 2026-11-05: with the whole alt ROM image, alt ROM image 1 is Sinclair's ROM, so
BASIC continues as on a 48K: PAUSE 0, then USR 44816. Both builds now start from the snapshot itself. Proof: the ROM
path check over all 4 recordings (every ROM byte the original runs is as recorded, the tail never read before written),
and JNext 1.1.104 (both builds: loading screen, credits, menu, play). The replay starts where the build starts.
The stub stays in cobra.py behind START_STUB = False, its unit case kept.

## Rendering model (PLAYBOOK 2): full redraw, direct to screen
Ink is 0 (or the sky colour); blank = 0xFF, so a figure's LIGHT pixels are PAPER: mask 0 + gfx 0 clears the bit and the cell's paper shows. That is the clash.
Main loop 36396: wait for interrupt (40852: R bit 7, set by the ISR's LD R,255, is the frame flag; beeper there; the RNG
0xA507 is also called from that wait, 41022, so the game's randomness follows its timing), DI, logic, 38398 raster wait on
the floating bus, 40074 scenery (compiled PUSH blit), 41037 stars, 39651 figures (bullets 0x9ED1 inside it), EI.
| Figure | Plot | Notes |
|---|---|---|
| player, carried weapon, 7 enemies / burgers and other pickups / explosion pieces | 39819, 39812, 39744 (top clip) -> loop 39865 | rows in pairs, 3 columns, preshifted by 2 pixels |
| bullets (3) | 40714, 40716, 40733, 40735 | 8 x 4, overwrites its bytes |
Death loop 36596: 20 x CALL 39651 with NO redraw, interrupts on.
Readers (`scan --writers`): the ULA is read only by the plotter's own AND, the stars (41075, 41080) and 42107 (a wipe).
No recording writes any byte of the 91 listed images (work2/gfxwrites.py, all 4 recordings).

## Clash census (pilot work/cobra_census.py)
COLOUR: 49-57 % of plots span more than one paper; MONO 1.0 %. The engine targets COLOUR (the default).

## Build design
Sites and hook behaviour: top of asm/cobra_hooks.asm. ROM hooks 0x386E-0x3CBE in alt ROM image 1 (+ 20 register block);
state, stack, tables and the page code in Next page 26, mapped at slot 2 only inside a hook; the pattern store in pages
36-41 (banks 18-20), mapped at slot 6 only for its OTIR. Tail at 0xAE00 (zero, never touched). Plot index n owns sprites
and 4-bit patterns 4n..4n+3; a plot uploads only when (graphics address, rows) differ from that index's last.
- Upload: a listed image (91, profile colour_images) copies its prepared patterns (built from the snapshot's bytes by
  cobra.image_patterns, the slow path's output) with one OTIR a band; a painted, clipped or unlisted image builds them
  pixel by pixel as before.
- Pace: each plot opens a window; at its end pace_plot waits on the video line (NR 0x1E/0x1F) until the original loop's
  time has passed: 252 T a row pair less 5, 32 T more at each character row, less the hook's 3.5 MHz parts (T_FIX16).
  e_frame, hide_rest and e_bul pay their time into the debt (DBT_*), which the next windows repay; e_frame prepays
  hide_rest's quick path, which runs after the figures. The constants are measured on the verifier's time model.
- Clip x 24-239, y 0-143: the original's black-on-black cells hide figures there.
Colour map (docs/COLOURS.md; patch.runtime-colour-map) unchanged from the pilot: sheets, recolour, nothing painted.

## Defaults taken (a human would have decided these; PLAYBOOK 3c)
1. Every figure a sprite: player, weapon, enemies, burgers and pickups, explosion pieces, bullets.
2. Scenery, stars, panel, text stay on the ULA and keep their clash.
3. Depth: plot order, all figures in front of scenery.
4. Colours: COLOUR mode bright white body, black dark pixels; MONO the play area's paper. No outline (owner's look).
5. Explosion pieces above the frozen figures, without the original's accumulating trail.

## Verify (what it checks)
Per plot, bullet and frame site: every register but R / T / MEMPTR at the return, and R bit 7; the hook writes no game
memory but dead stack; every screen byte the original writes = (old AND mask) OR gfx at the modelled address; at the
frame's end patched ULA + sprites = the original's pixels in the window, bit for bit. Each hook is entered at the game's
clock (verify clock=) and must leave it, with slots 2 and 6 restored. Time model (NextState): real time at the current
clock (28 MHz = 8 x 3.5, no wait states), NR 0x1E/0x1F from the frame T + the build's skew; per figure phase the build's
time over the original's must stay within 2 %. Unit: plot geometry, guard, cache, bullets, hide, palette, colour map,
and the every-site matrix (hooklib.every_site: each captured entry at NR 7 = 0-3, the same results, its clock back).

## Results (stamped run 2026-11-05, `selftest.py --game cobra --verify --stamp`; simulation only)
Builds: cobra.nex 2ec883ba2f88ef4fcda0623c2b985777, cobra_sprites.nex 00ead70a486598fb9b908feb675680ee; boot OK.
| Recording | Frames | plot / top clip | bullet | frame | round / text | Verify | Picture pixels | Uploads |
|---|---|---|---|---|---|---|---|---|
| cobra_colour_lives | 14024 | 17850 / 6 | 0 | 4781 | 1 / 1+0 | IDENTICAL | 9115792 | 11325 |
| cobra_colour_all | 9016 | 11014 / 1 | 837 | 1817 | 7 / 1+0 | IDENTICAL | 4640704 | 7009 |
| cobra_mono_all | 7005 | 8230 / 0 | 407 | 1411 | 6 / 1+0 | IDENTICAL | 3631392 | 5182 |
| cobra_colour_nocheat | 7009 | 5098 / 0 | 0 | 1371 | 4 / 4+3 | IDENTICAL | 2609440 | 3181 |
Every hook ran. Unit PASS: plot geometry 210, bullets 12, palette 4, colour map 36 (+12 controls), every-site clock matrix
340 cases over 9 sites. ROM paths: both builds, all 4 recordings, every ROM byte the game runs as recorded; the tail
never read before written.
Negatives, each a full replay of cobra_colour_all (work2/negative.py, pilot run folder), 12 of 12 DETECTED: plot hook
never runs, bullet hook never runs, no sprites shown, sprites one row low, pixel classes swapped, hook loses a register,
cache key ignores the graphics, leftover sprites not hidden, hook leaves slot 2 mapped, forced 3.5 MHz exit (replayed at
7 MHz), limiter never waits (figure phases -39.0 %), store entries point at other images. The good build replayed at
7 MHz: clean. Time model, cobra_colour_all: figure phases -0.89 % of the original's, worst +998 / -763 T.
JNext 1.1.104 (pilot runs/cobra/jn2): both builds reach play from their own start; pace 30 trials (quiet, busy, sound x
10, fixture runs in lockstep at every update): +0.00 % each, beeper writes 158.7 / 158.6, 509.6 / 510.4, 541.2 / 541.8 a
second against the original; flicker clean in 3 windows (plain .nex control); 15-minute soak: no freeze, loop or crash.

## Hardware checklist (nothing here has run on hardware)
1. Boot the .nex: the loading screen waits for a key (BASIC's PAUSE 0); if Enter from the browser is still held it may
   go straight on to the credits. Any key, credits; any key, menu; 5 swaps COLOUR / MONO; 1 starts.
2. COLOUR: Cobretti and enemies stay white and black crossing cyan brick, yellow blocks, white blocks.
3. Floating bus: the game must not hang at round start.
4. Speed and sound against the plain .nex: walk, fire; beeper notes as long as the original's.
5. Figures cut off cleanly at x 24 and x 239, and at y 143.
6. Weapons, bullets, pickups; death: explosion over frozen figures, a clean restart with no stray sprites.
7. Round end, ROUND screen, game over, high score, menu: no stray sprites. Pause (N). The speed key F8 mid-game.
Hardware risk review: DivMMC: hooks 0x386E-0x3CD2, not in 0x3D00-0x3DFF. IM 2 vector table 0xFF needs ROM 0x0000 = Sinclair's
(the alt image). The limiter needs NR 0x1E/0x1F (core 3.0+); without them it gives up after 65,536 polls.

## Open
- Never run on hardware. JNext only.
- A human's answers to "Defaults taken". The owner's painting: sheets and recolour are ready.
- Random-key recordings only: the boss path of level type 2 (43707) and the bonus for a real round end not reached.
- The ISR in the death loop can push onto figure graphics (SP = graphics in the original's plotter); no recording
  shows it, and the store and the cache assume the graphics stay as loaded.
- The flicker check reads a .z80 control's screen from bank 5's VRAM file, where a 48K JNext run does not keep it.

## On the current pace library (2026-11-07, shared engine refactor, goal 3)
- HLIB_PACE_V1 dropped: lib/hlib_pace.asm's current code (consistent line / held readings, the frame length never
  learned from a poll). HLIB_V_PACE 14 -> 26 bytes (0x4060-0x4079, free). dbt_open now keeps DE: the current
  hlib_debt_open loses it (V1's kept it; the first try failed the replay on D / E at every frame hook). The verifier's
  clock matrix leaves out all 26 bytes of limiter state.
- Sprites 00ead70a -> 82b05daf; plain unchanged. 4 recordings IDENTICAL (37,054 frames, 42,192 plots), unit PASS
  (clock matrix 340 cases), stamped. JNext pace on the pace fixture (300 updates keyed to 0xA5CD, state checked
  every update, lockstep to 300): -0.00% before, +0.00% after (quiet / busy 0.00%); port FE writes 437 / 436 a second
  (original 437); interrupts 33.53 a second all three.

## Lessons
- [local: hlib_pace.asm's header already says only hlib_line keeps DE] The current library's hlib_pace_open / hlib_debt_open lose DE (V1's kept it): an
  engine moving off HLIB_PACE_V1 saves DE around them.
- [local: this game's start] observed: the whole alt ROM image made the key-wait stub unnecessary: Sinclair's ROM runs the snapshot's own BASIC return, and the ROM path check proves it on the recordings.
- [local: this game's RNG] observed: the RNG runs in the wait-for-interrupt sound loop, so any timing change gives other enemies; pace trials ran on a fixture (that call and the lives decrement removed, in the original and the build alike), in lockstep for every update.
- [local: this game's sound] demonstrated: frame-locked pace hid a slower figure phase: game updates equal, but the beeper plays only while waiting for the interrupt, so port FE writes fell 8 % in busy scenes. The limiter and the prepared patterns brought them back (510.4 / 509.6 a second).
- [deferred Open: reconsider when the flicker check's .z80 reader is fixed upstream] observed: with a .z80 control the original's attribute transients read 0 (its screen is not in that run's bank 5 VRAM file); the original flashes the same cells (JNext mem[] log, work2/attrwatch.py). The plain .nex is the control.
- [local: the archive's trainer] observed: the TOSEC .pok's Infinite Lives also pokes 34925, which is not lives but a graphics pointer (read by the plotter's frame lookup at 39837); the single-poke trainer is used.

## Friction
- reuse: [local: the floating-bus Machine of the pilot's recorder is repeated in work2/cheats.py, outside the repo]
- retries: [local: the first pace runs left the RNG in, and diverged at update 3; the fixture fixed it]
- environment: [local: NEXCLASH_NEXT_ROM (enNextZX.rom) and NEXCLASH_JNEXT_CARD point into other pilot runs, read only]
- hand-rolled: [local: the time model in NextState repeats hooklib.NextModel's clock arithmetic for this verifier's events]
- scratch: [none: scratch scripts stay in the pilot run folder, none added to the repo]

## Technique use
- patch.whole-altrom-image: helped: also removed the start stub.
- patch.restore-speed: helped: the every-site matrix caught the forced exit at clocks 1-3.
- patch.pace-limiter: helped: equal pace, equal beeper writes; the debt took the outside hooks.
- optimise.pattern-cache: helped: build-time patterns cut an upload to one OTIR a band.
- detect.gameplay-screen-readers: helped: `scan --writers` over the ULA gave the proof (2026-11-02).
- detect.tracked-unit: helped: named the question; the disassembly answered it (2026-11-02).

## Stage log
- 2026-11-02 stages 0-3 in one session (pilot, unattended); start-up fix after JNext; colour route.
- 2026-11-05 import (pilot runs/cobra/nexclash2 on refactor-final dab40cb): new defaults, start without the stub, speed
  latch, limiter, prepared patterns, every-site matrix, 12 negatives, pace / flicker / soak in JNext, .nxc v1.0.

## Enhanced-colour check (2026-11-05): HARD, not built
No .256 for Cobra in Spec256-256-all38. The figures are silhouettes: body = the cell's paper, dark pixels only for
outline and a few details; the 2026-11-02 repaint of every body pixel looked worse. The scenery is compiled PUSH-blit
code (pixels as immediates in the code, 2-pixel scroll phases), not tiles a tilemap layer could recolour. Players and
enemies differ in shape, not colour. A repaint would need figures and scenery together.
