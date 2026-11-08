# Inferno stage log

Newest first; moved from inferno.md to keep it within its size budget.

- 2026-11-08 (claude/inferno-pipeline-dispatch): window exact dispatch; gate PASS; NEX m3d boot PASS.
- 2026-11-08 (claude/inferno-pipeline-driver): 8EF9 live-table driver page 81; PASS in the model.
- 2026-11-08 (claude/inferno-copier-window-m3b/m3c): 8F95 work in cw_wait; unfinished dropped; PASS.
- 2026-11-08 (claude/inferno-m3-hw-bisect): m3 hardware crash = hooks under the stub register
  block; moved, guarded, post-boot hook-byte check; gate PASS; fixed m3 for hardware.
- 2026-11-07 (claude/inferno-copier-window*): m1 pacing/head, m2 OUT replay/pad, m3a timed hooks; PASS.
- 2026-11-07: exact rows profiled (timing FAIL); initialization pause/R; owned store/dispatch PASS.
- 2026-11-05..07 (codex/inferno): loader, capture, textmap, frame/queue, actors, transfers; timing FAIL.
- 2026-11-05: stages 0/1 intake/full raw replays and approved design; six-level model/level-2 census
  and tools/canary/doccheck PASS. Cards/diagnostics revised; evidence in specnext design/.
- 2026-11-09 (claude/inferno-pattern-select): selection and 64-slot store in the window, 8EF9 chunk index; gate 0 failures; 18.5 % dropped, runs to 32. [none: lesson is in games/inferno.md]
- 2026-11-09 (claude/inferno-drop-runs): selection hit path cut; gate 0 failures; 17.3 % dropped, runs to 14, margin 108 T. [none: lesson is in games/inferno.md]
