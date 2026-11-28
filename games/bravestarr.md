# BraveStarr (Go!, 1987)

## Next session

Stage 1, feasibility. The recording plays through the ending. The original 128K dump starts inside its unpacker. A release needs a way to install hooks after unpacking without carrying the game's code.
Inputs live in reference-local/bravestarr. Branch add-bravestarr, base e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea. The private pilot run holds the survey and feasibility probes.
Start with the four single-byte tests under Target. Validate a post-unpack installation against the unmodified target, then repeat each trainer with the clash fix both on and off. The owner has already selected the design.

## Target

- The original Go! 128K TOSEC file has MD5 54806bd3eb71452ae2342a5d034ac015. PC is 0x5BAD with bank 0 paged in. The 48K original e71532aeaa70240c72ead895b197960e is already at the title. Its three banks differ from the RZX in 282 bytes.
- SkoolKit 10.1 reached the first title interrupt at 0x8181 from the 128K dump in 150,024 instructions. Only 36 bytes differed across all eight banks. At entry 71, all 131,072 bytes matched the recording except stack bytes 0xBB33 and 0xBB37 through 0xBB39. This identifies the 128K original and accounts for the apparently close 48K match.
- The survey's 0x5B00 tail applies to the RZX start. The packed target executes in that printer buffer. Any packed-start build must establish its own tail location and preserve the unpacker through NEXLOAD.
- Four single-byte trials from the packed original reached the same first interrupt. A marker at 0xF7D8 changed only live 0xF355, inside a player-plot branch operand. Changing the starting gun at packed 0xC9EC also changed live 0xD7FB and 0xE7D5. The two gargoyle markers each changed only their intended byte.
- An ordinary snapshot patch of the plain survey build would carry 21,327 changed bytes from the game's banks in 618 runs. Its 24,419-byte site table fits the loader but includes game code. In the initial images, 3,201 opcode addresses visited during replay in the range 0xC800 through 0xFA64 differ between packed and loaded memory. The toolkit refuses a separate --start on a snapshot target.
- The original TZX has five data blocks. Its reconstruction table found four matching runs totalling 70 bytes. It would carry 41,589 bytes across 359 sites, above the 8,192-byte allowance. The table would take 43,487 bytes against a 24,576-byte limit.
- loading.scr comes from a simulated load of that TZX, before unpacking. All 6,912 bytes match the loading picture in bank 5 of the original 128K dump. MD5 4362c0b070148efa29c4019d4a4a0d78. The raw sequence is absent from the TZX. Use SCR1 and build_screen=nex for a snapshot patch.
- Missing proof: boot the player's packed file, install each change at its live address, and compare all eight banks against the original at the same point. Every difference must be explained by an intended change or identified transient state. Include the loader's fix-off trainer path. This requires game-specific work. No additional recording is needed for the target investigation.

## Feasibility

- The unmodified RZX completed all 37,218 frames in one segment. The supplied survey found 14,993 accepted interrupts in its first 15,001 frames. It attributed 2,492 calls to the main copy in that prefix. Full replay reached the main copy at 0xCA0A 6,459 times, the ending copy at 0xCEFF 64 times and the title/reset copy at 0xC99E once.
- 0xF7D8 transfers 32 bytes from 36-byte source rows, starting at 0xB604, into ULA scanlines 64 through 175. It also copies 14 rows of 32 attributes from 0xC5C0. Each call transfers 3,584 pixel bytes and 448 attributes.
- A writer scan through frame 1,600 identified masked AND/OR draws with saved backgrounds at 0xF357, 0xF426 and 0xDBAD. The XOR projectile at 0xF03F draws eight rows. A separate effect at 0xEEAA toggles two bytes on each of eight rows. Late masked writes also reach the attribute buffer. Following only the large copy loses figure identity. Removing only masked figures leaves the XOR effects.
- The full recording reached 0xF32D 6,524 times, 0xDBAD 3,511 times, 0xF03F 51,156 times, and 0xEEAA 6,459 times, including inactive checks.
- HALT at 0xCA09 precedes the in-play copy. The pacing probe measured 372 intervals through frame 2,100. Median 282,203 T-states per update. The wait before the next interrupt had 128 T minimum and 30,936 T median. One interval spanned a 111-frame transition. A 1 ms addition exceeded the measured slack in 4.03% of intervals. The probe saw sound-port writes at 0x830F and 0xCCEC. No patch timing budget or speedup has been established.
- The shared skip-call probe accepts only a flat 48K state. A bank-aware check is still needed for registers, original RAM, screen reads, sound and interrupt delivery. DMA is a candidate for sprite uploads. DDMA cannot perform the masked and XOR operations by itself. A CPU fallback, core gating and measured whole-hook costs remain open.

## Design

The requested default uses 128 hardware sprites with DivMMC automap off. Convert every moving figure, including plotted effects and pickups. Keep the original colours, black lines, depth, gameplay, screen reads and pace. Add no white outline. Enhanced colours are deferred. Trainers start off. The plain diagnostic rebuilt by the CLI equals the survey NEX with its automap-off start applied. MD5 f28ed7efe28b7087f4d3806c666ee520.

## Cheats

All addresses below are **live bank 0**. Each proposed change was checked against the original instruction. Tests used the unmodified recording's routine-entry states and 128K free play from its title.

| Candidate | Live change | Result |
|---|---|---|
| No gargoyles, archive | 0xD65F and 0xD68A, DD to C9 | Both type 4 and type 5 return before activating the slot. Original play reached them 69 and 113 times. Both types appeared in all four scripted runs with the cheat off and in zero runs with it on. |
| Time, archive | 0xCA5B, 3A 3C to 18 12 | Drop. The jump skips timeout, victory and the restart-key test. At frame 36,162 it skips the recorded victory at 0xCA86 and continues play. |
| Keep nine days, replacement | 0xE7CD, DEC A to OR A (3D to B7) | The hours still roll over. Days 9 and 1 remain 9 and 1, with expiry clear. The original produced 8 and 0 and raised expiry at 0. The normal victory branch survives. |
| Start with full firepower, new candidate | 0xC9EC, 01 to 04 | Four fire presses from empty groups use 4, 8, 12 and 16 projectile slots. The original stays at 4. Later losses and pickups still work. |

Four archive on/off combinations were checked at the normal, expiry and victory branches. All eight combinations of the three retained candidates passed the spawn, day rollover, fire and branch tests. Each combination then ran for 9,000 simulated frames with scripted movement, jumping and firing, 72,000 frames total. All four full-firepower runs reached 16 active projectile slots. These tests apply the bytes after unpacking. Loader installation, fix-off play and hardware remain open.
The archive and the Hackers Anonymous listing do not establish worldwide novelty. The latter lists the same untested time jump. [Hackers Anonymous](https://worldofspectrum.net/hackersanon/ha3/b02.htm)

## Hardware checklist

Once a sprite build exists, check the loading picture at ENTER, post-unpack start, default-off trainers, both fix settings, title restart and victory. Check outlined details in black, bullets and pickups against scrolling buildings, menu overlays, the title music, busy-screen cadence and sprite flicker. OverSpec menu capture and board tests are pending.

## Technique use

- detect.buffer-layout-producer: used: followed the final copy into the masked and XOR writers.
- detect.pacing-structure: used: measured the HALT gap and sound output.
- detect.routine-removal: no help: its shared probe requires flat 48K memory.

## Lessons

- [local: packed source aliases] One packed byte may supply several live instructions. A correct byte at the intended address proves only one of its destinations.
- [local: archive time jump] The winning frame is an effective negative control for an infinite-time trainer. An expiry-only test accepts the broken jump.

## Friction

- reuse: [local: shared tools] The survey, scan, pacing census, tape reconstruction and plain converter provided usable measurements.
- retries: [local: bank-qualified ranges] Split the scan at 0xC000 and name bank 0 above it.
- environment: [local: simulator] The 128K recording needs a bank-aware routine-removal check.
- hand-rolled: [local: packed marker checks] Each packed-address trial ran independently against all eight unpacked banks.
- scratch: [local: private evidence] The pilot run keeps the input comparison, full trace counters, trainer fixtures and scripted-play logs.

## Stage log

- 2026-11-28. Stage 0 intake confirmed, stage 1 feasibility stopped at the packed-target checks. Approximately 12 minutes, 45 tool calls, zero user rounds.
