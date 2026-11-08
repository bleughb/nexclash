# Scooby Doo in the Castle Mystery (Elite, 1986, 48K)

## Next session
Stage: 4 (owner's play, then Enhanced). Hardware: untested. v1.0 review build, not published, not pushed; not wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Inputs: `Scooby Doo in the Castle Mystery (1986)(Elite Systems).z80`, MD5 8a82e06f6829a2a1c30781491cfbc42e. The loading screen is the tape's (`ScoobyDoo2`, first 6912 bytes), staged by the review run, never in this repo.
Build: `scooby_doo.build(z80, nex)`, then the review run's `work/pkg.py`, `.nex` 6c52221e with the screen.
Pending: the owner's verdict on the mock-up; the small clash below.

## Facts
- No 128K release in the archive folder: all are the 48K game. The Spec256 set "Scooby-Doo" is this game, Castle Mystery (same screens, same code in place): Scooby-Doo and Scrappy-Doo (Hi-Tec, 1991) matches 10% of its bytes.
- The snapshot is a loader state: BASIC running, `RANDOMIZE USR 16384`. Pokes into the code at that state hold in play.
- Main loop 6F4D: wait until 5 frames have passed, HALT, copy the back buffer (844B: bitmap 9FCC, attributes AFCC, 18 rows), restore figures (92A7), logic and plots (7320). So the update is locked to 5 frames unless the work overruns.
- Scooby himself is composited during the copy (837E: `AND (IX) / OR (IY)` in columns 14-17); the others are plotted in the buffer with a save-under list at 969B (92xx).
- Level table 6290, 14 bytes a level; attributes 61F4/61F5. Levels 1, 2, 3 in one colour pair for the corridors, with brick strips in another; every fourth level (4, 8) has rooms with red jars and a blue wall.
- The ISR at FDFD plays sound by calling ROM BEEPER (03B6) from the interrupt.
- The game reads R (75B6, 7605, 860D).
- Keys (95F5, table 95E6): X right, Z left, O up, K down, P punch, U pause, Y quit. Menu: ENTER starts, J then K Kempston (or I, C), P practice.

## Decision
The play area is one colour pair, with figures in the cell's ink. A figure over a brick strip, a door pillar or a jar takes that cell's ink and paper. Measured by the figures' boxes (work/overlap.py): 0.35% of figure cells in level 1, 0.13% in level 2, 0.08% in level 3, 3.6% in level 4's rooms. No hook in v1.0: the patch is Sinclair's whole 48K ROM, no game byte changed, and no clash fix is claimed; the menu line reads "Original colours". Removing what is left needs the figures on their own layer, the same route Enhanced needs; the owner decides.
No outline: Scooby and the ghosts carry their own masks; they do get busy against the panelling. An outline would need the same layer.

## Known issues
- The small clash above.
- Runs without the test fixture leave lockstep, because the game reads R; the fixture reads R as a constant in both arms.

## Evidence (review run runs/scooby_doo/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, nexclash.pace with input applied after the game's read (732F), fixture on both arms, 800 updates in lockstep at every update, 3 seeds at each of levels 1, 2, 4: the update is frame-locked, see the review run's NOTES.md. rom_paths over 26.11's ROM3 on two recordings (a clean run, levels 1 to 9 by test pokes): every byte the game runs is as recorded, the tail never read before written. Boot exact with and without NEXLOAD, R included. Broken builds caught: R off by one, clock left at 28 MHz, a game byte changed, Next ROM3 copied as the alt ROM, no alt ROM at all. Soak 15 emulated minutes, flicker, real .NEXCLASH loader on a private NextZXOS 26.11 card copy (default, each cheat, all): the review run's NOTES.md.

## Hardware checklist
Nothing has run on a Next. To check: the BASIC loader and its BEEP, title, keys and Kempston, beeper in play, one death, a level change, each cheat, a 1MB Next (top bank 47).

## Technique use
- patch.whole-altrom-image: used: the build's only change; the BASIC loader's BEEP and PAUSE run on Sinclair's ROM whichever NextZXOS loads it.
- verify.update-locked-pace: used: lockstep runs with the input applied after the game's read.

## Lessons
- [local: nearly monochrome] A game's colour look can read as monochrome and still have a little clash: measure figure cells by attribute before saying so.
- [local: unsafe POKE] An archive POKE of an opcode byte can open a new instruction over the next bytes: 29479 turns CP 1 / JP Z into NOP / LD BC,nn / LD (HL),E. Read it before offering it.
- [local: menu keys] J opens a joystick menu; K there picks Kempston. A J alone leaves the game on keys, and a script that holds Kempston directions then looks like it plays while nothing moves. Check the sheet moves.

## Friction
- reuse: [none: nextboot, jnext, soak, flicker and pace were enough]
- retries: [local: start keys] The first pace run measured nothing: ENTER landed while the joystick menu was closing.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture, cheats and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: no-hook engine, clash measured, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
