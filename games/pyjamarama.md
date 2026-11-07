# Pyjamarama v1.1 handoff — 2026-11-05

Local package complete; ready for owner artwork review and subsequent release handling. No hardware test or card installation. Work is isolated in this folder; the other games and published builds were not changed.

## Owner artwork revision 1 — 2026-11-05

The owner reported that Pyjamarama looks good and edited graphics 85 and 100 in the PAINTING PNG. Both coins now use flat orange edging. Exactly 56 ink pixels changed. The uploaded PNG had 91 blended background pixels; those were removed only in the imported copy. The owner's saved PNG remains untouched. Enlarged before/upload/import comparison: `work/owner-import01/owner-changes-review.png`.

Current deliverables remain `out/pyjamarama_v1.1.nxc` and its Default/Enhanced NEX files. NXC SHA256 `cb17ba32fa801a334fbb6ea0f4ca74e91a003ccc5cf570f0fbda5d6f4905a9b5` (30,886 bytes); Enhanced MD5 `17f853050ea6f38a99d9937291ccd254`. Default is unchanged. The preceding package is archived in `out/before-owner01/`. A fresh clean editing kit is `out/pyjamarama_editable_owner01/` and `.zip`; the owner's original editing folder is retained.

The full-build output matches recolouring the preceding build byte for byte. Only 56 pattern nibbles changed; game code, hooks, palette, header, screen, sprite coverage and black detail are identical. Therefore the preceding timing measurements remain applicable; no new pace measurement is claimed. All 200 graphics passed 1,000 plot/boundary cases, 400 cache recycling cases, reset and setup checks. Two targeted recordings covering both coins passed 4,579 frames. The earlier 62-recording engine proof remains the baseline, not a newly rerun full suite. Actual dot-loader runs on fresh private card copies rebuilt both current outputs byte for byte and reached play in JNext (`jn/real-loader-owner01/`). No hardware test.

Painting import now merges only explicitly changed pixels onto the current map, so an older sheet cannot silently revert newer artwork. Current- and old-sheet no-op imports preserve the current map; the valid-edit and four refusal controls pass. Evidence: `work/owner-import01/`.

## Deliverables

- `out/pyjamarama_v1.1.nxc` — 30,886 bytes. SHA256 `cb17ba32fa801a334fbb6ea0f4ca74e91a003ccc5cf570f0fbda5d6f4905a9b5`.
- `out/pyjamarama_v1.1-default.nex` — MD5 `3d131076febb094be7e3613020363d3f`.
- `out/pyjamarama_v1.1-enhanced.nex` — MD5 `17f853050ea6f38a99d9937291ccd254`.
- `out/pyjamarama_editable_v1.1.zip` and folder of the same name — native-pixel PAINTING sheet, complete REFERENCE sheet, layout JSONs, original baselines and instructions.
- `out/catalog-curated01.png` — enlarged artwork catalogue; `out/pyjamarama_comparison.png` — original, previous solid build, Enhanced in native JNext captures.
- `work/painting_sheets.py` imports owner edits into a proposed map. It rejects altered silhouette, protected black detail, resized canvas, blended colours and contradictory shared-pose edits. No-op import reproduces the map; valid one-pixel edit and four rejection controls passed.

## Source and appearance

Source: archive `Pyjamarama (1984)(Mikro-Gen).z80`, MD5 `1ff279754d0730e503816199ac6976f3`, 48K. Refactor base `bd1528cfa50e598f9414ffc382c4bd0b123fbca0`; prior Pyjamarama engine `2847c0721dcdb289b1be5c15475e76293c5376ea`.

All 200 graphics are available as sprites below the HUD and in the sheet, joined into 163 complete poses/items. Enhanced has pink skin, blue pyjamas, red slippers, separately painted tool handles and blades, radio body/controls, bottle/label, food, insects and other objects. Flat colours follow original drawing details. Solid black inner detail is retained; no external outline or added silhouette pixels. Naturally single-material objects remain coherent. Scenery and HUD retain the game's original colouring; there is no new scenery painting route in this build. Enhanced is an opt-in menu set and starts OFF. The owner approved the general appearance; the two requested coin edits are included in artwork revision 1.

The enlarged catalogue and in-game comparison were visually inspected. Character and object parts read clearly without the previous outlined silhouette. The look checker reports 163 figures, 0 CUT, 0 RIM and 0 VANISH against black; that is not a guarantee against every scenery colour. Native captures confirm the palette and sprite alignment in play.

## Engine and pace

Pure screen XOR renderer at 43758, not Herbert's back-buffer engine. The family lessons reused are painting/export safeguards, sprite caching, speed restoration and R preservation. Patterns use four pages and a 128-slot cache. Hooks run at 28 MHz and restore the incoming speed; all other game code, beeper routines and counted delays remain unchanged. The original has interrupts disabled during gameplay and uses R-based randomness. There is no AY music in this release.

Player-update probe 43900; ten paired trials per scene, 180 requested updates. Start-room pokes are only in disposable measurement fixtures.

| Scene | Completed trials | Mean matched-update slowdown | Mean hook time/update |
|---|---:|---:|---:|
| Quiet room 0, no input | 10/10 | 1.6554% | 0.6151 ms |
| Busy room 3, walking | 10/10 | 1.2408% | 0.5137 ms |
| Sound room 14, walking/jumping | 9/10 | 1.6183% | 1.1005 ms |

Default and Enhanced timing is identical in every trial. Sound seed 2 diverges by one movement step at update 64 after a frame-sampled key release; its 63 matched updates are recorded but excluded from the full-trial mean. The other sound trials range from 0.8340% to 1.7795%; busy trials from 1.1492% to 1.3707%. Quiet repeats are deterministic repeats, not independent random seeds. This is a small residual slowdown, not a zero-penalty or faster-than-original claim. No limiter was inserted because the hook-only build remains slower than the original.

Beeper writes match by value and player update; intra-note timing has at most 48 master cycles (1.714 microseconds) of jitter. Audio is not claimed bit-identical. Evidence: `jn/pace-final05/`, `work/pace-final05.log`.

## Verification

- Final default and Enhanced: each 62 recordings, 186,686 frames IDENTICAL, 548,249 plots, 83,125 waits, 363 room wipes and 127 whole clears. All hook types executed. `work/full-proof05/` (124 result files).
- 192/200 graphics reached by those recordings; all 200 exercised in 1,000 plot/edge cases. Also 400 pattern-cache recycling cases, full-list, two reset and setup checks: PASS (`work/art-unit.json`, final rerun).
- 224 incoming-speed/R combinations: PASS. 11/11 deliberate negatives caught, including wrong R compensation and forced 3.5 MHz exit (`work/clock-matrix.json`, `work/negatives.json`).
- 220-frame flicker check: zero out-of-step, one-frame vanish, attribute or picture transients (`work/flicker05.log`).
- Fifteen emulated minutes each original/build: no freeze, loop or crash; final picture sheet inspected (`jn/soak05/sheet.png`, `work/soak05.log`).
- Full hidden Sinclair ROM with writable hook RAM slot verified using deliberately wrong system-ROM bytes. Shared builder canary passed with unchanged Chuckie outputs (`work/canary.log`).
- Ordinary `auto` reproducibly builds the same banks. Packaged NEX files additionally contain the clean archive loading screen; stripping that screen/header flag gives exact auto output (`work/repro-auto.log`).

Coverage includes menus, deaths, game over/restarts, natural play and injected room starts. The game has not been solved; later unvisited paths and the ending are not claimed covered. Eight unreached graphics have unit coverage only.

## Loading screen, trainers and actual loader

Loading screen: clean archive `Pyjamarama (1984)(Mikro-Gen).tap`, MD5 `ab438ccb91300179372e097cd7133e98`; checked tape block checksum, original 6912-byte screen (`files/loading.scr`, `work/loading.json`).

Archive POK contains addresses for other releases. Three trainers were retained after inspecting this source's code: Infinite Lives (48683, DEC (HL) -> NOP), Infinite Energy (33835, INC A -> NOP), Immunity (33904 and 33767 -> RET). Verified original bytes and all six trainer/set combinations. `files/Pyjamarama-verified.pok` is the exact package input; trainer semantics were code-audited, not exhaustively played. Invalid gun/bucket pokes were omitted.

Host NXC apply reconstructs both outputs byte for byte. Actual dot loader was also run in JNext from fresh private SD image copies: Default menu OFF and Enhanced menu ON, original loading screen, then gameplay. Both actual `/tmp/NEXCLASH.NEX` outputs were extracted and match the hashes above exactly. `jn/real-loader/{default,enhanced}/result.json` and screenshots are the evidence. The user's real card was not written.

Package credit: Jon Attree, with standard Dean credit retained. No publication, upload, push or network operation was performed.

## Reproduce / owner edits

Use `pilot/venv/bin/python -B`, `PYTHONDONTWRITEBYTECODE=1`, and TMPDIR within this run. Local clone is `nexclash/`. `work/build_art.py` builds both screen-bearing candidates; `work/package.py` packages them (a fresh nonce can change the NXC hash). `work/full_verify.py`, `work/clock_negative.py`, `work/pace_trials.py` and `work/real_loader.py` hold the verification recipes. Do not rerun one-off source mutation scripts.

Edit only `out/pyjamarama_editable_v1.1/PYJAMARAMA_PAINTING_SPRITES.png` at native size using exact swatches. Keep its layout JSON and originals folder. The README's import command stages the proposed colour map; review it, rebuild, compare geometry and replay, then create a new package. Do not overwrite the owner's edited PNG during regeneration.


---

# Historical 2026-11-03 build notes (superseded by v1.1 above)

# Pyjamarama (Mikro-Gen, 1984, 48K) - engine `pyjamarama` (batch game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended; simulation and JNext only; never run on a Next.
Inputs: run folder (pyjamarama.z80 md5 1ff27975, ref/pyjamarama/*.rzx, sheets/)
Start with: the hardware checklist below on a real Next; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `detect.gameplay-screen-readers` (recipe and results: docs/records/pyjamarama.json)

## Inputs
Snapshot: archive "Pyjamarama (1984)(Mikro-Gen).z80", md5 1ff279754d0730e503816199ac6976f3, no [t], [h], [c] or [a]. ZXDB 0003949 from pilot/eye-check-candidates.json; the filecheck lookup answered 502 this time, so not re-confirmed. 48K. No 128K release seen in the archive. One load: all rooms in the file.
It stands at the title ("press a key"), though `inspect` calls it a loader: PC at the ROM's IM 1 handler, stack into the game. Keys: any key, then ENTER at the menu. Defaults O left, P right, M jump or use. 1 and 2 pick joysticks, 3 defines keys; no menu option changes the drawing.
Recordings, no Fuse and no human: work/rec.py, random walks. Cheats change bytes in the RZX's own snapshot, never a build: 33904 + 33767 RET (immunity), 33835 NOP (energy), 45839 the first room.
| Recordings | Cheats | Reach |
|---|---|---|
| p_o1, p_o2 | none | rooms 1-3, deaths by enemies, game over, title, restart |
| p_r00-29 | immunity, energy, first room 0-29 | every room 0-29, 1,200 frames each |
| p_s0-29 | the same, other seeds | the same, 4,000 frames each; also the walk into room 30 |
Plot callers: 96 of 111 reached with a figure; 11 more ran on the ULA as items and icons. NOT reached: 60073, 60082, 60094, 60103 (graphics 115, 116, only with an item held). Graphics 136, 137, 139, 140 never drawn. The game was never solved: rooms walked at random, items picked up only by chance, rooms 31+ and the ending not reached.

## Clash
Kind A. work/census2.py at the end of each pass on 32 recordings: 24 % of plots of figures other than the player span several attribute values, so a figure's pixels change colour as it crosses scenery. The player paints a bright-yellow block over 2-3 x 4-5 cells (three LD (HL),70) wherever he stands: a yellow rectangle over walls, doors and floor. Others have no colour of their own: they take the cell's ink. Owner's eye: clash. Numbers agree.

## Rendering model
Pure XOR plotter to the screen. 43758: A graphic (16 x 16, 1 bit, at 37355 + 32A; 200 graphics), x at 43755, y at 43756, row table 36971, three byte writes per line. A second identical call rubs out. All game figures, items and icons go through it, 111 call sites. Main loop 45900 ends in the delay routine 44092 (BC = 3500), which all animation loops call. Interrupts off in play (the plotter's own DI; the title and menu run with IM 1, ROM below 0x2000). Logic reads no pixels; attributes only at 44900-44918 (saving the player's block) and 49317 (the cell under his feet, below his block): checked at every read. 57896 clears the play area on a room change, 44969 the whole screen. ROM 0x2000-0x3FFF never touched, on all recordings.

## Design (defaults, unattended)
| Site | Original | Now |
|---|---|---|
| 43758 | DI, PUSH AF, PUSH HL | JP e_plot: figure -> writes off, toggle (A, x, y) in the list; item or icon -> writes on |
| 43840, 43844, 43848 | LD (HL),A | run-time: 77 or NOP, set per plot by e_plot |
| 44092 | PUSH BC, PUSH AF, LD BC,nn | JP e_wait: the list as sprite attributes, if changed; then the same, nn read at run time |
| 57896, 44969 | start of the clears | JP e_wipe, e_clr: list emptied, sprites hidden |
| 44902, 44908, 44920 | LD (HL),70 | LD (HL),A + NOP: the block is saved as before, nothing painted |
Every register and byte of game memory stay as the original's, sites and the screen apart. Hooks in RAM page 24 at slot 1, whole game, own stack. 164 figure graphics exceed the 128 4-bit pattern slots, so patterns are uploaded when first needed from pages 26-28 (mapped at slot 3 only during the OTIR, interrupts off), round robin, never a slot on show. List 32 figures; the recordings reach 8. Tail at 0x8110, zeros, never touched.
Figures = graphics 0-75, 77, 78, 114-199. Stay on the ULA: 76, 79-113 (lives icon, items, lift arrows), and anything above line 40.
Speed: plot hook 817 T mean, 6,455 max with an upload; commit 1,097 T mean, 1,500 max, against about 147,000 T a pass with 6.6 plots: about 4 % slower by this count, not measured on hardware. At the game's own 3.5 MHz. No frame sync, as in the original: the delay is a counted loop.

## Differences from the original, by design
1. No yellow block round the player. 2. Figures keep one colour and do not cancel with scenery: over ink pixels the original inverted them, so they showed dark on bright; a sprite covers. 3. See-through: only the graphic's own pixels, as there is no mask. 4. A tile drawn over a live figure (rooms 0 and 28: 1,424 screen bytes, on cheat starts and the rare falls past the wall) cuts the figure in the original and leaves XOR garbage when it moves; the sprite stays whole and in front. The verifier computes this per byte, it is not a tolerance.

## Colours and what vanishes
Default per graphic: the ink of the cell the game most often draws it in; the player's own bright yellow (70). Nothing painted. Sheets in run folder sheets/; recolour tested (paint/).
FLAG for the owner, frames in run folder png/ (each original left, sprite build right; drawn from the verifier's patched screen and sprite list, not JNext):
- png/vanish_bird_room2.png: the bird (graphics 147-152) is bright yellow and disappears over the solid yellow cupboards in room 2 (98 % of its pixels fall on its own colour) and much of the way in room 17 (65 %). The original inverts it to black there, so it was visible.
- png/vanish_insect_wally_room19.png, lower pair: the player over the yellow bath in room 19 keeps only his outline against black; the body merges (66 % of his pixels). The insect (144-146) merges there too (83 %).
- png/vanish_wally_room14.png: the player against yellow furniture in room 14 (68 %).
Averages stay low (7-9 % of pixels at worst for the player, 18 % for the bird in room 2), but these moments are real and the player in the bath is the one to judge. The colour route or a dark outline would fix it; that is the owner's decision, so nothing is painted.

## Results
Stamped by selftest.py --game pyjamarama --verify --stamp: SELFTEST PASSED, log in run folder work/stamp. Totals over 62 recordings, 186,686 frames, every recording IDENTICAL:
plots 548,249 (figures 546,098, ULA 2,151); figure draws 273,811, erases 272,287; waits with sprites, patterns, screen and attributes compared 83,125; wipes 363; clears 127; 35,548,737 sprite pixels; attribute reads checked 963,132; other screen writes modelled 2,906,923; most sprites 8.
Hooks that ran, on every recording: e_plot, e_wait, e_clr; e_wipe on all with a room change. 44902-20 ran 888,911 times. No hook never ran. Real patched plotter, to its RET, on every plot; real commit, wipe and clear on every event.
Unit: plot cases 1,000 (every graphic, 5 position edges, draw and rub out), full list, pattern recycling 328, clears 2, setup: PASS.
Negative controls on p_r03, all detected: figure writes on 672 failures; hook clobbers HL 12,566; x bit 8 lost 112; half slot dropped 1,694; old sprites stay 359; upload to the wrong half 3,446; list never removes 670; player paint stays 517; room change leaves sprites 462.
JNext 1.1.104 headless: plain 19c7f0ac and sprites 3b917bec reach play; jn/ shots viewed (p1, s1, s1s, s1b, s3, s3s, s4: game over back to the menu, no figures left); figures are the sprite layer's. Hardware: none.

## Defaults taken (a human would have decided)
1. Every moving figure a sprite, including static hazards and energy items drawn by the same plotter (graphics 114-199). 2. Items and icons stay on the ULA (they are static and never crossed scenery). 3. Depth: all figures over the scenery; no behind. 4. Colours as above. 5. See-through bodies, no outline. 6. Figures hidden during a room change, as the original wipes them.

## Lessons
- [local: owner-edited Pyjamarama coins] The owner requested flat orange edging on graphics 85 and 100; the accepted revision changes only 56 existing ink pixels. The supplied PNG and exact import comparison are retained under work/owner-import01.
- [local: a XOR plotter's own NOPped writes keep every register] The A and B the patched writes read differ, but both are POPped before the RET, so no emulation was needed: the plotter runs on.
- [local: tiles over live figures look like a failed check] Rooms 0 and 28 failed until the model tracked figure bits lost per byte.
- [local: 164 graphics in 128 slots] An upload-on-demand cache cost little: 6,455 T at worst, rare.
- [local: the .pok is for another release] Its Lives and Energy addresses do not fit this file's code; only those whose bytes make sense were imported.

- [local: a colour map can keep only the painting] the check byte per entry is null in the stored maps (pyjamarama_colours.json, pyjamarama_enhanced.json); the engine reads the image byte from the player's snapshot instead. Null them again after importing a repainted sheet.

## Friction

- reuse: [local: Pyjamarama owner artwork] Reused the existing native-pixel sheet, guarded import, pattern build and real-loader recipes.
- retries: [deferred Open: reconsider when screen-bearing repaint is promoted] The screen-bearing NEX needed its loading payload separated before colour replacement and restored afterwards; the full build independently matched it.
- environment: [local: isolated owner revision] All builds and private loader cards stayed in this run. No network refresh was permitted; base remains bd1528cf.
- hand-rolled: [local: these two coin edits] The owner PNG had blended orange ink and grey-background spill; a staged copy snaps only the 56 changed ink pixels to orange and restores the 91 background pixels. The upload is retained.
- scratch: [local: reproducible owner revision] The run keeps import_owner01.py, verify_owner01.py, accept_owner01.py and real_loader_owner01.py with inputs and results. These scripts are specific to this source and revision.

## Technique use
- detect.gameplay-screen-readers: helped: scan on all recordings shows no logic reads pixels.
- optimise.pattern-cache: helped: the round robin above.

## Hardware checklist
1. Loads to the title; any key, ENTER: the hall, Wally walks with O and P, jumps with M.
2. No yellow block round him; the door stays magenta when he stands at it; the ball stays yellow across the green rail.
3. Room changes: no stale sprites; items pick up with M; HUD icons fine.
4. Death: the ghost rises as sprites; game over, title, restart: no figures left over the screens.
5. Bird over the yellow cupboards in room 2: judge the vanish flagged above.

## Stage log
- 2026-11-03 stages 0-3 in one session (batch, unattended): about 40 min, about 45 tool calls, 0 user rounds.

## Open
- Owner artwork import follow-up: support screen-bearing NEX files directly if this private repaint workflow is promoted; current owner revision preserves the original screen by verified extraction/reinsertion.
- Hardware, CSpect: never run.
- Game never solved; the 4 unreached callers; rooms beyond 30.
- Bird vanish: owner's call.

## Solid build (owner, after playing: "colour clash gone", see-through body showed door stripes; outline black at his request)
Run folder out/pyjamarama_sprites_solid.nex md5 a8f02d1c, by recolour with paint/solid_colours.json (work/solid.py); only pattern banks 13, 14 differ from the verified 3b917bec, so no full re-verification; p_o1, p_r03, p_r14, p_r19 re-run with these patterns: no failures. Not the record's default build.
Inside = flood from outside on the joined top + bottom, 1-pixel gaps sealed (a plain flood leaked: 23-49 pixels against 74-90 sealed, steady across all 46 pairs); black. Every drawn pixel kept. Black outline, 1 pixel. Bottoms shared by two tops take what both agree on. Others: fill; black outline unless small (134, 135, 144-146, 159, 160, 165-168, 173, 174, 178).
Limits: no room in a 16 x 16 pattern where ink touches its edge, so the outline is open there (all 46 pairs, about 10 pixels, plus under the feet). On black rooms a black outline shows nothing, so he looks as before there.
Vanish: bird on cupboards and player on bath and furniture fixed; the insect (144-146) over the bath remains, as it is small and thin. JNext: png/solid_vs_default_jnext.png, evidence builds with start-room pokes in jn/, never released.
