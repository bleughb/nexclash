# Rainbow Islands sky rework: experimental DMA v0.1

## Next session
Stage: experimental hardware round, following software results in `docs/benchmarks/rainbow_dma_v01.json`.
Source: branch `codex/rainbow-dma-game`; module entry point `python -m nexclash.rainbow_dma`.
Inputs: record `rainbow_z80n`, its sky rework's loading screen and LeeBee cuts in specnext.
Start with the delivered blitter / no-blitter / CPU-only comparison and the hardware checklist below.
Pinned releases remain unchanged. This experiment has no full-game or hardware verification stamp.

## Design and current variant
The base is `rainbow_z80n_sky` v1.0, including the loading screen, sky palette entry 17 rule,
class colours (the thrown rainbow has no outline), pattern cache, tile composer, queued AY,
3-interrupt limiter and overrun recovery. The original sky build rebuilds to MD5
`d7b2345c8f1fd35f592324740ec4daae`. No graphic, colour, plotter or gameplay patch changes.
A startup trampoline follows the fixed-address palette block; setup labels and all 512 palette
upload bytes are checked, including a stale-address negative control.
PR #93 merged at `3efa10f370b21ba7d8cdb6021ac68f32b483b839`; its branch head remains
`449682f2fe987e71e68a254e771efd424681d90d`.

`RainbowDMA` subclasses the sky patch and checks the original bytes before replacing the actual
`tcommit` LDIR row loop with a call into writable page 28. It calls `hlib_dma_rect`: 64 bytes x
20 rows, source stride 64, destination stride 80, offset `(6*40+4)*2 = 488`. DDMA flags = 2:
virtual general 2D memory, never Layer 2 XY. Clip and layer enable follow synchronous completion.
Sprite uploads and cache behaviour are unchanged. Only the real tilemap copy adopts DMA.

## Ownership, memory and interrupts
The NEX boot completes the loader, disables an inherited DMA job and sets NextReg $C0 to 0
(pulse mode). The Spectrum game's IM2 handler at 65171 is software IM2, not Next hardware IM2.
The original game and AY queue do not own DMA. Commit executes under DI at 28 MHz with its own
page-26 stack; it neither enables interrupts nor changes $CC-$CE. Each job rechecks $C0 through
`hlib_dma_init`: unexpected hardware IM2 forces CPU fallback even with pending interrupt masks.
Do not enable DMA by bypassing that gate. There is no asynchronous transfer or ISR/audio DMA user.

During the job slot 0 = page 26, slot 1 = alt ROM, slot 2 = page 28, slot 3 = page 14.
Source $4000-$44FF is ordinary mapped shadow RAM. Destination $61E8 through $6817 is bank-7
virtual memory (physical SRAM addressing cannot reach its block RAM). Both mappings remain until
completion and are restored to 10/11. The backend and mutable packets live at $5000-$52F9
(page 28 offset $1000), beyond shadow rows, LASTT and X8T; page 28 is now initialized in the NEX.
No DMA read uses a CPU-only alt ROM view. Stack tests reserve $00E8-$00FF and keep IFF disabled.

## Pacing and timing
The three-interrupt pacing and existing missed-interrupt credit remain. Stable raster samples
bracket the bounded transfer. The immediate-commit map allowance increases from 20 to 64 lines
(about 4.1 ms at 28 MHz); otherwise commit is deferred to the next interrupt, never beam-waited.
More commits may be deferred, changing display latency by up to one video frame without changing the game-update grid.
This is an experimental budget, not a measured hardware guarantee. The deferred path retains
its top-to-bottom publication and non-play cancellation; it still needs a raster/visual check.

The verifier advances elapsed T by an explicit assumed DMA transfer stall, default 4 MB/s.
It reports complete hook costs, including mapping, setup, cache work and deferred interrupt commits,
plus frame profiles and separate injected stalls. Matched active-boss policy profiles also account for
NextReg $07 speed changes across complete interrupt hooks; raw instruction T is labelled separately. It does not infer transfer time from OTIR cost.
Whole tcommit synthetic CPU costs plus assumed stalls: see the benchmark report. Sensitivity checks
use 8, 4, 1 and 0.5 MB/s; no reported rate is a Next measurement or a speedup claim.

## Build and verify
From nexclash (SkoolKit and Pillow installed):

```
python -m nexclash.rainbow_dma build --snapshot ../specnext/reference/rainbow_islands/rainbow.z80 --out work/rainbow-dma
python -m nexclash.rainbow_dma build --snapshot ../specnext/reference/rainbow_islands/rainbow.z80 --out work/rainbow-dma --no-blitter
python -m nexclash.rainbow_dma build --snapshot ../specnext/reference/rainbow_islands/rainbow.z80 --out work/rainbow-dma --cpu-only
python -m nexclash.rainbow_dma_check
python -m nexclash.rainbow_dma verify --rzx ../specnext/reference/rainbow_islands/rainbownew.rzx --frames 2000 --report work/rainbow-dma/replay.json
```

`build --diagnostic` creates the actual game's border diagnostic. These are real game-build flags,
separate from the synthetic `python -m nexclash.dma` command. `verify --no-blitter`, `--cpu-only`,
`--core 0x32`, `--hardware-im2` and `--dma-mbps 1` select verifier routes and stall assumptions.
Autosave snapshots are stripped as in the sky auto engine; original input identities are recorded.
Omitting `--frames` requests a complete supplied recording. LeeBee cuts start mid-game: replay-only.

## Software evidence
Software results: complete rainbow.rzx, 7,178 observed replay frames, 2,212 commits; rainbownew.rzx sampled at 2,000 requested frames (2,008 observed), 489 commits; no-blitter, CPU-only, old-core and hardware-IM2 routes sampled at 200 requested frames each on an active island-1 boss segment. Twelve LeeBee gameplay cuts sampled (five boss cuts at 200 and seven round-start cuts at 1,200 requested frames), plus a 200-frame ending sample with no commit hook reached. All reported comparisons pass. The full recording still has 60 modeled frames over 20 ms, max 25.666 ms before wait states; recovery comparisons pass. The latter ending sample is not DMA gameplay proof. The legacy game unit suite uses six captured dispatch states from a 1,200-frame capture, plus its object/AY/raster cases and negative controls. Hardware is untested.

The benchmark report records exact recording hashes, requested/observed coverage, commits, DMA
jobs and failures. Functional DMA callbacks access Rainbow's own PMem, including its actual MMU
mapping and overlay; tilemap rows and tile definitions are checked against the existing game model.
Port counts alone never prove a transfer. Data-free tests execute the real assembled tcommit for
24 policy/core/IM2 combinations, preserve untouched gaps and the source, test elapsed stalls and
wrap credit, and detect five controls (stride, missing enable, wrong mapping, old-core gate bypass,
missing post-transfer sample), plus the startup palette-address control. Assembly/profile checks, canary and doccheck are separate gates.
Partial replays do not replace the sky rework's prior proof or certify this new build for a full game.

## Hardware checklist
Copy the separate experimental NEX files to the SD card and launch with NextZXOS .nexload.
Compare the same busy scene using blitter, no-blitter and CPU-only builds. Record board issue,
exact core, CPU speed, file hash and actual selected route; blitter requires core 3.03.00+,
older supported cores fall back to ordinary DMA. Keep pinned builds available for comparison.

- Boot/loading screen, menus, start, death, continue, round/island transitions and ending.
- Sky: islands 1 and 4-7 bright blue paper; islands 2-3 unchanged; thrown rainbows without outlines.
- Figures, objects, colours, depth and scrolling match; no tile corruption, tearing or stale frames.
- Whole-commit worst time remains inside the reserved map budget, including setup and stalls;
  deferred commits finish top rows before the beam. Check diagnostic border and overrun recovery.
- Music tempo and sound remain steady in busy scenes; no hang when a ULA interrupt becomes pending
  during DI; ordinary DMA on old cores and explicit no-blitter on a 3.03+ core both work.
- Compare quiet/busy gameplay pace and worst-frame hitches. Film or capture faults with scene,
  core, build hash and policy. No hardware run has been performed for these builds.

## Lessons
- [tool nexclash/rainbow_dma.py] Legacy randomized object fixtures must reserve the rework's
  shadow-page code region before executing hooks; the loader initializes that allocation.
- [tool nexclash/nextboot.py] Boot simulation must honor the NEX entry bank: a bank-32 loading-screen
  wrapper was otherwise bypassed. Both wrapped and unwrapped game-entry states now compare equal.
- [tool nexclash/rainbow_dma.py] A virtual DMA transfer needs the game's actual mapped-memory callbacks;
  CPU alt-ROM reads are not proof of DMA visibility. Source, full destination and gaps are checked.
- [doc docs/DDMA_IMPLEMENTATION.md §Rainbow game integration] Legacy Spectrum IM2 is compatible with
  the backend when $C0=0; unexpected Next hardware IM2 still falls back without changing masks.

## Friction
- reuse: [tool nexclash/rainbow_dma_check.py] real tcommit mapped-memory policy and stall checks run in CI.
- retries: [tool nexclash/rainbow_dma.py] baseline MD5 comparison preserves the sky auto engine's default class colours.
- environment: [none: both fetched repositories had clean tracked files; work stayed on a new branch]
- hand-rolled: [local: game-specific PMem and commit oracle] the strict shared DMA model is reused.
- scratch: [none: validation orchestration and temporary raw builds stay outside source control]

## Technique use
- patch.display-atomic-switch: helped: existing commit order retained; no new sprite-buffer design.
- verify.update-locked-pace: helped: scoped simulator timing and hook/frame profiles; hardware pace remains unproved.

## Stage log
- 2026-11-06: experimental v0.1 DMA integration on the sky rework. Whole sky engine read was needed to
  trace memory mappings, commit/deferred paths, AY, pacing and the differential verifier. Knowledge
  refreshed from main ec937e9; no original workspace edits were present. Software scope is in the report.
