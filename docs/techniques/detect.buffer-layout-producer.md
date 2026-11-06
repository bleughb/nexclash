# Trace a screen copy back to its graphics producer

```json
{
  "schema": 4,
  "id": "detect.buffer-layout-producer",
  "revision": 2,
  "kind": "detect",
  "title": "Trace a screen copy back to its graphics producer",
  "question": "Which buffer and producer create the figure before the final screen copy?",
  "tags": [
    "analysis",
    "back-buffer",
    "tiles",
    "copy",
    "layout"
  ],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": [],
  "sources": [
    "https://github.com/TheGoodDoktor/SpectrumAnalyserProjects/blob/2aeb826aea3ccb73ad7630288d0351fda4096e84/Ranarama/OffscreenBuffers.lua",
    "https://github.com/TheGoodDoktor/SpectrumAnalyserProjects/blob/2aeb826aea3ccb73ad7630288d0351fda4096e84/ChaseHQ/ViewerScript.lua"
  ]
}
```

## Use / do not use
**Assumptions.** Producer and consumer share the observed mapped memory view.

**Validation gap.** No full-recording patch verification; Inferno covers 25 ticks, six levels.

Follow a copier or tile renderer upstream to the figure composer. A decoded buffer remains
a candidate until its relationship to the screen writes is demonstrated.

## Recognise
Large LDI/LDIR or stack copies, dynamic tile definitions, screen writes that mix scenery and
figures, or rows appearing out of order in a linear memory view. Producers and the final copier
may run at different points in a frame or use different memory banks.

## Probe and stop
1. Inspect survey's writers and preview. At the copy, establish actual source addresses, bank,
   destination and traversal; do not infer the source from a final register value alone.
2. Run `scan --range LO-HI --writers` on the source range to find its producers and readers.
   Follow another copy upstream if necessary; separate background, figure and clear writers.
3. Derive a coordinate-to-address mapping from the consumer. Compare corner/interior rows and
   any wrap, scroll or bank transition. Use a small optional Spectrum Analyser buffer viewer if
   visual inspection helps; the external Lua examples are not automatic layout detectors.
4. Observe before/after one producer call and confirm which changes reach the screen, and when.
   For dynamic tiles, follow the tile-map references as well as the pixel storage.
   Compare colours too: stale pixels under black attributes are invisible, but game logic may
   still read them. Retain original memory for the State check.
Stop when the producer-to-buffer-to-screen path is supported within scope, or report the missing
link. Keep a compact mapping, writer list and representative events; store raw captures privately.

## Contract
Output: physical buffer identity, layout mapping, producer/copy entries, update ordering and scope.
Feeds detect.tracked-unit and potentially patch.scratch-redirect. A masked producer that keeps a
save-under (Nemesis the Warlock: AND/OR into the buffer, background bytes to IY) allows an
overlay instead: plotters untouched, the screen rebuilt from the save-unders after the copy, so
all game memory stays comparable (games/nemesis_the_warlock.md "Engine"). Check every producer
call's save pointer: one in ROM is a permanent stamp (scenery). A buffer finding alone does not
establish redirectability, absence of gameplay readers, interrupt safety or Display equivalence.
Manual evaluation; unmatched producers and unreached scenes stay unknown.

## Resources owned
None; a candidate buffer is game data, not scratch space available to a patch.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| All objects attributed to one blit | copier mistaken for producer | scan source writers | follow upstream | hook copier as one figure |
| Scrambled rows | non-linear layout | compare source/destination pairs | derive row mapping | assume Spectrum screen layout |
| Missing aircraft | figures composed into tiles | trace dynamic tile writes | include map references | screen writers alone |

## Verification
Predict destination bytes for sampled source updates and compare with the original copy. A wrong
row mapping must fail on nonuniform rows; include scroll/wrap cases when observed. These are
required checks for future applications, not results of this documentation change.

## Evidence
- External sources (metadata), source-reviewed only: Ranarama and Chase HQ decode known layouts.
- Local: games/nemesis_the_warlock.md (save-under overlay, 2026-11-02).
- Local motivation: games/midnight_resistance.md describes a linear buffer and shared address
  helper; games/cyclone.md documents figures composed into dynamic tiles rather than the screen.
- Inferno stage 1 (2026-11-05): 25 ticks across levels 1-6 reconstruct actor tile writes and
  36,864 viewport pixels with zero mismatches. Black cells retain stale bitmap bytes.
  Design-model check only, not hook verification.
