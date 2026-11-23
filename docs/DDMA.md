# Core 3.03.00 zxnDDMA: hook design and candidate review

Source: user-supplied `zxnDDMA_guide.txt` (CC BY-NC-SA, stored separately in
`bleughb/specnext` under `docs/reference/`; SHA-256
`f820ba041be5ed502a99599b293eea0c861e7b02a1aef7c18f092616761be12d`).
The guide describes core 3.03.00 on issue 2, 4 and 5 boards. This page records
engineering facts and independent analysis, not a licence to copy its example code into GPL sources.
The owner reports transfer rates exceeding 8 MB/s on the new code; transfer size, direction,
timing mode, board/core revision and inclusion of setup have not yet been supplied. It is an
observation, not a guaranteed rate or a per-hook cost. Do not substitute it into a benchmark.

## New-game decision (stage 1 and again before delivery)

1. Measure the existing and proposed hook at the actual call frequency, including worst frame,
   game ISR, setup, re-arm, mapping, cache hits/misses, stalls and wait states. Compare at the same
   CPU speed and desired ORIGINAL/TURBO pace, not just peak bytes/s. Consider full-program,
   retained-state rearm, batched rectangle, CPU and existing zxnDMA; retain existing pattern-cache
   hits rather than uploading again. Define the crossover for the actual byte counts and shapes.
2. On core 3.03.00+, evaluate port $6B physical 22-bit memory addressing, 2D row/stride copy,
   transparent-byte skip, constant fill, Layer 2 X/Y and hidden-bank destination. Use only where
   the output semantics match: it transfers bytes; it does not shift individual pixels, perform
   XOR/AND/OR compositing, generate outlines or expand packed ZX bitmaps. A transparent skip keeps
   destination data; restore/clear old pixels first when needed. Slot/palette and priority rules
   still apply. Sprite uploads are memory-to-I/O and may benefit from existing zxnDMA without 2D.
3. Check core capability *before* sending any extended command and its parameters. On old cores
   and port $0B the commands are ignored but parameter bytes can be interpreted as DMA writes.
   The guide's probe requires a reserved scratch physical page and byte; do not run it without
   proving that page is present, unowned and restored. A core-version gate or validated safe probe
   and a tested existing CPU/zxnDMA fallback are required; do not change the baseline minimum core
   silently. Capability is not inferred from board issue alone.
4. DMA is shared single-channel state. Establish ownership and save/restore or exclude all game,
   ISR and sound DMA uses; don't reset or clobber an active transfer. Re-arm only after completion.
   Continuous transfer stalls the CPU; burst mode's CPU availability depends on pacing, and is not
   proof of concurrent transfer. Check pulse interrupt loss, DMA bus hold, beam deadlines and
   music. With hardware IM2 and enabled pending sources, DMA may wait indefinitely under DI;
   preserve the game's interrupt configuration rather than blindly clearing $CC-$CE. Prove any
   bounded critical section and restoration of IFF, speed, MMU and DMA state.
5. Budget effective elapsed time per hook and per game frame, including the above overhead, with
   median, tail and worst values, not only aggregate throughput. Compare original and patched
   gameplay speed and the 50 Hz 20 ms deadline; preserve deliberate pace limiter behavior. Simulator
   T-counts are not a hardware DMA timing or display proof. Record board, core, CPU speed, test,
   bytes/shape, programmed cycles, setup and flags; test busy scenes on actual hardware.
6. A proposed conversion must have a differential model of DMA memory/port effects and retained
   state, negative controls, clipping/zero-size/bank-boundary and fallback tests, original gameplay
   and sprite/layer comparisons, and hardware timing plus interrupt/raster checks. If the simulator
   cannot model DDMA, mark verification incomplete and add a model or independent oracle first;
   do not claim replay proves the new DMA path. The opt-in shared backend and synthetic Rainbow rectangle prototype are described in
   [DDMA_IMPLEMENTATION.md](DDMA_IMPLEMENTATION.md); pinned game builds remain unchanged.

## Addressing and setup traps

- 2D length and row count are actual values, not minus one; zero still transfers one byte.
  Strides are distances between row starts; validate clipping and wrap before programming.
- Physical addresses have 22 effective bits and board-dependent RAM; banks 5/7 screen storage
  is block RAM and cannot be reached through their physical SRAM addresses. In virtual mode,
  ensure all source/destination pages remain mapped for the whole transfer.
- X/Y requires physical mode; destination layout is row-major in 256x192 and column-major in
  320x256 (640 mode X is a byte column). X/Y sets destination stride 256; write the command after
  WR4 address or use WR4 with no destination bytes. `$DF` replaces all mode flags; reset or
  explicitly set flags, strides, lengths and values at ownership boundaries. `$CF` load before
  `$87` enable. Do not use the guide's unsupported `$FB` as a copy operation.
- 3.03.00 guide: reset defaults to 3 cycles per port, fastest 2 per port; a fill skips source
  reads. These are port cycle settings, not a universal bytes/s figure. Timing depends on core,
  clocks, setup, arbitration and the transfer's memory/I/O path.

## Timing evidence and limits

The guide's compare example reports an issue 5, core 3.02.21 (not the 3.03.00 release), CPU 28 MHz: 32 rectangles of
16x16, 320x256 Layer 2. Its stated elapsed times: LDIR 7.2 ms, CPU transparent 15.6 ms,
ordinary DMA per column 8.2 ms, 2D opaque 2.1 ms, 2D transparent 2.1 ms. These are the guide's
measurements of that particular workload, not independent reproduction or 3.03.00 measurements;
opaque and transparent outputs differ. Its example says default three-cycle timing on both DMA
ports and claims two-cycle was about 12% faster for that workload. Existing core 3.02.00 board
measurements and their 3.5 MHz failure remain in TECHNIQUES 1.0/1.0b; do not extrapolate them
to DDMA, and do not infer that 3.03.00 reproduces an earlier core defect.

### NEW in core 3.03.00: zxnDDMA timings (not usable before 3.03.00)

Every figure in this table is for zxnDDMA features (port $6B extended commands). They do not exist
on cores before 3.03.00: never budget a pre-3.03.00 build, or a no-blitter fallback, from them.
Source: the 3.03.00 guide (specnext/docs/reference/zxnDDMA_guide.txt), section or example named.
All are the guide's own figures on an issue 5 at CPU 28 MHz, not reproduced on a nexclash board;
where the guide names the measuring core it is 3.02.21, otherwise it names none. A nexclash
measurement on a released 3.03.00 core is still to do.

| Figure (guide) | Value | Where |
|---|---|---|
| Port cycle length after reset `$C3` | 3 + 3 cycles = 6 a byte | 2.7 |
| Fastest port cycle setting | 2 + 2 cycles = 4 a byte; "about 12% faster" in the examples. KS1 3.03.00 (nxsuite D02): 4 T at 3.5 MHz but 4.96 clocks at 28 MHz; reset timing 6 T / 5.92 | 2.7, 3.4 |
| Fill (`$DF` bit 3, `$F7`) | no read phase: twice as fast as a fixed-source fill | 2.5 mode flags |
| Prescaler | 875 kHz / prescaler bytes a second at every CPU speed. KS1 3.03.00 (nxsuite D04): 32P clocks a byte at 28 MHz (P >= 55 within 0.3 %, P = 12: 390); at 3.5 MHz 4P+3 T plus 2-7 T (P = 12: 58.4 T); burst mode leaves the CPU 99.37 % (D05) | 2.7 |
| 32 x 16x16 rectangles, Layer 2 320x256, 3-cycle | 2D opaque 2.1 ms, 2D transparent 2.1 ms (LDIR 7.2, CPU transparent 15.6, zxnDMA per column 8.2) | 3.4 compare (core 3.02.21) |
| One ball: rub out + draw | about 0.13 ms (2 video lines) | 3.5 sprites |
| One 12x12 lemming | about 1.6 video lines | 3.7 lemmings |
| Two 166 x 118 window copies (39,176 bytes) | 7.0 ms (109 lines); = about 5.6 MB/s by division, set-up included | 3.10 windows |
| Worst frame, about 250 X,Y transfers + background strip | 8.4 ms (FLIP), 10.0 ms (PULSE) | 3.11 scroller |

Classic zxnDMA timings for cores before 3.03.00 are the board measurements in TECHNIQUES 1.0 / 1.0b
(core 3.02.00); those remain the only figures valid for a pre-3.03.00 build.

## Existing conversions: prioritised hypotheses, not proven gains

Review based on STATUS.md and the corresponding games/ notes on main. Assess the exact active
build and profiler before implementing; baseline binaries are unchanged. Legacy zxnDMA may be
sufficient for contiguous sprite uploads; DDMA adds value where 2D, fill, physical or transparent
semantics avoid repeated CPU/setup work. Frozen/deprecated variants are not automatic targets.

| Priority / games | Evidence and candidate | Stop / verify |
|---|---|---|
| Investigate first: Ikari Warriors / Nightshade | Recent docs/REFACTOR.md pilot reports 42% / 26% hook time; these outrank Rainbow by reported total hook cost. Ikari's new instruction profile separates generation, colour lookup, cache and I/O (DDMA_IMPLEMENTATION.md). | Total hook time is not transferable time. Nightshade's current DMA-port counter is not a transfer model. Use the active variant checker and real recordings. |
| Prototype Rainbow Islands Z80N | `games/rainbow_z80n.md` reports slow busy scenes; tcommit copies 20 x 64 bytes (~27K T) per render. Benchmark one strided 2D transfer vs LDIR and existing DMA; profile cache misses. | Prove 2D layout and display timing; handler executes game frame in IM2, so DMA stalls and interrupts can change pace. 69369c89 hardware timing still open. |
| Layer 2 Everyone's a Wally updated | `games/everyones_a_wally_updated.md`: double-buffered Layer 2 commit mean ~0.3 frame, max ~1.3 (simulator T/8). Profile clearing and figure composition for 2D transparent/fill and direct hidden bank. | Transparent skip is not masked compositing; prove draw order, old-pixel clearing, unchanged game reads and atomic bank switch. |
| Cache/miss Midnight Resistance | `games/midnight_resistance.md`: tank commit 340–410K simulated T with 16-entry cache thrash. Measure upload misses and scratch-buffer rectangles. | Increase cache first if it wins; background masks, cell colours, ISR and sound DMA must be preserved. This number is simulator T, not measured DDMA savings. |
| Small-copy Smash TV | `games/smash_tv.md`: ~6% slower simulated play, scratch restore ~5.4K T and per-plot decision ~750 T; check if restore is a byte copy/fill or actual game logic. | DDMA does not accelerate lookup or replace masked plots/XOR; game runs DI, so check hardware-IM2 state and do not change timing semantics. |
| Upload Atic Atac / Match Day | `games/atic_atac.md` reports setup/upload and scans; `games/match_day.md` has a no-sync loop and measured hook overhead. Profile the active reworks and cache misses before memory-to-port DMA. | Existing newer Atic cache can change cost; compare active versions. Small transfers and interrupt beeper timing may outweigh gains. |
| Upload Target Renegade / Cyclone / Commando | Cache misses and pattern uploads are plausible ordinary-DMA candidates; target has ~145K simulated T in 28 MHz hooks, Cyclone cache reuse was limited, Commando reuses patterns. | Measure miss counts, exact lengths and setup; do not overwrite visible slots or assume DDMA fixes cache misses. |
| Profile Cauldron / Dizzy 1 / Fireman (both variants) | XOR shadow/overlay and upload paths merit profiling only if speed is problematic; Cauldron already runs at full speed on the reported board. | Byte copy/transparent is not XOR; no removal of shadow, mask or existing verification. |
| Profile Three Weeks in Paradise / Knight Tyme / Spellbound Magic Knight | Layer 2 or sprite commit paths may have copy/upload work; measure before proposing changes. | Existing notes do not establish a DDMA bottleneck or hardware speedup. |
| Lower evidence: Chuckie Egg; Dizzy V, Dizzy 6, Fantasy World Dizzy, Magicland Dizzy, Treasure Island Dizzy; Jetpac; Lode Runner; Nemesis; Rambo; Renegade 128; Starquake; Lunar Jetman; Robin of the Wood | No documented DDMA-specific bottleneck established in this review. Profile the active engine and recordings first. | Do not alter working conversions on throughput claims alone. |
| No conversion to optimise: Crystal Kingdom Dizzy | Plain-only conversion; include this checklist if sprite work is resumed. | No current sprite hook to benchmark. |
| Frozen/superseded: original Rainbow and original Everyone's a Wally | Consider only if explicitly requested; use their successors for the first experiment. | Keep excluded/frozen builds unchanged. |

Prototype implemented: synthetic differential check of Rainbow’s exact 20 x 64-byte rectangle,
source stride 64 and destination stride 80, using CPU / ordinary DMA / DDMA. No Layer 2 XY.
Next hardware/rework experiment: replay Rainbow's two recordings and instrument tcommit distributions and exact
memory geometry; compare CPU, existing DMA and DDMA on a 3.03.00 board, including setup, frame
stall and overrun. Then re-run differential and negative controls and hardware-play busy scenes;
retain baseline and fallback until all pass. Report measurements and core requirements in the
record and game notes rather than changing generated STATUS rows directly.
