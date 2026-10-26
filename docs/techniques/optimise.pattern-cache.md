# Pattern cache: reuse sprite patterns instead of re-uploading

```json
{
  "schema": 3,
  "id": "optimise.pattern-cache",
  "revision": 1,
  "kind": "optimise",
  "title": "Pattern cache: reuse sprite patterns instead of re-uploading",
  "question": "Do figures show far fewer distinct images than plots, so uploads can be skipped?",
  "tags": ["cache", "patterns", "speed", "sprites"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["sprite.working_set_fits"],
  "rejects": [],
  "conflicts": [],
  "phases": ["commit"],
  "order": {
    "commit": {"before": []},
    "cross": ["slots shown in the current frame are never evicted (no tearing between pattern and attribute)"]
  },
  "owns": {"pattern_slots": "param", "memory": "param"},
  "examples": ["midnight_resistance", "commando", "target_renegade", "cyclone"],
  "sources": []
}
```

## Use / do not use
Key pattern slots by image identity and reuse a slot when the same image is shown again, when the
working set fits. Do not use when graphics change in place without a stable key (check bytes per
address first), or when the worst scene's distinct images exceed the cache.

## Recognise
- Distinct images far fewer than plots (Commando: ~110 frames in ~4,300 plots; reused 2,764 of
  4,332 converted plots).
- Keys must identify the image: (graphics page, frame offset, lines) in Commando; graphics, width,
  rows, flags, colour in Midnight Resistance. Masked images (scenery in front) are not reusable.

## Probe and stop
1. `cost GAME.z80 --rzx R --at PLOTTER --group IX`: draws per frame and per object.
2. Distinct images per frame in the worst scene of every recording.
3. Do graphics change in place? (values seen per address at the plot.)
Stop when the worst scene's working set is known against the planned size.

## Contract
- State: none (pattern memory is outside the game).
- Time: hit = attributes only; miss = upload. Hook stack: per engine; interrupt headroom per engine.
- Display: a slot shown this frame is never overwritten; eviction round robin among unshown slots.
- Display: software = return/boundary only; hardware = checklist item "no wrong image for one frame in busy scenes"

## Resources owned
Pattern slots (or a pattern store in Next pages), the cache table.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Busy scenes slow (Midnight Resistance tank) | 16 entries thrash | count distinct images in that scene | larger cache if pages allow | - |
| Bigger cache gives nothing (Cyclone) | images rarely repeat | distinct / renders | keep small, optimise the miss path | larger cache |
| Wrong image flashes | evicted a slot still shown | unit: full cache case | never evict shown slots | - |

## Verification
Sprite layer identical with and without the cache (cache off as a control); unit cases: full cache,
eviction, a masked image never reused.

### Measurements
| Game | Workload | Payload | Hits / misses | Worst scene | CPU, core |
|---|---|---|---|---|---|
| Commando | RZX | 4-bit patterns, 32 slots of 4 | 2,764 reused / 4,332 converted plots | not recorded | hooks at 28 MHz; core not recorded |
| Midnight Resistance | 2 RZX | 16 entries | not recorded | tank: commit 340-410K T (thrash); 15-60K T without vehicles, 76-200K with the jeep | 28 MHz in hooks; core not recorded |
| Cyclone | RZX + bookmarks | mask cache, 3 entries | 157 distinct images in 682 renders | - | 28 MHz in hooks |
When it does not help: Cyclone (images rarely repeat). Midnight Resistance at 32 entries needs
more page room (SIG area). Setup cost not recorded for any; record it next time.

## Evidence
- games/commando.md (pattern slots); games/midnight_resistance.md (cache, Speed); games/cyclone.md
  (mask cache); LEARNINGS 2.1e (pattern RAM as a content cache).
- asm labels `alloc`, `sigadr`, `sigeq`, `mksig`: asm/midres_hooks.asm; `alloc`, `pat`:
  asm/commando_hooks.asm.
