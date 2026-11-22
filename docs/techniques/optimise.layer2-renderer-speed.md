# Speed up a Z80N polygon renderer on Layer 2: profile first, then fills, divides, flips

```json
{
  "schema": 4,
  "id": "optimise.layer2-renderer-speed",
  "revision": 1,
  "kind": "optimise",
  "title": "Speed up a Z80N polygon renderer on Layer 2: profile first, then fills, divides, flips",
  "question": "Where does a software polygon renderer's time go on the Next, and which changes (CPU, DMA, blitter) pay?",
  "tags": ["speed", "renderer", "layer2", "push-fill", "divide", "dma", "ddma", "blitter", "flip", "profile"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "commit"],
  "order": {"cross": ["a DMA job never covers the frame interrupt's lines"]},
  "owns": {"speed": "28MHz-inside-hook"},
  "examples": ["castle_master"],
  "sources": ["specnext reference/castle_master/build: timing_map.md (profile, benchmark table), cm12_cmr.asm, m3_prof.py, ddma_probe.py"]
}
```

## Use / do not use
Profile the whole update by routine in the simulator first; there may be no hot spot (largest 13 %). Use after patch.native-renderer-own-pages works on hardware. Do not
start from the blitter: for dithered faces it is not the lever (below).

**Assumptions.** Faces are dithered (two colours in a 4-pixel pattern); rows average about 80 pixels.

**Validation gap.** One game; times from the simulator (T) and CSpect 4.5.9 (blitter); the speed
builds ran on hardware by eye only. JNext 1.3.0 does not emulate the blitter.

## Recognise
- Waits and maths visible in the profile.

## Probe and stop
1. Profile by routine over a sampled run (every 10th update), in-between views on.
2. Change one thing, re-run the sample + the sequence test; all updates before hardware.

Stop when the remaining time is the game's own code, the fill and many small routines.

## Contract
- State: every changed routine stays bit-exact (verify.staged-port-gates: sweeps, a mutant each).
- Time: classic zxnDMA holds the bus, so the CPU cannot see the frame interrupt: copy in chunks (8
  rows) and use LDIR for a chunk that could cover it (line & 255 in 238-255 or 0-3). Gate DMA on
  the core (docs/DDMA.md). Hook stack: SP is inside Layer 2 during a PUSH fill; interrupt headroom:
  only the return address may be written there.
- Display: unchanged per pixel.

### Measurements
Castle Master, 28 MHz, 524 sampled updates of 17.0 frames. Share before: geometry 27 %, the game's
code 18, row set-up 13, PUSH fill 12, face walking 8, waits 7, maths 7, overlays 5, view copy 3.

| Change | Before -> after |
|---|---|
| 32-bit divide: 8 bits a step, divisor negated (ADD gives the carry), zero top bytes skipped | 1,967 -> 970 T a call |
| Row set-up: PUSH run from the row's end whatever its parity | 530 -> 495 T a row |
| View copy (192 x 112) by classic zxnDMA instead of LDIR | 458,000 -> 114,000 T |
| In-between flips no longer wait for the raster (deferred into the next view's object loop) | 21 lines idle a flip -> 0 |
| All four: views per update | 6.67 -> 7.46 (+12 %) |

Fill, 192 x 64 block, microseconds a byte (CSpect): LDIR 0.76; CPU PUSH fill 0.20; blitter constant
fill 0.07-0.11; blitter copy 0.18-0.21; one DMA job a row about 26 us set-up. Does not help: a
constant fill cannot write a dither; a pattern-row copy is no faster than PUSH; a job a row costs as
much as 55-130 pixels of CPU fill. Sideways-shifted turn
views (3.7 ms against 40) are up to 12 pixels wrong at the edges: the user's decision.

## Resources owned
None beyond the renderer's.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| a lost frame after a DMA copy | the job covered the frame interrupt | interrupts per update | chunks + LDIR near the interrupt | one long job |
| pointer / sight the wrong colour for a frame | colour chosen when drawn, not when shown | sequence test | set it at the flip | - |

## Verification
Sample, sequence test, then all updates once. Negative controls: four for the flip, one each for
divide, projection, row fill and the DMA gate.

## Evidence
- games/castle_master.md M3c; timing_map.md sections 1-4 (measured: simulator T; CSpect lines).
- `grep -n '^div32\|^proj1\|^span\|^flipchk' cm12_cmr.asm cm12_glue.asm` (specnext).
