# Cybernoid - The Fighting Machine v1.1

128K source MD5 `92ad5a23acfe06f0756ae2d503ab31cc`. Main baseline `2bcec3e34de23a7ee533520fa7dc645192432833`.
Default removes clash using the original figure colours; Enhanced is optional and off by default.
Enhanced artist credit: Spec256 team. Approved art banks are byte-identical; no outline or art changes.
Patch by Jon Attree. NexClash by Dean Woodyatt (Bleugh.biz), GPL-3.0-or-later.

## Verification

Three level-start tours plus a separate one-life death, game-over and restart recording. Tours use labelled level-start and immunity/stock fixtures; they are not natural full-game completion. Total: 25,707 frames. 192 small, 648 big, 1,020 tile image/position cases; 48 colours; 960 painter edges; table-full, clear and priority cases. All 17 deliberately broken variants detected.
216 ABI cases cover all four incoming speeds, both IFF states and varied R; 32 IRQ cases cover inside/outside hooks.
Registers including R, working RAM, sprite positions/pixels and restored speed/MMU are checked.
These are sampled interrupt cases, not every possible instruction-boundary race.
6,552 consecutive AY register/value writes identical after a 12-interrupt (168-write) startup phase offset. Native music ticks stay approximately 50 Hz; this is AY-port evidence, not a listening or hardware claim.

| Scene | Default pace delta, three trials | Enhanced pace delta, three trials |
|---|---|---|
| quiet | -0.0001%, +0.0000%, -0.0006% | -0.0001%, +0.0000%, -0.0006% |
| busy | -0.6935%, -0.6873%, -0.6911% | -0.6935%, -0.6873%, -0.6911% |
| sound | +0.1004%, +0.1300%, +0.2043% | +0.1004%, +0.1300%, +0.2043% |

Positive means faster than the original. Counted at the player-update routine with update-keyed inputs;
240 measured updates per trial, matching room/X/Y sequences. Worst absolute delta 0.6935%.
These quiet/busy/sound scenes establish the measured scope, not an exhaustive timing bound for every room.

## Design and boot

X-position and image-cache buckets, resident small patterns, fewer colour writes and retired small drawing/painting work reduce overhead. The limiter debit of 20 sixteenths of a line is empirically calibrated; 16, 24 and 30 failed the 2% target. The tile path needs its own R delta. Startup tail moved from live level data at B000 to write-before-read workspace at 5B00.
The full hidden 128K ROM1 image is supplied, including its lower 8K, instead of inheriting NextZXOS ROM bytes.
The 26.11 compatibility fix is present. Direct and NEXLOAD model entry checks compare R, registers and visible RAM;
5B00..5BFF is excluded only after the ROM-path audit proved write-before-read.
The real dot-loader rebuild is tested on private copies of the Beyond the Ice Palace test card in JNext 1.1.104.
No shared card is written. No physical Next has been tested.

Shared hlib_speed, hlib_r and hlib_pace are used unchanged. hlib_iff is included; drawing hooks never DI,
so they do not need an IFF read/restore sequence. The IRQ wrapper enters with the original interrupt state,
restores the original music clock and accounts for time/R across the ISR. No game sound or delay code is accelerated.

## DMA assessment

CPU/cache path retained. Resident patterns and cache hits avoid transfers; remaining sprite misses are contiguous
memory-to-port uploads, for which ordinary DMA would be the relevant experiment. DDMA 2D/transparent operations
do not implement the XOR/image-generation work. Both sets meet ORIGINAL pace without introducing shared DMA
ownership, core gating or an unproven interrupt stall. No DMA/DDMA performance or hardware compatibility is claimed.
Any future backend needs a measured whole-hook crossover and the present CPU path as fallback.

## Trainers

Archive Infinite Shields is correctly labelled Infinite weapon stock. No Sound address 61683 is inside the 128K decoder: translated to the game’s own sound-off entries 61240/61243/61250, explicitly bank 0. Start-lives parameter is fixed at 99. Immediate Backshot and Lives (alt) are startup-overwritten data; not offered. Infinite Weapons (31799), Immunity (alt), Cyber-maces and the extra Eternal Satellite tweak are not certified here. Keep satellite on death certifies only the death-clear suppression.
All 13 stored trainers have original-versus-patched CPU behaviour tests. The first eight appear
in the ten-line loader menu, followed by Colour clash fix and Enhanced colours. Remaining stored trainers are
host-tool options only. The real loader checks all eight visible patch values in active 128K gameplay.

## Open

128K release with AY sound. Original colours with clash removed by default; approved Enhanced colours optional and off by default. Known issues: Very heavy debris can exceed the available small-figure slots, as in the approved earlier build. The loader displays the first eight trainers; additional verified trainers are host-tool options only. Missing: hardware testing, natural full-game completion, and unsupported archive trainer variants.
Natural completion, exhaustive asynchronous IRQ interleavings and physical hardware timing remain untested.
Generic auto is registered for 128K and its no-recording default rebuild is byte-identical. Detailed verification
uses the external suite; no generic selftest verification stamp is asserted.

## Lessons

- [local: these engines retain the Sinclair 128K sound ROM] Preserve all eight banks and the original ROM1; a 48K conversion is not an AY validation.
- [local: measured hook cost is game-specific] Count player updates and repeat trials. Calibrate total entry/exit and ISR cost, not only the sprite uploader.
- [local: release-header assembly is in the external package script] NEX byte 139 is the entry bank; start delay is byte 133. The actual loader caught a bad hand-built header that a payload-only comparison missed.
- [local: the private 128K recorder uses native fetch counts] At a frame boundary, HALT handling must inspect the last executed instruction, not the next PC. Death/menu loops exposed the difference.
- [local: archive cheats name multiple releases] Match opcodes and test their behaviour; upper-bank POKs need an explicit bank number.

## Technique use

- patch.pace-limiter: used; ORIGINAL target and repeated native player-update measurements.
- patch.preserve-r: used; every drawing hook and original ISR accounting tested.
- patch.iff-safe-read: no help; hooks keep interrupts enabled, so no added DI/read/restore section.
- optimise.pattern-cache: used; preserve cache hits and reduce uploads before considering DMA.

## Friction

- reuse: [local: per-game evidence uses existing libraries] Shared hook primitives and the private-card test method were reused unchanged.
- retries: [local: tests retained the failed runs] Header entry-bank and recorder HALT mistakes were fixed, then replayed; stale false-positive reports remain explicitly superseded.
- environment: [local: writable files stay in this game folder] Isolated HOME/TMPDIR and disposable card copies keep the shared card untouched.
- hand-rolled: [local: the 128K paths need per-engine evidence] Game-specific ABI, ROM-path and trainer checks supplement the shared tools.
- scratch: [local: work scripts are part of this release evidence] Keep the work directory for reproducibility; do not merge local paths or game payloads into the toolkit.

## Stage log

2026-11-06: release upgrade on pinned main; unchanged approved artwork, full ROM, shared clock/R/pace,
128K cheats and external proof suite. Only these engines and their local evidence were changed.

## Next session

Claude: use the top-level HANDOFF-CLAUDE.md and release-20261106 artifacts. Preserve credits, the approved art
and default options. Review/package; hardware review remains separate. Do not push or write the shared card without authorization.
