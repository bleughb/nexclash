# That Sinking Feeling (Sunteam, 2017, 48K-128K, Arcade Game Designer)

## Next session
Stage: 3 (review build for the owner). Hardware: untested. Default and Enhanced built; nothing published, engine local.
Inputs: That Sinking Feeling (2017-08-02)(Sunteam)(48K-128K).tap, MD5 5123adf2c0e828a380b9e260942def4a, a tape target (TAP1); the start state from SkoolKit's tap2sna on a 128K machine to USR 25511; the Spec256 set `That Sinking Feeling.256` and backdrops B00-B06 and rules from the "That Sink Filling" folder.
Pending: the owner's play; hardware; a record and `auto` if it goes upstream.

## Facts
- The release exists only on tape. Its 128K path pages the AY tune (DMS player, Klimenko) into bank 4 and plays it from an IM 2 ISR at 6060; on a 48K machine the tune and IM 2 are skipped. So the start state is a 128K load.
- The ISR pages by port 7FFD. On a Next (JNext at least) that resets slot 1 to the ROM, and the ISR calls the ROM's IM 1. A hook in slot 1 with interrupts on is therefore unsafe unless the ISR puts slot 1 back: NR 0x7F holds the page from its entry to its second OUT, and hooks use the game's stack, as the ROM comes back under a stack in slot 1.
- NEXLOAD overwrites the printer buffer and the game reads 5B5C (its 7FFD copy). `keep_printer_buffer` is 48K only, so setup restores it.
- RNG at 82D0: LD A,R and XOR (HL) over bytes of the ROM's first page, which differ between 128K ROM 1 and Sinclair's (004A), so the build's random spawns are not the original's. A fixture makes it constant for lockstep.
- At start the game turns on ULA+ with its own palette (7FBA). The original look here on a Next: purple water, brown walls. Kept.
- Figures: AGD XOR plots at 8C84, two groups a frame, locked to FRAMES (7F5D). 12 figure records, 15 bytes apart from 8F2E; 24 frames, 128 bytes each (4 shifts of 32). 10 objects at D0B1, 38 bytes each, XORed by 87DB. Blocks and characters: 876D, 8 rows, attribute by 8755. Dots: 81B0.

## Decision
- Default: the ULA stays the original's, every byte; figures and objects are hardware sprites over it, in the pale yellow they have in open water under the game's ULA+ palette; plots run at 28 MHz. A figure in a plant no longer turns green. The game keeps its records in y order by swapping them (8B23): the sprites swap with them. AGD's dots (81B0) would stay on the ULA; no recording reached them.
- Enhanced: the set's colours on the same sprites (8-bit patterns); the game's ULA+ stays off (7FC4), as the set is painted for the Spectrum's colours; Layer 2 under them holds the set's backdrop, chosen by the set's own rules on room number 7D1B (sticky), with every block and character drawn from a table of the set's pixels; a dot toggles a pixel on Layer 2. Room drawing runs at 28 MHz, empty blocks skipped.
- The .256 holds only 4 of the source set's 7 backdrops (rules 0C, 10 and 15 show none there); the source's B03-B05 are used, as its CFG says.

## Evidence
In the review run, NOTES.md: runs/that_sinking_feeling/release-20261108. Emulator and simulator only.

## Hardware checklist
Nothing has run on a Next. To check: slot 1 after the ISR's 7FFD (does the core reset it as JNext does; the code is right either way); ULA+ on the real palette; the AY tune from the tape's 128K path; sprites over Layer 2; 1MB Next.

## Technique use
- patch.preserve-r: used: R compared at every hook and in the ABI cases; the game reads R (82D6, 7F72).
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM.
- patch.xor-shadow: no help: a figure's XOR plot needs no shadow when the figure is a sprite.
- verify.update-locked-pace: used: lockstep pace runs on a fixture.

## Lessons
- [local: 7FFD and slot 1] An ISR that writes port 7FFD puts the ROM back in slot 1 (JNext): a hook there and a hook stack there both die. Found by the Enhanced build hanging in the backdrop copy: the replay, which runs no interrupt inside a hook, passed.
- [local: printer buffer] A 128K game that reads BANKM (5B5C) needs the printer buffer back after NEXLOAD, and z80tonex refuses keep_printer_buffer for 128K: setup restores it here.
- [local: ROM calls] This game's ROM calls run the calculator at 2Dxx, where the usual hook area sits: nextboot.rom_paths found it, and the entries moved to the free space at 3880 (rom2 block).
- [local: ROM-read RNG] A random source that reads ROM bytes separates a game on the 128K ROM from the build on Sinclair's: lockstep ended at a spawn although frames were equal. Constant in the fixture.
- [local: backdrop count] The .256's BGX1 holds 4 backdrops and the source 7: read the source's CFG, not the block.

- [local: records move] Keying a sprite to a record's address fails when the game swaps records to sort them: one figure vanished and another doubled for a frame, a few times in 300 frames. The flicker tool found it; the replay's sprite check did not, as it only looked at the record plotted.
- [local: pattern pages] 34 patterns are 8,704 bytes: the upload ran off an 8K page and the last two objects were noise, in both modes. Every test had passed, since the sprite checks compare x, y and pattern number, not the pattern; the side-by-side with the set found it. The upload now has its own check against the art. nextboot.check had in fact listed reads of ROM at 2000 on, in a long message read past: read that list when it is non-empty. What it still reports, alt image 0 differing, is only the register block at 3CE0-3CF4 inside the 2800-3D00 range it compares.
- [local: colours by shift] A set can paint a frame's pre-shifts differently: the jellyfish's tentacles are yellow at even shifts, red at odd. Count colours per shift, not rows that differ.

## Friction
- reuse: [none: Page Pharaoh's engine shape carried over]
- retries: [local: hook site addresses] The AGD build's addresses differ between games: found by the routine's bytes.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Review build: sprites for figures in the default look, Enhanced from the Spec256 set, proofs in the review run.
