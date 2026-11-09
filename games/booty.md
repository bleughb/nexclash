# Booty (John F. Cain, Firebird, 1984, 48K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 05d3127) at the owner's request, not yet played by him. Default has no hooks; Enhanced is a menu option, off by default.
Inputs: Booty (1984)(Firebird).z80, MD5 0b2cb0c5a033e853d62c3a5e492f8bc0; beside it, all staged by the record, never in this repo: `booty_loading.scr` (the tape's screen, MD5 d09b4390), `booty.256` (the Spec256 set, MD5 62ccf9b7) and `spec256-palette.pal` (Spec256-Games' palette, MD5 b095dc99; licence not established, so read from beside the set like lunar_jetman's, never a profile in this repo).
Build: `nexclash.py auto` writes `NAME.nex` (7a41de52) and, with the screen, `NAME_loading.nex` (6393a6f9); with the set and palette also `NAME_enhanced.nex` (ebc40ec7) and `NAME_enhanced_loading.nex` (8113662c). The two with the screen equal `nxc.py PATCH GAME --bare [--colours Enhanced]` of the published patch byte for byte. A missing input is said and its builds skipped.
Checks: `selftest.py --game booty --verify`: Enhanced replay of the five recordings with R (a1 to 6,000 frames, over to 9,000), ABI cases, 21 broken builds, every build boot-checked; the ROM path check lists the two alt ROM hook sites as known. Pace, soak, flicker and real loader are in Evidence, not in the repo.
Pending: hardware checklist; natural completion.

## Facts
- Every figure and all the scenery are whole 8x8 cells printed with their own attribute (ROM PR-ALL at 0B93, the loops A817 and E6DC), so a cell holds one thing in one attribute: there is no colour clash.
- Figures move in two-pixel steps by rebuilding the frame at A0F4 from its graphic each time (EED7); the buffer's two-pixel shifts are in the set's planes too.
- The ISR (IM 2, FEFE to FE69) plays beeper notes by timed loops in the interrupt, up to two frames long (139,800 T), so interrupts are lost in both the original and the build while one sounds, and the time the game gets between notes turns on a few T of the handler's length.
- The main loop runs free with a delay at E9D9, 2,000 steps of 26 T: no frame lock.
- A "hidden game" (CE41) is in the release, reached only by the archive's POKE at CE3E.

## Decision
- Default: no hook, no game byte changed; Sinclair's ROM as the whole alt ROM. The clash claim is not made.
- Enhanced: Layer 2 over the unchanged ULA. Every print repeats on Layer 2 from a table of the set's pixels kept by the graphic's address (8 bytes for each byte of graphic); the frame buffer is rebuilt in the table. The set's value FF is transparent, so ink, paper and FLASH come from the ULA. A hook's cost goes to the debt (hlib_pace) and E9D9 is shortened by it. A hold is drawn at 28 MHz and then waits at the game's clock, from a fit of the original's time. The ISR has no hook: I points at a vector (3BFF) only inside a hook or a hold's drawing, which runs it at the game's clock.
- The title is its own Layer 2 picture, switched by NR 0x12. The sea's sparkle stays on the ULA with paper blue black, as the set shows.
- Hidden game: no set colours for what it draws by its own routines: Layer 2 goes off.

## Known issues
- Pace in JNext, music off, lockstep: the slowest 20-update stretch in hold 8 reads +2.78% to +3.33% in Enhanced, over the 2% line; the default, which runs no hook, reads +1.95% to +2.35% there. Every whole run and third is within 2%.
- The default reads +0.5% whole-run against the 48K original with no hook: a difference between the two machines.
- A note the ISR plays can land either side of an update boundary, in the original too, so 20-update stretches with the music on read several percent either way.

## Evidence
In the review run, NOTES.md: runs/booty/release-20261108. Emulator and simulator only.

## Hardware checklist
Nothing has run on a Next. To check: pace (K values fitted in JNext); ISR notes while a hook runs; Layer 2 and the transparent index over ULA text; the loader on a 1MB Next.

## Technique use
- patch.pace-limiter: used: debt and the game's own delay (hlib_debt_add, hlib_debt_repay).
- patch.preserve-r: used: R compared at every hook and in the ABI cases, though the game has no LD A,R.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM, hooks at 0B9B and 0E44 in the image (altrom_low).
- verify.update-locked-pace: used: lockstep pace runs with music off in both arms.

## Lessons
- [local: pace noise] A free-running game with notes played in the ISR compares unlike phases of the tune: arms a note apart read +13% in a stretch with no real cost. Music off in both arms, for the table.
- [local: probe twice] JNext fires an execute probe twice when an interrupt lands on it. A probe at a loop head gave one extra update and read as a run shifted by one; the pace script now ignores a second firing within 20,000 T.
- [local: moving graphics] A table by the graphic's address is only right if the bytes never change. The replay's ULA check found the frame buffer in the first 500 frames; the check holds what was printed, not what is at the source now.
- [local: hook reads] Reading the game's own tables must come before mapping slot 5 over them: the first version read a width of 0 from the table.

- [local: ISR near a whole number of frames] A handler a few T short of or past two frames decides whether the game gets a frame between notes. A wrapper of 300 T on every interrupt took a death's room from 36 frames to 94. So no hook on the handler: a second vector, selected by I inside hooks only. Worth a line in patch.isr-deferral's card.
- [local: room time] A room at 28 MHz needs its original time back: a fit over all rooms, then a wait at the game's clock, so the ISR takes its share as it did.

## Friction
- reuse: [none: the shared pace and hook libraries were enough]
- retries: [local: K values] K_CELL, K_COMP fitted over six pace runs.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Upstream: `auto`, registration and record added; the engine bytes are the published ones, MD5s 6393a6f9 (default) and 8113662c (Enhanced). The Spec256 palette moved out of docs/profiles to a private input beside the set.
- 2026-11-08 Published: .nxc 1.0 (nxc 05d3127) at the owner's request, not yet played by him.
- 2026-11-08 Review build: default without a hook, Enhanced from the Spec256 set, proofs in the review run.
