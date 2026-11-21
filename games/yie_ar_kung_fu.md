# Yie Ar Kung-Fu (Imagine 1985, 128K edition) - engine `yie` (pilot first cut, not releasable yet)

## Next session
Stage: 2 (build)    Branch: add-yie-ar-kung-fu (local, from sprites-hide-all)
State: engine ported from the pilot run (NextTang-evidence/2026-11-02-nexclash/pilot/runs/yie_ar_kung_fu: snapshot,
  rzx/t1-t3.rzx). Fixed 2026-11-21: mirrored plots' X (aligned +4, unaligned +8), the spark sprite opaque over its
  cell (the game copies it over the whole cell), layer-check exceptions counted (outline on another figure's ink,
  outline where the game masks scenery, figure pixels in a spark's wiped cell). t1 and t2 then fail only on items
  being fixed; t3 DIVERGES at frame 1625.
Blocker: the thrown-star hit test reads the screen. 0xF622-0xF646 sums a cell of the drawing screen (63102) and of
  the clean copy at +0x1300 / +0x9300 (63103); unequal = something drawn there = hit. The sprite build keeps the
  screen clean (figure stores NOPped), so the test never sees a figure: stars never hit (t3, frame 1625).
Next: give the hit test the figures' pixels: a shadow of the drawing screen with the figures' ink/mask, or the cell
  rebuilt in a hook at 0xF622 from the figures' patterns (ink 1, body 0, outline and empty = clean); then unit
  tests, negatives, auto(), record (rename to yie_ar_kung_fu), colour sheets for the Enhanced round.

## Lessons
- [local: a pilot first cut is not proof] Two recordings passed the layer check; the third reached a screen reader
  the design breaks. Search every routine that reads the drawing screen (scan --writers readers) before building.
