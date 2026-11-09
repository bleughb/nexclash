# The Official Father Christmas Game (Enigma Variations / Alternative, 1989, 48K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 05d3127, wording fix d5cc1df) at the owner's request, not yet played by him. The clash fix is on by default.
Inputs: Official Father Christmas Game, The (1989)(Alternative).z80, MD5 71dd57b2ece2787dfff915bf3ba50d3f, 48K, at the options menu with its tune running. No other private input: the published build has no loading screen.
Build: `nexclash.py auto` writes `NAME_sprites.nex` (227268fe), equal to `nxc.py PATCH GAME --bare` of the published patch byte for byte, and boot-checks it with and without NEXLOAD.
Checks: `selftest.py --game father_christmas --verify`: replay of s1, full1, full2 and deep1 with R, Layer 2 against the model and the ULA bitmap, ABI cases and 10 broken builds on s1's first 2,500 frames. Pace, soak, flicker, beam audit and real loader are in Evidence, not in the repo.
Pending: the owner's play; hardware checklist; whether level 3's bands want anything; Enhanced (mock-up only, figures EASY).

## Facts
- 48K only: the archive has one release, beeper, no AY.
- Level 1 (the house), plotted straight to the ULA: Santa 7EE7 (4 bytes x 40 lines), each of two elves 8FEE (3 x 24), `(screen AND mask) OR data`, restored from buffers each update. An update is locked by EI HALT HALT: 25 a second.
- Figures do not paint attributes; they take the ink of the cells they cross: cyan at the table and stool, yellow on a ladder. Open space is 47, bright white on black.
- The game reads the screen attributes for walls and ladders (8A54, 8EDA...): ULA attributes may not change.
- R: LD A,R at 15 places decides the elves' moves; R also runs in a HALT, so real play is timing-dependent even in the original. Lockstep needs a test fixture.
- Level 2's presents (white on black, one floor) and level 3's sleigh (row bands: cyan, white, cyan, yellow, by design) use other code, not hooked.

## Decision
Owner's standard: the original look with clash removed. Layer 2, as in Game Over: figure ink in the colour it has in the open, bright white, in plot order; opaque paper of an elf punches what it covers (elves in front of Santa, as on the ULA). ULA untouched. Scenery keeps its own colours. No outline: figures stand out.
- Not sprites: Santa is 32 x 40 and his ink must overlap the elves' in order; Layer 2 is straight and each graphic's pixels are a list made once, kept in Next pages (RAM only).
- Santa's and the elves' plots and the restores run at 28 MHz (no port writes in them) and pay for the overlay. The HALTs hold the pace: an update has a frame of slack, more than one frame's work takes three. No pace window.
- Overlay off at a room build (88D4) and a text screen (83A5), so nothing stale shows.

## Known issues
- The flip comes as soon as the update's plots end, which can be inside Santa's or an elf's rows (see NOTES.md for how often): those rows above the beam show the old overlay for that frame over the new bitmap. In open space both are white: visible only at the table, stool and ladder.
- Level 2 and 3 are the original's picture: see Facts.

## Evidence
Upstream (2026-11-09): `selftest.py --game father_christmas --verify --stamp` on main's tree, results in the record's status. See the review run's NOTES.md (runs/official_father_christmas/release-20261108): pace, replay with R, negatives, soak, flicker, loader. JNext 1.1.104 and simulator only; nothing has run on a Next.

## Hardware checklist
Nothing has run on a Next. To check: ladder and table in level 1; beeper tune and effects at their clock; level changes and game over leaving no overlay; the real loader; 1MB Next.

## Technique use
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- verify.update-locked-pace: used: lockstep pace runs on a fixture without R and with infinite time.

## Lessons
- [local: HALT locked] Where an update is held by HALTs, its time matters only at the frame edge: the plots at 28 MHz pay for the overlay and no window is needed; pace stays in lockstep at 25 a second.
- [local: lockstep needs R gone] R runs during a HALT, so LD A,R is timing: a test fixture with those reads made constant keeps state in lockstep.
- [local: probe after read] The pace input has to go in after the game's read (8979, after 7E95), or a key lands an update early on one machine, as in Ikari Warriors.
- [local: upstream naming] The default is a hook build, so auto names it NAME_sprites.nex, which nxcout packages as the default.

## Friction
- reuse: [none: the shared pace and hook libraries, and Flying Shark's list store, were enough]
- retries: [local: name screen] The start needs a wheel of letters; a held key stepped past the end: short presses with a wait.
- environment: [none: the pilot venv was enough; other agents' load only made some runs slower]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-09 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5 227268fe.
- 2026-11-08 Published: .nxc 1.0 (nxc 05d3127, d5cc1df) at the owner's request, not yet played by him.
- 2026-11-08 Stage 3: review build, level 1 figures on Layer 2, proofs; not yet played by the owner.
