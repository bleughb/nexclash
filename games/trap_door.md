# Trap Door (48K, Piranha 1986, Don Priestley)

## Next session
Stage: 1 (design)           State: ANALYSED, SKIPPED - owner decision 2026-11-14 (no colour clash to remove)
Inputs: trapdoor.z80 (md5 2cf01264292aa00d876bf5b03382bcf8) + trapdoor.rzx (189,333 frames), owner's machine only
Branch: none    Commit: none    Checks: survey only    Pending user answers: none
Start with: nothing - reopen only if the owner asks for the cut-out fix below
Open: findings below are from survey counts + disassembly reading, not verified by a probe

## Facts (basis: observed in survey / disassembly unless marked)
- 48K, IM 1, interrupts off through the whole recording (0 accepted): no frame sync, pace = CPU time.
- Rendering model: cell map, rebuilt each update, diffed, changed cells copied (PLAYBOOK 2 list).
  - Two maps 0x63A0 / 0x6B20, 32 x 20 cells x 3 bytes (tile set, tile index, attribute); 0x72EA picks current.
  - Composer 0xE73F: walks an object's cell list, writes cells; a later object replaces the whole cell;
    an object with no paper inherits the cell's colour. Clear: 0xEA44.
  - Refresh 0xE991: compares maps, CALL 0xE9EF per changed cell (attribute, then 8 bytes from the tile
    set table 0x730B; attribute bit 7 = mirrored via table 0x7319).
- Other screen writers: 0xE3C7 (from 0xE376), 0xEB67 text (6 callers), 0xAB95 status bar, 0xF70A attributes.
- Figures move in whole cells: no pixel-level attribute clash. Visible fault: square cut-outs where a
  figure's cell hides the background cell.
- Free memory: 0x5B00-0x5C77, 0x5C79-0x6372 untouched; plain .nex tail at 0x5B00, simulated boot OK.
- Coverage gate: CHECK - CALL 0xE991 at 0xAB28 not reached.
- Survey row 43925 (0xAB95) "called from top, 43925", max 21,457,175 T: main loop mis-attributed.
- Research database entry: docs/kb/games/trap_door.json (routine fingerprints, 6,000-frame survey).

## Decisions
- 2026-11-14 owner: log and skip. No engine, no record, no profile.

## Design sketch (not approved, not built)
Keep the composer; record two layers per cell: ULA shows the cell underneath, Next tilemap (text mode,
1-bit tiles) shows the top object with transparent paper. Risks: text mode has no mirror bit and 512
tiles (run-time tile cache needed); any added time changes game speed (unpaced game).

## Open
- A stage-0 measure of "is there colour clash to remove" (cells given ink by two figures with different
  colours). Reconsider when a second game without pixel-level clash reaches stage 1.

## Lessons
- [tool survey.findings] The survey had the counts for the rendering model, the copier's source buffer and the
  pacing but left them to disassembly reading; its Findings section now states them with their basis.
- [tool nexclash.kb] An analysed-but-skipped game had no home and no way to help the next one: docs/kb
  entries with routine fingerprints, matched by every later survey.
- [doc docs/PLAYBOOK.md §2. Identify the engine] The cell map + diff copier model was missing from the
  rendering-model list.
- [deferred Open: reconsider when a second game without pixel-level clash reaches stage 1] No tool says
  "there is no colour clash to remove"; an attribute-change count cannot tell a cell copier from clash.
- [local: inferred from the author's other games, not checked] Same engine family: Popeye, Flunky,
  Through the Trap Door.

## Friction
- reuse: [tool nexclash.kb] the survey facts are reusable as a docs/kb entry.
- retries: [tool survey.survey] a 64-minute survey of a 63-minute recording; it now warns and reuses a result.
- environment: [tool tools/doccheck.py] an autocrlf checkout on Windows failed 18 size budgets and listed docs twice.
- hand-rolled: [tool survey.findings] the copier's source buffer was found by a second replay (`scan --writers`).
- scratch: [none: no scripts written; the disassembly came from SkoolKit's sna2skool]

## Technique use
- detect.pacing-structure: no help: stage 1 stopped at the design question, before feasibility.

## Stage log
- 2026-11-14, stages 0-1, survey 64 min (63-minute recording), ~25 tool calls, 1 user round. Stopped at the design gate.
