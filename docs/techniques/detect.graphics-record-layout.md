# Decode graphics record boundaries and flags

```json
{
  "schema": 3,
  "id": "detect.graphics-record-layout",
  "revision": 1,
  "kind": "detect",
  "title": "Decode graphics record boundaries and flags",
  "question": "How are graphics dimensions, mask flags and record boundaries encoded?",
  "tags": [
    "analysis",
    "graphics",
    "records",
    "mask",
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
    "https://github.com/TheGoodDoktor/SpectrumAnalyserProjects/blob/2aeb826aea3ccb73ad7630288d0351fda4096e84/Livingstone%20I%20Presume/SpriteViewer.lua"
  ]
}
```

## Use / do not use
Establish the layout of graphics records when a known source region cannot yet be decoded reliably.
Start from pointers observed in drawing code or a candidate graphics search match. An image-shaped
byte sequence alone is not evidence of a record boundary. Skip this probe when the original
plotter already supplies a trustworthy image without decoding its storage.

## Recognise
Variable widths or heights, pointer tables, flag bits sharing dimension bytes, paired mask/ink
bytes, mirrored or winding rows. Apparent unused memory may contain unvisited graphics records.
A packed stream or generated image may have no simple fixed record layout.

## Probe and stop
1. Use `scan --range LO-HI --writers` to inspect accesses to the candidate source region; follow
   readers into the plotter. Spectrum Analyser's graphics search/viewer is optional for locating
   candidates, not proof that a match is the source.
2. Infer header fields, byte order, stride, mask storage and next-record calculation from the
   consuming instructions. Decode several records of different sizes and compare with live draws.
3. Check animation/effects for changes to headers or pixels. Record bank and loader phase;
   validate pointer-table targets beyond the recording before calling a region unused.
Stop at a layout that explains the sampled records and live draws, or retain competing layouts
and name a discriminating probe. Export a short field map and exceptions, not a full asset dump.

## Contract
Output: source range, record/header formula, units, storage order, flag interpretation and scoped
uncertainties. Mask presence does not establish mask polarity or AND/OR/XOR composition: inspect
the consumer separately. Runtime-generated and compressed sources may require another method.
This manual detection card does not certify spare RAM or authorise a patch.

## Resources owned
None. Keep extracted graphics and detailed dumps in the private game reference folder.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Records drift after first image | optional mask or variable dimensions | check successive boundaries | derive consumed length | fixed size from one image |
| Plausible but incorrect sprite | wrong stride or winding | compare live source reads | reproduce consumer traversal | visual resemblance alone |
| Effect decodes as huge image | header modified during execution | detect.drawing-parameters | decode at draw time | static header assumption |

## Verification
Compare decoded rows with bytes the original routine consumes on held-out sizes/flags. Intentionally
wrong stride or mask-presence interpretation must fail a relevant case. No such validation was
performed for this new card; keep it candidate until locally exercised and documented.

## Evidence
- External source (metadata), source-reviewed only: `DrawSpriteToViewByIndex` starts at hard-coded
  0x9AE0, reads width/height and doubles stored width when bit 7 indicates a mask. Its addresses,
  flag meaning and helper dependencies are Livingstone-specific, not Spectrum conventions.
- Local motivation: games/midnight_resistance.md describes zig-zag mask/graphic storage;
  games/atic_atac.md records graphics in spans that a recording never touched.
