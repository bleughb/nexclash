# Probes: kept investigation scripts (docs/LEARNING.md)

A probe is an analysis script a game session wrote and that answered a question another game may
ask again. It is kept here instead of in a scratch folder, with its invocation, limits and a smoke
test, until it is promoted into a shared command (BRIEFING C4) or retired. Game evidence never
depends on a probe (docs/records do not list it): changing one re-verifies nothing.

Rules (learncheck checks all four):
- One file per probe, `tools/probes/<name>.py`, listed in the table below.
- Its docstring has the lines `Invocation:`, `Limits:`, `Origin:` and `Smoke test:`.
- A smoke test on a reference game runs in `python selftest.py --tools` (golden values, like the
  shared commands): a function `smoke_<name>(ez, er, ok)` in selftest.py, registered in its
  `PROBE_SMOKE` dict, which tools_check runs. A probe without one is not kept (learncheck fails a
  probe missing from the registry, a registry entry naming no function, or a tools_check that does
  not run the registry; the docstring's `Smoke test:` line alone is not enough).
- Promotion to a shared command (nexclash.py or `python -m nexclash.<module>`): when a second
  game used it, or it replaces a slower shared path; keep its output lines, add a tools_check.

| Probe | Answers | Smoke test | Origin |
|---|---|---|---|
| rzx_census.py | how often and from which frame a recording reaches given addresses (+ HL buckets); optional first-hit register/memory captures per requested PC/frame; C simulator | Chuckie Egg: ISR 40092 x299 in 300 frames, 43909 x141017 (= `scan --writers`); six captures with exact PC/frame and code bytes | Cauldron 2026-10-27; Inferno captures 2026-11-05 |
| attr_census.py | which attribute sets a screen window shows across a recording (sampled; colour-rule questions at design) | Chuckie Egg: 3000 frames every 50 -> 60 samples, 35 sets | Nemesis the Warlock 2026-11-03 |
