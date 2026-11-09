# Gunrunner (Cybadyne / Hewson, 1987, 48K)

## Next session
Stage: 4 (owner's play). Hardware: untested. v1.1 review build (default and Enhanced), not published, not pushed; not wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Inputs: `Gunrunner (1987)(Hewson Consultants).z80`, MD5 c9d8ff6b87d413df486a42c988c7079e. The loading screen is the snapshot's own picture.
Build: `gunrunner.build(z80, nex)` and `gunrunner.build_enhanced(z80, nex, set)`, then the review run's `release-20261108b/work/pkg2.py`, default `.nex` f409ce60 with the screen, unchanged from v1.0.
Pending: the owner's play. A per-level tint of Enhanced is a later mock-up idea; the set has one look for every level.

## Facts
- No 128K release in the archive folder: every Gunrunner dump is the 48K game, so this is the 48K beeper game.
- 19 levels (F230, 6 bytes each): odd levels play, even levels are the bonus run. Each level sets one attribute for the 26 x 16 play window (E67D table, byte E681): bright cyan, green, yellow or white, magenta on the bonus. The window is one colour on black in every level, so no figure can take another colour.
- Back-buffer composer: buffer 6A00, 34-byte rows; `AND mask, XOR gfx` plots, so every figure carries a black mask; D3C4 copies with a table of 125 rows under DI after a HALT at BEDF. Update head BD9F.
- The game reads R for randomness (BF1C, CDEE, D02E, D1B7).
- Keys read at C715: M right, N left, S up, X down, A fire, Symbol Shift poison, P pause; Kempston with Space for poison.

- Spec256 set "Gun Runner", painter Jao Paulo (readme). 93.44% of 7B00-FFFF equal in place, the rest variables and self-modified operands; nothing differs 820D-BD4E. 584 of the 8,322 source bytes used differ, all save areas or the menu-time table DF0C-DF2B: no play graphic. Its background image is empty.
- The BASIC loader runs on the ROM, so hook veneers may only sit in Sinclair's unused 0x3870-0x3BFF.

## Enhanced
Off by default, on the menu. The play window on a double-buffered Layer 2 (x 24-231, y 49-173) over the game's own ULA picture. A colour canvas holds, for RAM address A, 8 pixels at page 14 + A/1024, offset (A & 1023) x 8, from the set's planes; AND / XOR per pixel on 8-bit values are the set's plane operations. Hooks mirror each write to the buffer (figures, tiles, stars, bullets, save and restore, fill, scroll, clear, the 34-byte row copy) and publish at the copy. Pixels 192-255 follow the level's attribute as the set's renderer mixes them: 16 tables reloaded on an attribute change. Pace: bodies at 28 MHz in windows with computed targets; long windows with measured constants, biased about 5% fast so a window near a frame's edge does not miss the HALT (section Lessons). Fits a 1MB Next: top bank 47.
Left in the original colours, listed in the .nfo: the panel, title, menus, level text. The set paints them; the panel's lit items are attribute-driven and would be lost.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and do not claim a clash fix. So the default has no hook and no site: only the ROM (Sinclair's whole 48K ROM as the alt ROM). No outline: figures already have their own black masks. The menu line reads "Original colours", as in Martianoids.

## Known issues
- Pace: whole runs +0.11 to +0.35%, quiet thirds up to +0.38%, busy thirds up to +0.70%, slowest 20 updates up to +4.01%. No hook runs and the clock never changes, so this looks like the game's update beating with the frame from a different start phase; not isolated.
- Runs without the test fixture leave lockstep after 113 to 205 updates, because the game reads R; the fixture reads R as a constant in both arms.

## Evidence (review run runs/gunrunner/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, nexclash.pace with input applied after the game's read (C1F2), fixture on both arms, 800 updates in lockstep at every update, 3 seeds at each of levels 1, 5, 9, 17. rom_paths over 26.11's ROM3 on two recordings (38,134 frames, all 19 levels by a test poke): every byte the game runs is as recorded, the tail never read before written. Boot exact with and without NEXLOAD, R included. Broken builds caught: R off by one, clock left at 28 MHz, a game byte changed, Next ROM3 copied as the alt ROM, no alt ROM at all. Soak 15 emulated minutes: no freeze, loop or crash, sheet viewed, input reached play. Flicker: none. Real .NEXCLASH loader on a private NextZXOS 26.11 card copy: default, each cheat, all cheats, output equal to nxc.py, reaching play.

## Hardware checklist
Nothing has run on a Next. Enhanced also: the window against the panel, no tearing, DMA on a real core, the flip outside the window's rows, pace by ear against the 48K original. To check: start-up to the title picture, keyboard and Kempston, beeper sound in play, one death, level 1 to the bonus, each cheat, a 1MB Next (top bank 47).

## Technique use
- patch.whole-altrom-image: used: the build's only change; no hook bytes over Sinclair's ROM, only the register block in its unused area.
- verify.update-locked-pace: used: lockstep runs with the input applied after the game's read.

- patch.preserve-r: used in Enhanced: every hook leaves R as the original; the replay compares it at each hook.
- patch.display-atomic-switch: used in Enhanced: two Layer 2 buffers, the flip outside the window's rows.

## Lessons
- [local: frame-locked pace] A game that HALTs to the frame turns a small lateness into a whole frame: a window on target can cost 20 ms for stretches, depending on phase. A change of a few ms at the start of a run moved the slowest 20 updates from +2.6% to +20.9% with no slower code. Bias long windows fast and re-measure at every level after any byte change, however small.
- [local: replay caught a real bug] The per-level replays found the canvas clear covering the wrong span, leaving stale pixels after a restart; the shorter recording had passed. Replay every level before calling a build frozen.
- [local: stale builds] A pace script that builds its fixture only if the file is missing measured a build from hours earlier under a reused tag. Use a new tag per measurement and build once before the runs start.
- [local: no-hook engine] A monochrome game needs no site; the checks that still mean something are the boot compare with R, rom_paths over the system ROM and the tail reads.
- [local: rom_paths on test pokes] A recording with test pokes keeps sync when each poke starts a new segment from its own snapshot; rom_paths says so in its lines.
- [local: R-reading game] Without a fixture a game that reads R leaves lockstep whatever the build does: the two arms start at another raster phase.
- [local: survey keys] A survey key schedule at the title proved nothing: this game's menu needs a key to pass the picture, then one to pick the controls. Look at the screen first.

## Friction
- reuse: [none: nextboot, jnext, soak, flicker and pace were enough]
- retries: [local: start keys] Pokes on the game's menu were applied after the key that started the game, so the test level did not take.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3 again: Enhanced on the review branch, Spec256 colours, proofs on the exact bytes; waiting for the owner's play.
- 2026-11-08 Stage 3: no-hook engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
