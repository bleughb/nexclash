# Colour map for patterns built at run time: per-image override tables applied at the upload

```json
{
  "schema": 4,
  "id": "patch.runtime-colour-map",
  "revision": 1,
  "kind": "patch",
  "title": "Colour map for patterns built at run time: per-image override tables applied at the upload",
  "question": "How does a painted colour sheet reach sprites whose patterns the hooks build from game graphics at each draw?",
  "tags": ["colour", "recolour", "outline", "sprites"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["sprite.patterns_built_at_runtime", "mem.hook_page_slot_free"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry"],
  "order": {
    "entry": {"after": ["patch.xor-overlay-keep-ula"]},
    "exit": {"after": []},
    "cross": ["the outline is computed from the real ink before transparent pixels are taken out",
              "the colour pages are mapped only while the pattern bytes are written"]
  },
  "owns": {"mmu_slots": "param", "next_pages": "param", "memory": "param", "hook_state": ["override flag, stream pointer, stride"]},
  "examples": ["cauldron"],
  "sources": []
}
```

## Use / do not use
Every game is paintable, recolour needs no rebuild (docs/COLOURS.md). When hooks convert graphics
at the draw, the build stores the painting as per-image
OVERRIDE TABLES in Next pages the game never reads, and the upload applies them. Use for run-time
pattern builders (overlay engines, outlines made at the draw). Do not use when patterns are built
at build time: colour them there (Dizzy 1 plane, Midnight Resistance commit pages).

**Assumptions.** The image list is known (whole-recording capture, kept in the profile); graphics
are never written (else a run-time check per entry); an MMU slot is free at the upload.

**Validation gap.** One game (Cauldron): unit cases on every image geometry and the screen edges,
a synthetic painting through read-back + recolour + a quick verify; no painting on hardware yet.

## Recognise
- Patterns written from a canvas the hook fills from the graphic at each draw (Cauldron `upload`).
- Outlines or rings beyond the graphic's bytes: those pixels need keys of their own.

## Probe and stop
1. Capture every image the plotter draws over the whole recording (Cauldron `capture`, C simulator, ~70 s for 90K frames): geometry, first frame, inks. Store the list in the profile.
2. Size the worst case (every image painted) against the pages you can give it.
Stop when both are known.

## Contract
- State: game memory untouched; tables only in pages the game never maps (recolour splices only
  them: a repaint cannot change logic). Keys: a canvas pixel inside the graphic's bytes = the
  graphics byte (address; check = its value; shared by every image drawing it); ring pixels =
  per-image keys (graphic:WxR:line,col). Paint: a colour (ink, outline or paper -> opaque) or
  transparent (any pixel).
- Time: one index search per draw (count + 7-byte entries: graphic, width, rows, page, address),
  then, for a painted image only, a mask pass and one AND / OR per pattern byte:
  byte = (default AND KEEP[v]) OR v, KEEP[v] keeps the nibbles v leaves 0. Unpainted images: fast path. hook stack: none beyond the upload's; interrupt headroom: unchanged.
- Display: transparent pixels leave the ink / outline canvases after the outline is computed (the
  outline stays the real ink's); colours replace the default nibble.
- Display: software = return/boundary only; hardware = checklist item "painted colours shown, unpainted unchanged"

## Resources owned
Colour pages + one slot during the upload (Cauldron: pages 28-35 at slot 6, KEEP in page 27).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Stripes of colour in the next line | stream stride shorter than the canvas bytes the patterns read | unit case per image width | stride = 4 x canvas bytes read per line | stride from the image width alone |
| Paint shows on the wrong image | key by graphic address alone | two images sharing bytes | bytes shared, rings per (graphic, width, rows) | - |

## Verification
The verify model applies the map per canvas pixel; unit cases with a synthetic map per image
geometry, shifted and at the screen edges; a wrong check byte must be ignored; negative controls
(map left out of the build, transparent mask ignored, check byte not checked); recolour both ways
equals a full build (selftest guard).

## Evidence
- games/cauldron.md "Colour map" (observed: unit cases, synthetic painting quick run).
- `grep -n 'def colour_tables\|def canvas_keys\|def colour_cases\|def recolour' nexclash/cauldron.py`;
  asm labels `ovfind`, `.bpo`: asm/cauldron_hooks.asm.
