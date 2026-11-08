# Renegade (Imagine, 1987; 128K release) - engine `renegade128` (batch game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: pace review build 1.2 (2026-11-08, section Pace), owner's play pending; imported into `refactor` 2026-11-04 (phase 7); stages 0-3 done unattended in
Jon's run folder; simulation and JNext only; never run on a Next.
Inputs: specnext/reference/renegade/ (start.z80 md5 1a931038 staged as renegade.z80, the archive renegade128.z80,
4 bot .rzx, renegade_enhanced_colours.json, renegade128.pok)
Start with: the hardware checklist below on a real Next. Read: this file. Open: everything under "Open".

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04: the run's clone (pilot runs/renegade/nexclash, 99451b9..361f529 on
d7abd1c; the 128K engine only) brought onto `refactor` 884d31a. Record, folder and this file are `renegade` (the
game); the module stays `renegade128`. The 48K-128K file's engine `renegade1` (games/renegade.md of that clone) is
not imported. Published .nxc: **Renegade v1.0** (github.com/jattree/nxc, patch md5 b3530132; Jon Attree; credit
Dean Woodyatt / NexClash; Enhanced colours from the MVV package's older Spec256 conversion). `nxc.py --bare` of it
on the archive file gives default a670c5b1 and Enhanced 82b45f46: `auto` on start.z80 builds both byte for byte
(plain 62a06036). The .nxc accepts the archive file because game RAM is the same in all eight banks (below).
- Moved in as it was: nexclash/renegade128.py, asm/renegade128_hooks.asm, docs/profiles/renegade128.json. It still
  imports Dean's `renegade` (Target Renegade) for boot_check, unchanged. RECOLOUR's game is now `renegade` (the
  record), so selftest's recolour guard runs for it.
- Pinned: `"pin": {"altrom_fill": "rom3"}`. Alt ROM hooks; the approved build used the fill before 2026-11-04.
  Today's default gives sprites cec3e894: a rework, not this build.
- Moved into the engine from the run folder: the Enhanced build (work/paint.py's last step: `enhanced_nex` =
  recolour() + sprite palette entries 4-15 in the setup stub's palette (bank 10) + the floors table (bank 12), the
  44 bytes in the profile's "enhanced" section). The colour map itself (14,575 entries, from the .256) carries the
  note "local only": it is not in this repo; specnext/reference/renegade/renegade_enhanced_colours.json, staged
  beside the snapshot as a record input. Without it `auto` builds no Enhanced set.
- Not replay-verified separately: the Enhanced set is recolour() of the verified build (colour banks, palette,
  floors); the recolour guard proves recolour() matches the builder. As in the run folder.

Techniques: `detect.gameplay-screen-readers` (recipe and results: docs/records/renegade.json)

## Inputs
Snapshot: archive "Renegade (1987)(Imagine)(128K).z80", md5 9432bbad61d76f7e2a6e1a079c0f363a, ZXDB entry 0004082 from eye-check-candidates (api.zxinfo.dk answered 502 earlier that night). It waits for a key in the 48K ROM with the loading screen up, then the game's code runs. start.z80 is that machine run on to 31814, after the game's unpack: no BASIC, as target_renegade. Game RAM is the same as the file's in all eight banks, so the patch accepts the archive's file.
Keys: a key leaves the loading screen. 1 keyboard. In play K left, L right, Q up, A down, SPACE fire, S pause. This release has a developer key: 0 goes to the next level (32814); it is in the original too.
Recordings (no Fuse, no human; renegade128/work/rec.py; pokes in the RZX's own snapshot, never a build):
| Recording | Pokes | Reaches |
|---|---|---|
| nocheat | none | first level, deaths, game over, menu, restarts |
| levels | infinite lives | all four levels by the 0 key, and round again |
| nodeath1 | no death, infinite lives | all four levels by the 0 key |
| run2 | no death, easy fight, infinite lives and time | by play, no skip: all four levels, past the last boss, into a second time round. The ending frames were not looked at |

## The model, and what differs from renegade1
The same composer and data as the 48K-128K file (renegade1: games/renegade.md of the run clone, pilot runs/renegade/nexclash), at other addresses (renegade128/work/align.py aligned the routines with operands wild). Levels are not packed: 40536 copies a level from banks 3, 4, 6, 7 to bank 0 at 0xC000, by HALT and 976-byte slices through 0x6000. Frame table 0xF900, tiles 0xF400, map (42230), list 41974, level 28872. The interrupt handler pages bank 1 and plays the AY music, and touches slots 3 to 7 (renegade128/work/isrslots.py).

## Design (defaults, unattended)
| Site | Original | Now |
|---|---|---|
| 38673, 38812 | LD (DE),A | LD A,(DE): the buffer and the screen only get scenery |
| 32834 | LD HL,49126 | once a tick: list -> sprites |
| 32800 | CALL 42314 | the same, before the tune at the start of a life |
| 39940 | LD HL,16384 | screen clear: all sprites off |
| 38833 | LD IX,(42230) | play area redraw: all sprites off until the next tick |
Patterns from every level's data, by running the game's own 0 key in a simulator at build time, then found by address and checksum (or by address alone, this level's first, if the game has poked the graphic). State page 22 at slot 2, which the handler never touches. Pattern page in its place while uploading, interrupts on (to 1.1: slot 6, interrupts off, since the handler remaps slots 6-7).
Why slot 2: the first version kept the state at slot 3 with interrupts off in the whole hook. In JNext its game timer ran 36 % fast: 19 seconds in 14 of emulated time, against 14 in the plain build. Moved to slot 2, with interrupts on, it is 14. The cause of the extra interrupts was not found; I do not know whether a real Next would do the same.
Outline: one pixel round each figure, nibble 3, in margins of the patterns, never over the figure: white, black on the second level where the body is white. Not on what is too small: W <= 2 and R <= 16. Verify and unit tests see through it. A figure is two parts, each outlined alone, so a join would show as a line: the owner saw one down the middle of the riderless bike, and it was also at the waist of figures. The build takes each frame's two parts from the frame table, as 37682 places them, and drops outline pixels that lie on the other part or in the seam beside it (join_drops: 3,749 pixels in 260 graphics; a graphic used in several frames loses a pixel if any frame needs it). Unit check: join_faults, 0 left.
Start: PC at a stub in the alt ROM, screen up: a key, or about 5 seconds, then JP 31814. No game memory touched. The screen is the snapshot's own, so nothing is added to the .nex's screen area. The plain .nex has no hold and starts at the menu.
Colour: entry 1 black; entry 2 the body, the level's floor paper; entry 3 the outline. Entries 10-15 per level, for Enhanced.

## Results
Today's tree (`selftest.py --game renegade --verify --stamp`, 2026-11-04, after the import): rebuild = recorded
(plain 62a06036, sprites a670c5b1, Enhanced 82b45f46 = the .nxc v1.0); recolour guard OK; hook profile = pinned
sjasmplus. nocheat 12,007 frames, levels 18,012, nodeath1 26,013, run2 50,023: IDENTICAL (screen checks with a few
bytes different 0, 0, 0, 7, as before); unit 3,544 positions PASS; negatives 13 of 13 on nocheat. Stamped verified
(run on a scratch copy of this tree, every dependency the same hash; here `--plan` says unchanged, rebuild OK).
Run folder: stamped by `selftest.py --game renegade128 --verify --stamp`, build a670c5b1 (plain 62a06036). Report: renegade128/work/stamp/start_report.txt in the run folder.
4 recordings, 106,055 frames, IDENTICAL. Every hook ran on each. Screen checks that differ by a few bytes: 0, 0, 0, 7. Most sprites 82 of 124.
Unit: all graphics that fit, 3,544 positions, PASS. One graphic, second level 0xD25A, 4 x 31, is too big for its 6 pattern slots and would be dropped: never drawn in any recording. Negative controls: 13 of 13 detected on the real recording.
JNext 1.1.104: original, plain and sprite reach play; the sprite build reaches game over, the menu and a restart. Timer against the plain build: 14 seconds in 14. Bosses in Enhanced seen in test builds started from mid-game states (renegade128/work/snapnex.py), which show the original's figures on the ULA until each is redrawn. Those are never packaged.

## Enhanced colour set
Colours from the MVV package's older Spec256 conversion, painter not established. The .256 is the 48K file's, so its level graphics come from renegade1's run of the loader on the emuspec256 model (work/lv256.js, paint/lv). Each 128K graphic takes them by renegade128/work/paint.py:
- bytes identical: 205 graphics. A few bytes different: 6. The same picture shifted by whole pixels: 8, by position.
- 57 others have no match: best pixel overlap, 0.64-0.83, a guess. They were never drawn in any recording, including the whole game: work/nm.py. They look unused. If one is ever drawn, its colours are approximate, but it will not be half-painted.
Index 0 on an ink or body pixel is black, as the model shows it. So the last boss is a black figure in jeans. Shared graphics use 6 fixed colours, a level's own 6 more of its own: 25-31 mean RGB error per level, against 34 with one palette.

## Cheats, renegade128.pok
The archive's and the owner's `[128K]` pokes do not fit this release: their sites are 2 to 11 bytes off, and some would break code (39804 is in a CALL). So they are redone for it, tested by bot and in JNext:
| Trainer | Poke | Seen |
|---|---|---|
| Infinite lives | 40468 DEC (HL) -> OR (HL) | lives held after deaths, JNext |
| Infinite time | 39785 SUB 1 -> SUB 0 | 2:15 after 3,000 frames, JNext |
| No death | 33411, 35822 -> RET | energy full, lives held, 5,000 frames idle, JNext |
| Easy fight, one-hit falls | 36978, 37011, 34797: punch strength 40 | second level by scripted keys in 6,000 frames with No death, JNext |
| Start at level 2, 3, 4 | new game calls a stub at 0x6900: level k-2, JP 40493, the game's own next-level path | each reaches its level in JNext, sprites and Enhanced |
Hard Punches is left out: Easy fight does what it would, and the archive's site did nothing here. Cheats have been run in JNext, not played by a person.

## Stays on the ULA
Scenery, HUD, menu, text. Nothing that moves.

## Defaults taken (a human would have decided)
Every part a sprite. Outline on, per the owner's standing preference. Body = the floor's paper. Solid bodies. Game's own depth.

## Open
Never run on hardware. Upload timing, 28 MHz hooks and K windows with the AY handler inside them, ROM selection at 7FFD = 0, and the floating bus wait are unmeasured on a real Next. The 36 % above is not understood. Music not listened to: headless. Joysticks not exercised. 0 still skips a level, as in the original.

## Hardware checklist
Loading screen; a key or 5 seconds; menu; 1. Music plays and keeps time. Timer counts seconds at the plain build's rate. Figures keep their colours across scenery, with outlines. Each trainer. Game over, menu, restart. Enhanced from the menu: all four levels, no half-painted figures.

## Pace (2026-11-08, review 1.2): K windows, R kept, skips back to the original's
Owner's pace rule: within 2% of the original where it runs steadily; never slower. 1.1 broke it (audit: runs/pace-audit-20261108), and the bigger fault was
not the figure: the game's time-slicer 0x8117 skips the fighters' logic once an update is past its 3 frames, and 1.1 tripped it in 63, 40, 78, 3 of 600 updates
against the original's 8, 1, 1, 0, so it played differently. Hook time 4 to 9 ms sat at the top of each update, before the slicer. Game order per update: frame
sync (bit 7 of 0x70CC, set by the third interrupt), commit (0x8042), logic and composing, slicer readings at 0x8117, sync. No time can be saved in the composer:
it waits on the real beam (0x98ED, floating bus), with the game's tone in the loop.
- Memo (m_look / m_put, 256 entries in the state page): a graphic seen in this level and wave takes no checksum; 150 T against up to 1 ms.
- Interrupts stay on through uploads: the pattern page takes the state page's place at slot 2, which the handler never reads. 1.1's DI at slot 6 lost interrupts,
  each a 20 ms lag for the game and for the music. Slot 0 instead of slot 2 hangs JNext: an interrupt there goes astray, cause not established.
- K windows (w_arm, w_cont, w_end; lib/hlib_pace.asm whole, unchanged, in the state page): the commit's time goes to the debt; the code after it runs at 28 MHz until the
  debt is repaid. A window ends at the raster wait (the CALL's operand 0x967C), the slicer's reading 0x8117 or 0x812B past it. These hold the game's own bytes unless a
  debt is open, so an update in step pays nothing. K 106 = JNext's 6.6; the window's own hook time goes to the debt by W_PASS and W_FIX, as K would scale it. One window goes on
  across raster calls whose flag is clear: each reading is a line at best, about 0.4 ms after K, so fewer windows are nearer. w_model follows the wait in both games: both
  in the border leave together (debt 0), only ours (+ its spin), only the original's (- its spin).
- A tick that starts within 24 lines of the interrupt spun at the sync, so it is in step: debt 0. The tune at a life's start opens no window (D = 1 at e_start). A window left
  open by a jump out of the tick ends at the next hook. Another speed set by the player: no window.
- Pace, JNext, input keyed to updates, 90 state addresses, against the plain build (62a06036). Default and Enhanced read the same in every run.
  all / quiet third / busy third (fastest, slowest stretch of 20):

| run | 1.1 (510cdd29, Enhanced 001b8f0c) | this (b4b45210, Enhanced 9ed0c98b) |
|---|---|---|
| seed 1, R + slicer fixtures | +1.82 / +0.31 / +4.48 (-3.3, +10.7) | -0.32 / +0.06 / -1.00 (-2.9, +0.4) |
| seed 2, same | +1.26 / +1.48 / +0.76 (-1.9, +9.1) | -0.05 / +0.18 / -0.22 (-1.8, +1.7) |
| seed 3, same | +0.51 / +1.26 / +0.36 (-0.9, +6.9) | +0.00 / +0.23 / -0.14 (-0.4, +1.6) |
| seed 4, same | +0.00 / +0.04 / -0.09 (-0.6, +0.6) | +0.00 / +0.02 / -0.06 (-0.3, +0.3) |

  As shipped (R fixture only, the slicer live), skips in 600 updates, original / 1.1 / this: 8/63/8, 1/40/1, 1/78/1, 0/3/0, and new seeds 5, 6: 8/80/5, 1/81/1. Lockstep at every one of
  the 600 updates on seeds 2, 3, 4, 6; seeds 1 and 5 part at 395 and 156, each at one skip that goes the other way in an update already overrunning, where
  the line-based reading cannot place it (0.1 to 0.5 ms). 1.1 held on seed 4 only, and parted at 103, 27, 199, 15, 181.
  AY writes a second equal within 1% (549 / 547 seed 1), port 0xFE writes 41 / 40, interrupts 49.89 / 49.75 (1.1: 49.28), longest gap 40.5 / 40.5 ms (1.1: 60.8).
- R: compared at every hook now (CMP includes 15; lib/hlib_r.asm unchanged; D_ constants counted). In play R is not equal between arms all the same: the frame sync spins on R-counted
  instructions for a time set by the beam, in the original as well, so lockstep runs keep the audit's R fixture. e_front (the start stub) is not compared: it holds a key wait no
  recording runs.
- Later levels (the game's own 0 key at updates 150, 330, 510, in both arms, 720 updates, seeds 1-4): whole -0.13 to +0.12, busy -0.21 to +0.19, slowest stretch +1.7, fastest -4.7 where the original lags; skips 11/10, 1/2, 23/22, 1/1 (original / this; 1.1: 69, 18, 31, 6); 2 seeds in lockstep throughout, the others part at 379 and 395. Bosses are not reached.
- Timing is JNext's. K, W_PASS and W_FIX are tuned on it; on hardware the windows' timing may differ, and an error there moves a skip, not the pace.
- Checks: `selftest.py --game renegade --verify --stamp`: 4 recordings, 106,055 frames IDENTICAL, R compared; unit 3,544 positions; 18 of 18 negatives, 5 new: a window that never waits, a slicer hook left in, the memo's wrong entry, R off by one after a commit and after a window. Stamped. Enhanced is recolour() of this build, as before (guard, MD5), not replayed separately.

## Speed restored (2026-11-07, shared engine refactor, goal 2)
- commit and hideall latch the caller's CPU speed after mapping the state page (HLIB_SPEED_IN, lib/hlib_speed.asm: 4
  bytes of the game's stack, which the stubs already push on); leave writes it back before the slot-2 page instead of a
  fixed NEXTREG 7,0. V_SPD = 0x4D1E. The verifier answers IN (0x253B) from its NextREG model (NextState.sel); the
  "speed not restored" negative now removes leave's NEXTREG 7,A.
- Sprites 93cb8bc9 -> 510cdd29, Enhanced 3a9ceaf9 -> 001b8f0c; plain unchanged. Replay: see the record's stamp
  (4 recordings). JNext pace (600 updates keyed to 0x9332, seed 1, keys K L Q A SPACE): +0.48% before and after
  (quiet +0.07%, busy +0.66 / +0.67%); interrupts 50.00 a second in all three, longest gap 20.3 ms.

## Lessons
- [card patch.restore-speed §Use / do not use] A hook on the game's stack latches after its page switch (the latch
  byte lives in that page); the stubs' pushes already make room for the macro's 4 bytes.
- [local: time a build against the plain one on the game's own clock: a fast timer in JNext showed what the replays could not]
- [local: the .pok in the archive names a release loosely: check each poke's site against the disassembly before importing it]
- [local: the same .256 serves another release by matching graphics by bytes, then position]
- [local: the approved Enhanced came from a run-folder script] observed (import, 2026-11-04): the clone's record held
  only the default; work/paint.py's last step (recolour, palette, floors) moved into auto, the map kept private.
- [local: K window readings] A K window's reading holds the hook's own time, which K would scale: on a short window that is most of the error (0.5 ms for each). Put it in
  the debt as hook time x K, and keep one window going across hook sites rather than opening one per site.
- [local: Renegade's time-slicer: an overrun here plays differently, not just slower] Count the game's own skips against the original's as well as the percentage; they are what parted lockstep.
- [local: interrupts on through an upload] A pattern page at the slot of the state page, which the handler never reads, needs no DI; at slot 0 an interrupt went astray in JNext (cause not established).
- [local: a third-party colour map marked local only] observed (import, 2026-11-04): the Enhanced map stays out of
  the public repo as a staged record input; the profile holds only the 44 palette and floors bytes.

## Technique use
- detect.gameplay-screen-readers: helped: as renegade1.
- patch.pace-limiter: helped: lib whole, K windows.
- patch.preserve-r: helped: hlib_r whole, on the two exits' M1s counted by path.

## Stage log
- 2026-11-03: stages 0-3, one unattended session, no user rounds.
- 2026-11-04: import into `refactor` (phase 7, group 3) as record `renegade`: Enhanced moved into auto, pinned;
  rebuild = .nxc v1.0 byte for byte; full verification stamped. 0 user rounds.
- 2026-11-08: pace, review 1.2: K windows, memo, interrupts on through uploads, R kept; no user rounds, owner's play pending.

## Friction
- reuse: [tool asm/lib/hlib_pace.asm] whole and unchanged, in the state page, with lib/hlib_r.asm and lib/hlib_speed.asm
- retries: [local: K 128 from Ikari read 25% long here: 6.6 is what JNext gives on this game's logic] measure K first
- environment: [none: the pinned sjasmplus gave the profile's bytes]
- hand-rolled: [local: seg.py logs site times in both arms] the run folder's tools/; `python -m nexclash.pace` has no per-site view
- scratch: [none: import scripts stayed in the session scratchpad]
