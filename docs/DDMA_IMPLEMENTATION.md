# Shared DMA backend and first blitter prototype

Status: opt-in library for new engines / versioned reworks, software checks only. Existing pinned
conversions and profiles are unchanged. This incorporates the guidance from PR #92. Protocol
reference and licence boundary: [DDMA.md](DDMA.md). No guide example code was copied.

## Policy: blitter by default, with a no-blitter option

`asm/lib/hlib_dma.asm` is included by the shared pattern cache. Set the policy before first use:

| Selection | Assembly build option | Runtime `hlib_dma_policy` | Behaviour |
|---|---|---:|---|
| Default | none | 2 | Prefer DDMA for rectangles when supported; ordinary DMA for sprite uploads |
| No blitter | `DEFINE HLIB_NO_BLITTER` | 1 | Ordinary DMA or CPU; never send extended commands |
| CPU only | `DEFINE HLIB_CPU_ONLY` | 0 | CPU copies and sprite output only |

The build options cap capability even if runtime policy is raised. Runtime policy can be lowered
without reinitializing. These are options for **engines adopting the library**, not switches that
rewrite already-pinned game packages. The data-free command exercises the same compiled policies:

```
python -m nexclash.dma
python -m nexclash.dma --no-blitter
python -m nexclash.dma --cpu-only
```

A new engine's launcher/build options must map its no-blitter choice to this policy and retain it
in the handoff, build metadata and verification recipe. Test all supported routes, including
blitter preference on old hardware. Never infer capability from the preference or board issue.

## Ownership and entry contract

Before `hlib_dma_init`, run at 28 MHz and pass A=1 only after proving exclusive ownership of an
idle DMA channel, stable source/destination mappings, and bounded transfers. A=0 revokes the
capability. Without initialization every transfer uses CPU fallback. AF/BC/DE are clobbered by init.
The initializer reads NR $01; cores below 3.00 or an absent $FF interface fall back to CPU,
3.00–3.02 use ordinary DMA, 3.03+ permit extensions. It deliberately does not infer support from
pre-release 3.02 builds. Hardware IM2 enabled in NR $C0 forces CPU fallback, conservatively
avoiding pending-source DMA holds under DI. It does not modify interrupt masks or IFF.

Reinitialize if interrupt configuration/ownership changes. Calls and mutable command packets
must reside in writable RAM, are non-reentrant, and must not race an ISR/audio DMA user. All
transfer calls run at 28 MHz; do not assume the old-core 3.5 MHz DMA path is safe. Source buffers
must be proven DMA-visible; an alt-ROM CPU mapping is not proof of DMA visibility.

Each job fully programs ordinary port modes, addresses and stop-at-end, resets extension state,
loads, then enables continuous DMA. No asynchronous job is published as complete. The library
owns channel configuration; it does not save another user's running transfer. Sprite upload
preserves DE (cache key); AF/BC/HL are scratch. Cache hits still avoid both programming and upload.
Attribute publication follows completed uploads into the back half; no visible-slot overwrite.

The rectangle entry takes HL=source, DE=destination and clobbers AF/BC/DE/HL. Its fixed geometry
is Rainbow `tcommit`: 64 bytes x 20 rows, strides 64 and 80, destination offset `(6*40+4)*2`.
DDMA uses one virtual-memory 2D job; ordinary DMA uses 20 row jobs; CPU uses the original LDIR
row geometry. This is a synthetic extracted prototype, **not a patched Rainbow release**.

## Functional verification and timing limits

`python -m nexclash.dma_check` assembles the real hooks with the pinned assembler, runs them in
SkoolKit, and compares the complete rectangle destination (including untouched gaps) against a
CPU oracle. It checks all three build policies, unsupported/older cores, revoked ownership and
hardware IM2 fallback; randomized immutable/mutable cache sequences; and atomic frame commits.
Independent functional tests cover transparent skip, fill without reads, zero dimensions (hardware
moves at least one byte), retained rearm, reset, fixed I/O, virtual wrapping and physical bank
crossing / installed RAM limits. Negative controls include wrong stride, missing reset, an old
core receiving an extension, enable without load, and unsupported commands. CI and `--tools` run them.

`nexclash/dma.py` is a strict subset model, not an FPGA emulator. Virtual accesses are callbacks;
a game must supply its own MMU implementation. Physical memory tests use explicit RAM storage.
Layer 2 XY/hidden-bank, burst, arbitrary cycle programming and legacy port $0B are not implemented
in this model. Unsupported commands fail. Do not claim a game using those features is verified.
Existing per-game verifiers do not automatically acquire this model by importing the library.

No real DMA duration is inferred from executed Z80 T-states. An optional stall callback permits
injected elapsed-time tests; the supplied `NextModel` accounts for that time in its raster clock.
Default synthetic reports label CPU instruction cost separately and exclude transfer stalls.
Each real job must fit comfortably below one frame; pace/debt tracking must sample before and
after it, and often enough that no frame wrap is missed. ORIGINAL pacing may turn savings into
extra waiting/headroom. Record worst hook/frame time and interrupt/raster behaviour on hardware.

## Profiling Ikari without changing its output

```
python -m nexclash.hookprofile --ikari --rzx /path/ik_2pw.rzx --frames 1200 --output profile.json
```

Default variant is the active default colour set; `--mode enhanced` selects Enhanced. The command
uses the existing variant-aware picture and register/memory checker, with an optional observer in
the patched instruction loop. It records recording/hash, hook hash, calls, bytes, raw T and
clock-adjusted costs, and per-sync median/mean/max. A synthetic regression compares execution
with and without observation, including registers, memory and pattern output.

Buckets are disjoint instruction-address regions: cache search; pixel generation/upload setup;
colour lookup; appended colour/seam code; other hooks. Pattern `OUT (C),A` instructions are counted
separately from those regions. This measures direct I/O cost, not all the work needed to prepare a
DMA buffer. Calls into helpers outside a region remain in their own region. Timing excludes
contention; a partial recording is not full-game or hardware verification.

## Recorded software results (2026-11-06)

[Ikari profile](benchmarks/ikari_dma_profile.json): active default, `ik_2pw.rzx` first 1,200
recording frames, 221 sync intervals, 901 cache searches, 108 image uploads (97 `uploadn`, 11
`upload`), 55,296 pattern bytes. The variant-aware memory/register/picture checks reported no
failures. This is partial replay evidence, not a new full verification stamp.

| Instruction bucket | Share of profiled hook time (clock-adjusted) |
|---|---:|
| Pixel generation and upload setup | 53.31% |
| Colour lookup | 20.10% |
| Other hooks | 24.60% |
| Cache search | 1.38% |
| Direct pattern port instructions | 0.60% |
| Appended colour/seam code | 0.01% |

For this sample, replacing only the OUT instructions has a very small upper bound on savings,
before DMA setup and the extra stores needed to create a contiguous staging buffer. Prioritize
precomputed/cached final patterns and cheaper colour/pixel preparation; measure their storage and
miss costs before a rework. DMA alone does not remove the dominant work. Nightshade remains a
separate high-total-hook-cost investigation, not a demonstrated DMA win.

## Hardware/rework acceptance

Record board, exact core, CPU speed, policy, actual selected backend, input/hash and busy scene.
Compare CPU, ordinary DMA and blitter with setup, transfer, mapping, cache hit/miss and whole-hook
median/tail/worst timings. Test fallback on a pre-DDMA core and explicit no-blitter on a DDMA core;
check sound, interrupt delivery, raster overruns and original pacing. Only then adopt the prototype
in a versioned game rework with its full replay, negative controls and new output hashes. The
owner's >8 MB/s observation is encouraging but does not establish a particular hook's speedup.

## Rainbow game integration

The versioned experiment in [games/rainbow_dma.md](../games/rainbow_dma.md) integrates the rectangle
backend into the actual sky rework's `tcommit`. `python -m nexclash.rainbow_dma build` provides real
`--no-blitter` and `--cpu-only` game builds; pinned engines remain unchanged. Its mapped-memory
verifier executes DMA effects, adds explicitly assumed elapsed stalls, and checks the existing
pixel/register/memory/AY/commit models. Legacy Spectrum IM2 runs with $C0=0; unexpected hardware
IM2 falls back without changing interrupt masks. Source and mutable packets are ordinary RAM.
Experimental timing and partial/full replay scope are recorded separately; hardware is untested.
