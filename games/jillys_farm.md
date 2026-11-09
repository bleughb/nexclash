# Jilly's Farm Volume 1 - SokoBAArn! (Bob's Stuff, 2017, 48K)

## Next session
Stage: 3 done for default and Enhanced; published as .nxc 1.0 (nxc 05d3127, 2026-11-08) and registered on main: `auto`, engines.py, record docs/records/jillys_farm.json. Hardware: untested. Not yet played by the owner.
Inputs: `Jilly's Farm Volume 1 - SokoBAArn! (2017)(Bob's Stuff).tap`, MD5 86a5e1dc43e4cfe45582e91eb7cd1cf3, the published patch's target (TAP1). Start state `jillys_farm.z80` (MD5 34e23d4a): that tape loaded by SkoolKit's tap2sna to the game's USR 33280 (`-s 33280`); derived game data, never in this repo. Review runs: runs/jillys_farm/release-20261108 (default), release-20261108b (Enhanced).
Build: `python nexclash.py auto jillys_farm.z80` writes jillys_farm.nex and, with `jillys_farm_loading.scr` (the tape's screen) beside the start state, jillys_farm_loading.nex = the published default bare build (e50bbd53). With `jillys_farm.256` (the Spec256 set) and `jillys_farm_palette.json` (its 256 colours) beside it, both never in this repo (MD5s in the record), it also writes jillys_farm_enhanced.nex and jillys_farm_enhanced_loading.nex = the published Enhanced bare build (9f9cad7c). Every build boot-checked; with `--rzx a1.rzx --rzx levels.rzx --rzx editor.rzx --rzx editor2.rzx` the Enhanced replay, the ABI cases and 13 broken builds.
Pending: owner's play; hardware checklist below; after it, a mock-up step for the improvement ideas in release-20261108b's NOTES.md.

## Facts
- Authorship: Bob's Stuff, 2017; a homebrew release. Nothing of the authors' is in this repo; the patch carries only what patches normally carry (the loading screen and the start state's bytes not on the tape).
- A later homebrew, shown as V1.01 on its menu. A BASIC loader, a screen and one code block, unprotected.
- An isometric Sokoban: 30 levels, each play window bright white on black (all 14 rows, level 1 to 30 by the game's own codes). The HUD at the top and bottom is its own cells.
- Back-buffer composer with attributes at CB00; IM 2, ISR at 8181 latches keys. One LD A,R (8FA8).
- A level editor on the menu (5). Codes are three characters at 639C.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and do not claim a clash fix. No hook, no site; only the ROM.

Enhanced (`jillys_farm_enh.py`, off by default, a menu option; the default mode's bytes unchanged): the Spec256 set by Ynicky, as it is. The set is V1.00, this release V1.01: every coloured byte of the set matches this release 13 bytes higher, so colours are mapped by graphic; a byte with no match stays in its original colour (27 bytes in AD10-AD57, none of them part of a graphic: the first graphic is AD59).
The game composes in a buffer and copies dirty cells, so Enhanced has both too: a value buffer on Layer 2 pages, each plot repeated on it as the planes would do it (LDD copies, AND mask / OR graphic, CPL mask), then the same cells copied to the Layer 2 on show. The shifted sheep routines hold the shifted graphic in IY, which has no planes, so Spec256 ORs the master's bits there: the painted face shows only in the routine that does not shift. That is reproduced, not corrected, and checked against emuspec256.
The game has no frame wait, so its time is its pace. Two K windows (8692-8374, the draw from A2C3 to A605) run at 28 MHz with Layer 2 work nested out and the sound left at the game's clock between them. Every known sprite is compiled to Z80 code (`compiled()`), with a table walk for any other source.

## Known issues
- Pace: see the review run's NOTES.md. Default: no hook runs and the clock never moves. Enhanced: thirds within about 2%.
- Enhanced: the sheep's painted face shows only in the unshifted routine, as on Spec256. The level editor's blue cursor can't be seen, as on Spec256: it is an attribute change under opaque value 0. A colour on exactly the transparent value moves one blue step.

## Evidence (review run runs/jillys_farm/release-20261108b for Enhanced, release-20261108 for the default, JNext 1.1.104; emulator and simulator only)
rom_paths over 26.11's ROM3 on the recordings, boot exact with and without NEXLOAD, deliberate negatives, soak, flicker, the real loader: in that run's NOTES.md.

## Hardware checklist
Nothing has run on a Next. To check: start-up through the loader, keyboard, the rotational controls, sound, undo and quit, a level code, a level completed, the editor, a 1MB Next (top bank 47), Layer 2 and the K windows' constants (JNext measurements) on a core.

## Technique use
- patch.whole-altrom-image: used: the default's only change.
- patch.pace-limiter: used, Enhanced only: two K windows, hlib_nest round the Layer 2 work, a banked debt.
- patch.preserve-r: used, Enhanced only: R compared at every hook.
- patch.restore-speed: used, Enhanced only: the incoming clock comes back after every hook.
- verify.update-locked-pace: used: lockstep with the input applied after the game's read.

## Lessons
- [local: no-hook engine] As Gunrunner: a monochrome game needs no site, and the checks that still mean something are the boot compare with R, rom_paths and the tail.
- [local: level codes] A game's own level codes reach every level by keys alone, with no test poke: the recording stays a clean one.

- [local: registers without planes] Compare with the set's own emulator, not just your model of it. My plane model and hook agreed perfectly and both were wrong on the sheep: OR IYh has no planes on Spec256. A frame diff against emuspec256 found it in one look.
- [local: hook the routine, not its callers] Eight routines' callers were hooked and the replay passed everywhere, and the menu stayed all ULA: 8BE9 falls into the copy at 8BED, past any CALL. The model only knew what the hooks told it. So the model's copied master plane is now compared with the game's real screen at every copy: nothing reaches the screen without passing a hook. Any overlay model should check itself against the real output, not only the hook's.
- [local: cheaper beats repaid] Tuning how overage was repaid only moved the miss around: +7% slow stretches, -33% bursts. Compiling known sprites to code took the overage away, and the same windows came within a few percent both ways. When a loop's budget is the problem, spend on the loop first.
- [local: flat-out game] A game with no frame wait needs a K window round all it can, or every hook entry at 3.5 MHz is its own cost. Time saved in the game's own logic pays for Layer 2 work, so a window over logic alone is useful.
- [local: debt cap] hlib's debt cap is taken inside a window too: capping it low stops a heavy window's nested work counting at all (a +90% stretch). Trim or bank what is left after the wait instead.
- [local: keys under the frame] When updates are shorter than a frame, keys applied at the frame edge cannot be keyed to updates, so a test fixture plays from inside the game: a small generator in place of the control read gave both arms the same input and lockstep over 3,000 updates.
- [local: set offset by graphic] Set and release can differ by a constant in their graphics while code moves about. Compare the set's master with the release at the candidate offset, byte by byte, and list what doesn't match; two early runs of text-like data matched at false offsets.

## Friction
- reuse: [none: nextboot, jnext, soak, flicker and pace were enough]
- retries: [local: pace tuning] Rounds of K and allowance before the sprites were compiled; two after.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Fixture and package scripts stay in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: no-hook engine, proofs, review build, mock-up for Enhanced; waiting for the owner's play.
- 2026-11-08 Stage 3: Enhanced built on the same review branch, Spec256 colours faithfully, proofs in release-20261108b; waiting for the owner's play.
- 2026-11-09 Upstream: `auto`, engines.py line, record 251 (views rebuilt); main rebuilds the published .nxc 1.0 bare builds, default e50bbd53 and Enhanced 9f9cad7c.
