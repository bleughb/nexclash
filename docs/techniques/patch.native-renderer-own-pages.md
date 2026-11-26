# Replace a software 3D renderer with a Next-native one in its own pages

```json
{
  "schema": 4,
  "id": "patch.native-renderer-own-pages",
  "revision": 1,
  "kind": "patch",
  "title": "Replace a software 3D renderer with a Next-native one in its own pages",
  "question": "Can a game whose view is drawn by a slow software renderer show that view from a Z80N renderer on Layer 2 while its own code still runs?",
  "tags": ["renderer", "3d", "freescape", "layer2", "pages", "interrupt", "overlay", "colour-switch"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup", "entry", "commit", "isr"],
  "order": {"cross": ["the page variables are written before each NEXTREG that changes a page",
                      "overlay sprites and Layer 2 switch together (patch.display-atomic-switch)"]},
  "owns": {"mmu_slots": "param", "next_pages": "param", "sprite_ids": "param", "pattern_slots": "param",
           "vectors": ["im2"], "speed": "28MHz-inside-hook"},
  "examples": ["castle_master"],
  "sources": ["specnext reference/castle_master/build: cm12_cmr.asm (renderer), cm12_glue.asm (hooks, switch, overlays), m2_build.py, timing_map.md"]
}
```

## Use / do not use
Run the game's own update and redraw unchanged (buffer and ULA stay whole) and draw the same view
again with a Z80N renderer in its own pages, on Layer 2 over the view window. Use when
the view is one window drawn by one routine from a display list, and gameplay reads that routine's
results (detect.routine-removal: keep), so patch.hybrid-display-replacement does not fit. Not
for sprite games, nor when the list cannot be read at fixed PCs.

**Assumptions.** Slots 0-1 are free for code during the redraw (the hooks sit in the alt ROM, the same
bytes at the same addresses in the renderer's page); the game's tables can be copied at start-up.

**Validation gap.** One 48K game (Castle Master); hardware by eye.

## Recognise
- survey: updates take many frames, no frame wait (detect.pacing-structure); one copier writes the view.
- The renderer's inputs are a list at a fixed address. Budget from simulator T x 1 (TECHNIQUES 1.0).

## Probe and stop
1. The copier's own pointer gives the exact view buffer (the survey's range may include variables).
2. Port on the host first, then Z80N, gated per stage (verify.staged-port-gates).
3. An integrated build early (plain hooks) on hardware; then pace (patch.inbetween-views), overlays,
   speed (optimise.layer2-renderer-speed).

Stop when one area plays on hardware at the original's pace.

## Contract
- State: all game RAM and registers but R equal to the original's; the renderer writes only its own
  pages. Start-up state goes in the image (patch.apply), not in setup_call (stub in slots 6-7).
- Time: the switch runs under DI (about 140 T). The IM 2 vector jumps to one address whose code
  differs: alt ROM = JP handler; renderer's page = restore pages, stack and speed, CALL handler. Hook
  stack: the renderer's own; interrupt headroom: a PUSH fill with SP inside Layer 2 leaves only the
  return address writable.
- Display: a Layer 2 byte = 2 x colour code + the original's pixel bit: palettes alone give colour,
  the original look (a build option, a .nxc toggle) or flat faces. What the game draws over the view
  = hardware sprites, opaque where the screen differs from the renderer's output. Non-view screens:
  Layer 2 and sprites off.
- Display: software = entry-to-exit coverage (every redraw per pixel against a model of the original); hardware = checklist item "view, overlays and non-view screens through one full area change"

## Resources owned
Pages, slots 0-1 and Layer 2's, the overlay sprite grid: values in the record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| boots in the simulator, not in JNext | setup_call wrote 0xC000-0xFFFF: the stub's bank | boot check | state in the image | poking the harness |
| RAM corrupt on a rare input | the original overruns a buffer; the copy cannot | force the input | clip, record it as a model option | copying the bug |
| CSpect closes / JNext shows no screen | a NEX header loading screen | - | screen in the image, setup restores the game's | header screen |
| a view stays in the original look | a second show path (dissolve, animation) | unreached CALL sites | draw hidden, repeat the effect on Layer 2 | Layer 2 off |

## Verification
verify.staged-port-gates: per redraw Layer 2 = the model per pixel; without interrupts, game RAM and
registers = the original's. Negative controls: a mutant per hook and per stage.

## Evidence
- games/castle_master.md M1-M3e (observed).
- `grep -n '^r_enter\|^isr_e\|^h_show\|^ov_s' cm12_glue.asm` (specnext).
