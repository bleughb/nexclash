# Gunrunner (Cybadyne / Hewson, 1987, 48K)

## Next session
Stage: 4 (owner's play, then Enhanced). Hardware: untested. v1.0 review build, not published, not pushed; not wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Inputs: `Gunrunner (1987)(Hewson Consultants).z80`, MD5 c9d8ff6b87d413df486a42c988c7079e. The loading screen is the snapshot's own picture.
Build: `gunrunner.build(z80, nex)`, then the review run's `work/pkg.py`, `.nex` f409ce60 with the screen.
Pending: the owner's verdict on the mock-up; Enhanced stops there.

## Facts
- No 128K release in the archive folder: every Gunrunner dump is the 48K game, so this is the 48K beeper game.
- 19 levels (F230, 6 bytes each): odd levels play, even levels are the bonus run. Each level sets one attribute for the 26 x 16 play window (E67D table, byte E681): bright cyan, green, yellow or white, magenta on the bonus. The window is one colour on black in every level, so no figure can take another colour.
- Back-buffer composer: buffer 6A00, 34-byte rows; `AND mask, XOR gfx` plots, so every figure carries a black mask; D3C4 copies with a table of 125 rows under DI after a HALT at BEDF. Update head BD9F.
- The game reads R for randomness (BF1C, CDEE, D02E, D1B7).
- Keys read at C715: M right, N left, S up, X down, A fire, Symbol Shift poison, P pause; Kempston with Space for poison.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and do not claim a clash fix. So no hook and no site: only the ROM (Sinclair's whole 48K ROM as the alt ROM). No outline: figures already have their own black masks. The menu line reads "Original colours", as in Martianoids.

## Known issues
- Pace: whole runs +0.11 to +0.35%, quiet thirds up to +0.38%, busy thirds up to +0.70%, slowest 20 updates up to +4.01%. No hook runs and the clock never changes, so this looks like the game's update beating with the frame from a different start phase; not isolated.
- Runs without the test fixture leave lockstep after 113 to 205 updates, because the game reads R; the fixture reads R as a constant in both arms.

## Evidence (review run runs/gunrunner/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, nexclash.pace with input applied after the game's read (C1F2), fixture on both arms, 800 updates in lockstep at every update, 3 seeds at each of levels 1, 5, 9, 17. rom_paths over 26.11's ROM3 on two recordings (38,134 frames, all 19 levels by a test poke): every byte the game runs is as recorded, the tail never read before written. Boot exact with and without NEXLOAD, R included. Broken builds caught: R off by one, clock left at 28 MHz, a game byte changed, Next ROM3 copied as the alt ROM, no alt ROM at all. Soak 15 emulated minutes: no freeze, loop or crash, sheet viewed, input reached play. Flicker: none. Real .NEXCLASH loader on a private NextZXOS 26.11 card copy: default, each cheat, all cheats, output equal to nxc.py, reaching play.

## Hardware checklist
Nothing has run on a Next. To check: start-up to the title picture, keyboard and Kempston, beeper sound in play, one death, level 1 to the bonus, each cheat, a 1MB Next (top bank 47).

## Technique use
- patch.whole-altrom-image: used: the build's only change; no hook bytes over Sinclair's ROM, only the register block in its unused area.
- verify.update-locked-pace: used: lockstep runs with the input applied after the game's read.

## Lessons
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
- 2026-11-08 Stage 3: no-hook engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
