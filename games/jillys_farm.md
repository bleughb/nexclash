# Jilly's Farm Volume 1 - SokoBAArn! (Bob's Stuff, 2017, 48K)

## Next session
Stage: 4 (owner's play, then Enhanced). Hardware: untested. v1.0 review build, not published, not pushed; not wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Inputs: `Jilly's Farm Volume 1 - SokoBAArn! (2017)(Bob's Stuff).tap`, MD5 86a5e1dc43e4cfe45582e91eb7cd1cf3. The start state is the tape loaded by SkoolKit's tap2sna to the game's USR 33280 (`-s 33280`), kept in the review run.
Build: `jillys_farm.build(start.z80, nex)`, then the review run's `work/pkg.py`, a TAP1 target of the plain tape.
Pending: the owner's verdict on the mock-up; Enhanced stops there.

## Facts
- A later homebrew, shown as V1.01 on its menu. A BASIC loader, a screen and one code block, unprotected.
- An isometric Sokoban: 30 levels, each play window bright white on black (all 14 rows, level 1 to 30 by the game's own codes). The HUD at the top and bottom is its own cells.
- Back-buffer composer with attributes at CB00; IM 2, ISR at 8181 latches keys. One LD A,R (8FA8).
- A level editor on the menu (5). Codes are three characters at 639C.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and do not claim a clash fix. No hook, no site; only the ROM.

## Known issues
- Pace: see the review run's NOTES.md. No hook runs and the clock never moves.

## Evidence (review run runs/jillys_farm/release-20261108, JNext 1.1.104; emulator and simulator only)
rom_paths over 26.11's ROM3 on the recordings, boot exact with and without NEXLOAD, deliberate negatives, soak, flicker, the real loader: in that run's NOTES.md.

## Hardware checklist
Nothing has run on a Next. To check: start-up through the loader, keyboard, the rotational controls, sound, undo and quit, a level code, a level completed, the editor, a 1MB Next (top bank 47).

## Technique use
- patch.whole-altrom-image: used: the build's only change.
- verify.update-locked-pace: used: lockstep with the input applied after the game's read.

## Lessons
- [local: no-hook engine] As Gunrunner: a monochrome game needs no site, and the checks that still mean something are the boot compare with R, rom_paths and the tail.
- [local: level codes] A game's own level codes reach every level by keys alone, with no test poke: the recording stays a clean one.

## Friction
- reuse: [none: nextboot, jnext, soak, flicker and pace were enough]
- retries: [none: first pass]
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: no-hook engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
