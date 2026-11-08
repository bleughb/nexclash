# Silkworm (Random Access / Virgin Games, 1989, 128K)

## Next session
Stage: 3 (review build, not yet played by the owner). Hardware: untested. Default only; Enhanced waits on the owner's mock-up.
Inputs: Silkworm (1989)(Virgin Games)(128K).z80, MD5 8fad50cd8c218ade32bf3c2332c8ee03; loading screen from the Mastertronic Plus 128K tape, block 3, MD5 ff8f4e3e, staged by the packager, never in this repo.
Build: `nexclash.silkworm.build(z80, nex)`. Not wired into `auto`, `engines.py` or a record yet: that comes when it goes upstream after the owner has played it.
Checks: review run private. Pending: the owner's play; Enhanced decision; hardware checklist.

## Facts
- A true 128K release: AY music from the ISR, 128K snapshot with paging locked at bank 0, ROM 1. Bank 0 holds game code. The other banks are never paged.
- Back buffer 8002-8DBF, 28 bytes by 110 rows; A25E blits it with POP/LDI to rows y=32..141, column 1 on. Attributes there stay 0x47, white on black. The ground rows 18-19 are drawn elsewhere, in their own wave colour; figures never reach them. So no colour clash, by construction.
- Main loop 9421..9483; the heli's and jeep's inputs read in 97DD and 9A68, so 9442 is the update probe after the reads. Two simultaneous players; one left idle dies off.
- Wave counter 9CC0, 0..10; B71E jumps to the ending at 7C27 after wave 11. RND 9C8F..9C92 is stepped by calls only.
- The game keeps code at 5B00-5BEE (entry at 5B00). NEXLOAD writes that buffer, so it must come back. SP is 0xFFFD, in the top 16K: no automatic tail.

## Decision
The owner's standard: where the play area is monochrome with no clash, keep the original look and claim no clash fix. So no hooks at all.
- Setup in the stub bank copies the snapshot's 5B00-5BFF back after NEXLOAD (the stub's own `keep_printer_buffer` refuses a 128K snapshot).
- Tail at 0x90B0, 79 bytes in zeros the game never touches. 0x9000-0x901F is not free: writes past the back buffer land there in some waves.
- No outlines: figures on black. Pace: nothing runs that the original does not.

## Known issues
- The original's own low update rate (about 12 a second) and long interrupt gaps (up to about 320 ms, so the music stops for moments) remain, as in the original.
- Three of nine pace runs stop being in lockstep at updates 548 to 643. Measured up to there the penalty is +0.00%. No code differs, so that is input timing between the two runs, not found further.

## Evidence (review run runs/silkworm/release-20261108, JNext 1.1.104; emulator and simulator only)
Pace, `nexclash.pace` against the original on a 128K machine, probe 0x9442: whole run, quiet third, busy third and slowest 20-update stretch +0.00% in all nine runs (wave 1 on the release; waves 6 and 11 on test fixtures), 6,520 updates. Soak, 15 emulated minutes, wave 1 and wave 11 fixture: no freeze, loop or crash; sheet looked at. Flicker: none. Start-up: all registers with R, 48K RAM against the snapshot with and without NEXLOAD's printer buffer, bar the tail; six broken builds caught. Every snapshot bank byte for byte in the .nex. ROM: one byte used in 9,004 frames, the same on NextZXOS 26.11's ROM 3. Tail region untouched over all 11 waves (99,000 frames) and the ending. Real .NEXCLASH loader on private NextZXOS 26.11 card copies: default, each cheat and all: output equal to nxc.py, live POKEs right, reaching play.

## Hardware checklist
Nothing has run on a Next. To check: the code at 5B00 after a real NEXLOAD (first game and restart); AY music; both players' controls; 1MB Next (top bank 10).

## Technique use
- patch.restore-speed: no help: no hooks, the clock is never touched.
- patch.whole-altrom-image: no help: one ROM byte read, equal on NextZXOS 26.11's ROM 3 (`rom_paths`).
- verify.update-locked-pace: used: probe after the input reads; penalty +0.00%.

## Lessons
- [local: no clash by construction] Decoding the blit's row table showed the back buffer ends above the ground rows, which proves there is no clash; attribute counts alone only suggested it.
- [local: tail region] A zero run can still take writes: 0x9000-0x901F looked free in wave 1 and took writes past the back buffer in other waves. Scan every wave before choosing a tail.
- [local: printer buffer on 128K] `keep_printer_buffer` refuses a 128K snapshot, yet this 128K game has code at 5B00; a setup call in the stub bank does the same job. Worth a note in BRIEFING C2 #36 when this goes upstream.

## Friction
- reuse: [none: nexclash.scan, pace, soak, flicker and rom_paths were enough]
- retries: [local: real loader] A relative run path made JNext miss the card copy; byte_exact False showed it at once.
- environment: [local: pilot venv] The venv must be called by its absolute path, or Python warns about sys.prefix.
- hand-rolled: [local: review scripts] Fixtures for each wave, boot negatives and loader runs live in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 0-3: survey, every wave by fixture, plain build with start-up fixes, proofs, mock-up for Enhanced.
