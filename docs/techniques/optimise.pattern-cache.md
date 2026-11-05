# Pattern cache: reuse sprite patterns instead of re-uploading

```json
{
  "schema": 4,
  "id": "optimise.pattern-cache",
  "revision": 2,
  "kind": "optimise",
  "title": "Pattern cache: reuse sprite patterns instead of re-uploading",
  "question": "Do figures show far fewer distinct images than plots, so uploads can be skipped?",
  "tags": ["cache", "patterns", "speed", "sprites", "content-cache", "hook-library"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["sprite.working_set_fits"],
  "rejects": [],
  "conflicts": [],
  "phases": ["commit"],
  "order": {
    "commit": {"before": ["patch.display-atomic-switch"]},
    "cross": ["slots shown in the current frame are never evicted (no tearing between pattern and attribute)",
              "a mutable image's upload invalidates its slot's key"]
  },
  "owns": {"pattern_slots": "param", "memory": "param", "hook_state": ["HLIB_PCACHE"]},
  "examples": ["midnight_resistance", "commando", "target_renegade", "cyclone"],
  "sources": ["pilot runs/atic_atac SPEED.md, work/PERFORMANCE.md (content cache after Rainbow Islands)",
              "asm/lib/hlib_pcache.asm + nexclash/hooklib.py (the shared library)"]
}
```

## Use / do not use
Key pattern slots by image identity and reuse a slot when the same image is shown again, when the
working set fits. Not when graphics change in place without a stable key, or the worst scene's
distinct images exceed the cache. NEW engines: the library's content cache (`hlib_pc_upload`):
- an immutable image's key names its bytes for good (`hooklib.pcache_key(page, row)`, never 0);
- a mutable image (a work buffer the hook rebuilds) has key 0: always uploaded, and the slot's key
  invalidated, so the next immutable image there is uploaded again;
- free, hide and clear keep pattern RAM and the keys; other pattern writers call `hlib_pc_inval` / `_reset`.

**Assumptions.** The game never rewrites the bytes behind an immutable key; keys are per physical slot.

**Validation gap.** The Atic Atac v1.1 candidate in JNext; the library on the simulator only.

## Recognise
- Distinct images far fewer than plots (Commando: ~110 frames in ~4,300 plots).
- Keys identify the image: (page, frame offset, lines) Commando; (source page, row) Atic Atac.
  Masked images (scenery in front) are mutable.

## Probe and stop
1. `cost GAME.z80 --rzx R --at PLOTTER --group IX`: draws per frame and per object.
2. Distinct images per frame in the worst scene; graphics changed in place (values per address)?
Stop when the worst scene's working set is known against the planned size.

## Contract
- State: none.
- Time: hit = 101 T, attributes only; miss = 256 OUTI (4,096 T; `HLIB_PC_OTIR`: 5,371 T, 508 bytes less code).
  Hook stack: 2 bytes; interrupt headroom: as the hook.
- Display: a slot shown this frame is never overwritten; eviction round robin among unshown slots.

## Resources owned
Pattern slots (or a pattern store in Next pages), the cache table (HLIB_PCACHE: 128 bytes, 256-aligned).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Busy scenes slow (Midnight tank) | 16 entries thrash | distinct images there | larger cache | - |
| Bigger cache no help (Cyclone) | images rarely repeat | distinct / renders | faster misses | larger cache |
| Wrong image flashes | evicted a slot still shown | unit: full cache case | never evict shown slots | - |
| Old image after a partial one | key kept on a mutable upload | 'stale pattern!' | key 0 | - |

## Verification
Sprite layer identical with the cache off; unit cases: full cache, eviction, a masked image never
reused. Negative control: the invalidation removed (`hooklib.NEGATIVES`
"missing cache invalidation") must give 'stale pattern!'.

### Measurements
| Game | Workload | Payload | Hits / misses | Worst scene | CPU, core |
|---|---|---|---|---|---|
| Commando | RZX | 4-bit patterns, 32 slots of 4 | 2,764 reused / 4,332 plots | not recorded | 28 MHz hooks |
| Midnight Resistance | 2 RZX | 16 entries | not recorded | tank: 340-410K T (thrash) | 28 MHz hooks |
| Cyclone | RZX + bookmarks | mask cache, 3 entries | 157 distinct in 682 renders | - | 28 MHz hooks |
| Atic Atac v1.1 | walk1, 1,300 frames | 4-bit pairs by page + row | not recorded; draw 2.98M -> 0.25M T | setup 20 ms | JNext 1.1.104 |
When it does not help: Cyclone (images rarely repeat). Setup cost: record it next time.

## Evidence
- games/commando.md, midnight_resistance.md, cyclone.md; LEARNINGS 2.1e.
- asm labels `alloc`, `sigadr`, `sigeq`, `mksig`: asm/midres_hooks.asm; `alloc`, `pat`: asm/commando_hooks.asm;
  `hlib_pc_upload`, `.inv`: asm/lib/hlib_pcache.asm.
