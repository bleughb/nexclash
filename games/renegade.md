# Renegade (Imagine, 1987; 128K release) - engine `renegade128` (batch game: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: imported into `refactor` 2026-11-04 (phase 7); stages 0-3 done unattended in
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
Patterns from every level's data, by running the game's own 0 key in a simulator at build time, then found by address and checksum (or by address alone, this level's first, if the game has poked the graphic). State page 22 at slot 2, which the handler never touches. Pattern page at slot 6 only while uploading, with interrupts off, since the handler remaps slots 6-7.
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
Never run on hardware. Upload timing, 28 MHz hooks with the AY handler inside them, ROM selection at 7FFD = 0, and the floating bus wait are unmeasured on a real Next. The 36 % above is not understood. Music not listened to: headless. Joysticks not exercised. 0 still skips a level, as in the original.

## Hardware checklist
Loading screen; a key or 5 seconds; menu; 1. Music plays and keeps time. Timer counts seconds at the plain build's rate. Figures keep their colours across scenery, with outlines. Each trainer. Game over, menu, restart. Enhanced from the menu: all four levels, no half-painted figures.

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
- [local: a third-party colour map marked local only] observed (import, 2026-11-04): the Enhanced map stays out of
  the public repo as a staged record input; the profile holds only the 44 palette and floors bytes.

## Technique use
- detect.gameplay-screen-readers: helped: as renegade1.

## Stage log
- 2026-11-03: stages 0-3, one unattended session, no user rounds.
- 2026-11-04: import into `refactor` (phase 7, group 3) as record `renegade`: Enhanced moved into auto, pinned;
  rebuild = .nxc v1.0 byte for byte; full verification stamped. 0 user rounds.

## Friction
- reuse: [none: the engine needed no shared helper to rebuild its bytes]
- retries: [none: the port rebuilt the approved MD5s first time]
- environment: [none: the pinned sjasmplus gave the profile's bytes]
- hand-rolled: [none: no scratch tool kept]
- scratch: [none: import scripts stayed in the session scratchpad]
