# Road Runner and Wile E. Coyote

## Next session

Stage 1, target decision pending. The named TOSEC snapshot is a playable two-scene demo. The supplied recording finishes the eight-scene game. Selecting the full tape changes the player file specified in the brief. No extra recording is needed to establish this difference.

Branch `add-road-runner`, base `e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea`. Reference inputs are under `road_runner/`. The private run directory is `NextTang-evidence/2026-11-02-nexclash/pilot/runs/road_runner/to-test/`. It contains the input checks, two ending captures, trainer checks and both surveys. Resume by selecting the target by checksum, then read PLAYBOOK stage 1. All visual defaults have already been answered.

## Stage 0. Identify the release

| Player file | MD5 | Observation |
|---|---|---|
| Staged unsuffixed .z80 | `d20bb6338a7d18fef2f557e4176cdd0b` | 32,844 bytes, 48K, PC F064. CCDB compares the next scene with 2. The ending at C76E names the demo. |
| Unsuffixed .tzx | `fb929444dfbf773b6b253102f636f505` | Contains the same demo. Thirteen of 38,824 loaded bytes at 5B00..F2A7 differ from the running demo snapshot. |
| [48-128K].tzx | `06239d172b509dce5c78598a7c63ccd6` | 49,953 bytes. D703 compares the next scene with 8. Loads 45,736 bytes at 4000, then 3,774 bytes for bank 3 on a 128K machine. |
| roadrunner.rzx | `1bf2616b97949464c54be40a989b929c` | Replays 37,413 frames, all eight scenes. The embedded 128K start is staged as `rzx-start-128.z80`, MD5 `bda2300cc779e088be051c2f51f63500`. |
| Same-name .z80 in the owner's 2011 Spectrum collection | `ace3ce66a09afc721cde841ef9debfdf` | 39,836 bytes, 48K, PC 029B in ROM. All 38,824 loaded bytes above the screen match the full tape. The 128K sound bank is absent. This is a separate snapshot candidate. |

The original 128K survey covered 15,001 frames and 5,187 accepted interrupts. Replacing its start with the staged demo left one port reading unused at frame 173. Retiming the recorded keys on the demo initially missed gameplay. Handling the keyboard-release prompt reached 1,312 updates in scene 1 and nine normal life losses. A separate 15,000-frame native run supplied 1,501 frames for the demo survey. It counted 293 accepted interrupts, reached the top plot callers in executed code and passed simulated plain boot. The converter warned that its tail had no proven-safe location.

Holding H, E, L and P at the demo title set the game's own flag at 5B36. From the unmodified demo snapshot, the assisted native run completed three two-scene games in 37,413 frames. Its first ending is visible at frame 9,610 in `demo-ending.png`. The full recording's ending is visible at frame 36,594 in `full-ending.png`. In the full recording the main loop ran in 10,336 frames across scene indices 0 through 7. In the assisted demo it ran in 7,775 frames across indices 0 and 1.

## Packaging

Turning the named .z80 into the supplied plain 128K NEX would replace 27,866 bytes in their three common banks. The 1,413 changed runs need a 34,933-byte site table. The loader limit is 24,576 bytes. This also leaves the 128K music to supply. The demo tape against the 128K start leaves 12,513 residual bytes, above the 8,192-byte tape limit. An undifferentiated patch would carry game content.

The full tape against the 128K start supplied 43,725 bytes in 19 copy runs. Its 112 residual runs carry 1,958 bytes. Reconstructing the table reproduced all eight RAM banks. The extra music block matched all 3,774 bytes in bank 3. Before a full-tape build, audit or eliminate residual game bytes. The loader jumps to F040 after loading. A clean post-load start built from the player's tape is a candidate. No post-load hook or release package has been tested.

Block 5 of both tapes has valid XOR checksum and the same 6,912-byte loading screen. Its first pixel byte is at file offset 347 in the demo and 430 in the full tape. `loading.scr` has MD5 `6550bfb1c1ff3974f350224c04abd375`. A snapshot build needs this staged screen. A full-tape build can read offset 430 for `build_screen`.

## Stage 1. Feasibility

The 128K update calls DF80 to rebuild scenery, dispatches masked figures through E53B, waits at E37B (EI / HALT / DI), then copies the playfield at E3D2. The copy uses SP first for source POPs and then for display PUSHes. In two 22-frame clips starting at frames 1,875 and 7,500, 14 complete updates each wrote 3,584 distinct display bytes. The source predicted 50,176 of 50,176 bytes. Swapping each source pair caused 30,610 mismatches. A separate scene-ending routine writes figures directly to display memory at E1C4 and E1D1. Both sites ran in 124 frames of the original recording. The main blit alone would miss them.

Preserve the original pace, reads, black lines and colours. Convert every moving figure, including effects and pickups. Keep the HUD and scenery on the ULA, start with DivMMC automap off and use 128 sprites. Enhanced colours are deferred. The clean scenery pass is a candidate source for the background. Figure order, opaque paper pixels, overlap, clipping, direct-draw scenes and interrupt slack still need measurement. A shared pixel-ownership renderer has neither been required nor ruled out by these samples. DMA could upload prepared patterns. DDMA cannot do the source's bit-mask composition. Hook costs, fallback and hardware timing are unmeasured.

## Trainer checks

The archive contains three labels and five writes. All five raw addresses belong to the full edition. Their current bytes in archive order are 03, 3D, 3D, C2, C8 in the full start and 40, 73, 2C, 73, ED in the demo. Every relocated demo site below was checked against the original instruction. These are host-side candidates, with zero trainers released.

| Candidate | Full / demo sites (hex) | Result |
|---|---|---|
| Start with 254 lives | D437 / CA0F | Changes initial lives from 3 to 254. A normal death leaves 253. |
| Infinite lives | D746, D78A / CD1E, CD62 | Keep the first OR A. Drop the archive's second NOP. The preceding sound routine leaves Z set, and NOP sends a player with remaining lives to game over on capture. OR A at the second site fixes the flags. |
| Survive empty energy | D737, DEE1 / CD0F, D4B9 | The archive's “Infinite energy” lets energy reach zero, bypasses the death branch and keeps the scene clock running. Retain the effect under an accurate label. |
| Start with full energy | D43C / CA14 | New candidate from the starting-energy instruction and the game's 47-point cap. Starts at 47 instead of 8. Damage still drains the meter. It is absent from the supplied archive. Publication history is unproven. |

All 16 combinations of the four candidates passed from each title with scripted input. The demo ran 4,000 frames per combination and the full edition ran 6,500, for 168,000 simulated frames. The checks covered starting lives and energy, loss of energy, clock movement at zero, and remaining lives. In the full edition the untrained run spent 5,552 frames at zero on the death screen. With survival enabled the clock changed 82 times while energy was zero.

The normal death and capture branches were run from their sound calls with 1, 3 and 254 lives, on both editions. Over 36 branch tests the archive NOP took game over in all six capture cases. OR A preserved lives in all six. The unmodified code took game over only at one life. The scripted input used for combinations reaches the normal death branch. The capture branch check is an isolated execution of game code.

## Verification and hardware

Release verification is pending target selection and a sprite implementation. No release record, engine, profile, verification stamp, OverSpec menu run or owner test copy exists. The ending captures show original game output. Hardware checks for a future build cover cold boot, the patch-time loading screen, colour at scenery boundaries, black lines, effects, capture and restart, the end-scene animation, pace and music against the chosen edition.

## Lessons

- [local: the Road Runner media have two distinct endings] Identical title and loading art occur on both releases. The scene-limit instruction and ending distinguish them.
- [local: the capture branch uses this game's sound flags] Replacing the second decrement with NOP leaves the zero flag from the sound routine live at JR Z.

## Technique use

- detect.buffer-layout-producer: helped distinguish the scenery rebuild, masked actors and final stack copy.
- detect.pacing-structure: helped identify the gameplay HALT separately from the title and three-HALT ending loop.

## Friction

- reuse: [local: two editions expose the same end-of-scene test] The game's own ending settled the identity of each file.
- retries: [local: the demo waits for every key to be released] Replaying only single-row keyboard reads stalled at an input prompt.
- environment: [local: the local collections contain conflicting filenames] Keep the MD5 with the filename.
- hand-rolled: [local: the archive trainer clobbers the capture branch outcome] A small branch check exercises the original sound call before reading the flags.
- scratch: [local: private replay evidence belongs with this run] Keep the input checker, original-game experiments and captures in the private run directory.

## Stage log

- 2026-11-28. Stages 0 and 1, intake and feasibility. Compared two editions, played both endings and exercised original trainer code. About 20 minutes, roughly 90 tool calls, one target decision requested.
