# Keep the original pace and fill each update's spare time with in-between views

```json
{
  "schema": 4,
  "id": "patch.inbetween-views",
  "revision": 1,
  "kind": "patch",
  "title": "Keep the original pace and fill each update's spare time with in-between views",
  "question": "When a faster renderer leaves most of an update's time free, can it show smooth intermediate views without changing the game's speed?",
  "tags": ["pace", "interpolation", "tween", "renderer", "clock", "raster", "smooth"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["hook.faster_than_original"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "commit", "isr"],
  "order": {"commit": {"after": ["patch.pace-limiter"]},
            "cross": ["the final view is shown at the original's time; in-between views only before it"]},
  "owns": {"next_pages": "param", "hook_state": ["VP"]},
  "examples": ["castle_master"],
  "sources": ["specnext reference/castle_master/build: cm12_glue.asm, m3_sim.py, timing_map.md"]
}
```

## Use / do not use
Run the game's own block for an update at 28 MHz inside a pace window, compute the time the original
took, draw views between the last camera and the new one while they fit, then show the final view at
the original's time. Use with patch.native-renderer-own-pages when an update takes several frames.
Not for a game that updates every frame.

**Assumptions.** The camera is a few words that interpolate linearly; the original time of a block =
K x its 28 MHz time + the handler's lines (K measured per game: 6.75 in JNext for Castle Master).

**Validation gap.** One game; K measured in JNext, pace on hardware by eye ("about the original").

## Recognise
- detect.pacing-structure: updates of 5-30 frames, event driven, no frame wait.

## Probe and stop
1. Probe the block for time that must stay real: sound, waits on the interrupt handler, a printer under
   DI (patch.timed-side-effect-replay). Castle Master: 14 handler waits = +28 frames until found.
2. Measure K over the recording; gate pace per update (verify.staged-port-gates).

Stop when the median pace error is under one frame and the worst under three.

## Contract
- State: the game's block is untouched; saved inputs give the final view. Clock state lives where the
  CPU never reads (40 bytes of the IM 2 table).
- Time: handler and sound run at 3.5 MHz, their time outside the window. hlib_pace's target is 16-bit
  sixteenths (13 frames): longer windows wait in lines. Two line readings a frame apart differ by 0 or
  311 by jitter: after a reading at an interrupt, under half a frame = one more frame. Tick before a
  long DI span and read again after. Commit main-line readings with interrupts off; read again if
  an interrupt came. Hook stack: the renderer's; interrupt headroom: as the game's.
- Display: three Layer 2 banks (shown, drawn, last final). Only the final view waits for the raster to
  leave the window; in-between views flip from a check inside the next view's work. No in-between
  view over an area change, a large step or turn, or a show path with an effect.
- Display: software = entry-to-exit coverage (no flip while the raster is in the view, never draw into the shown bank, every view drawn is shown); hardware = checklist item "walk and turn: smooth, no tearing, the original's speed"

## Resources owned
Three Layer 2 banks, the clock state: values in the record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| +N frames an update | the game waits on its handler inside the window | block probe | count those waits as real time | a smaller K |
| -6 frames, rarely | an interrupt during a main-line clock reading | pace per update | commit under DI, read again | - |
| pace gate fails on a right build | the game read real time: another path | instruction counts | gate same-path updates only | widening the limit |
| tearing | a flip inside the view's lines | flip line check | flip outside the window's lines | waiting before every flip |

## Verification
All 5,233 updates: final view = the model; pace median +0.7 frame, -0.1 to +2.4.
Negative controls: K changed, a wait not counted, a flip in the view: each must fail.

## Evidence
- games/castle_master.md M3a / M3c (observed: simulator, JNext, hardware by eye).
- `grep -n '^h_show\|^flipchk\|^r_enter' cm12_glue.asm` (specnext).
