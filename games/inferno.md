# Inferno

## Next session
Stage: 1 (design)    State: intake complete 2026-11-05; design not approved
Inputs: specnext/reference/inferno/    Branch: codex/inferno
Start with: refresh from main, then run the census command under Stage-1 entry below.
Read: docs/PLAYBOOK.md stage 1, the survey.md files, docs/techniques/index.json.
Open: classify figure/effect producers, design the multiload front end, then ask the design question.

## Inputs and facts
- Inferno.tzx: supplied tape, MD5 `335eec35a526f2044455cb87e8c77206`.
- Inferno1.rzx: supplied level-1 recording, MD5 `4f19c037b054059f47e3301037a33f37`;
  one snapshot segment, 61,721 frames (20 min 34.4 s at 50 Hz).
- Additional recordings received in this session (one snapshot segment each):

  | Recording | Frames | MD5 |
  |---|---|---|
  | Inferno_intro.rzx | 59560 | b1af564cc64a671699057c767956d136 |
  | Inferno2.rzx | 51574 | 613c8d902dd3630765ba2a6730da7bdc |
  | Inferno3.rzx | 58280 | f977b434bfab4a4315ce8d63c3cc51fd |
  | Inferno4.rzx | 78344 | 3b7d0a3d0e516329870fbc1d2b19aa76 |
  | Inferno5.rzx | 61314 | ab1c293ecb3aa2cc58314675cb76cbff |
  | Inferno6.rzx | 74500 | f5b2b116314f71f740040e01fae1e763 |
  | Inferno_outro.rzx | 4366 | 496f8c896b0ab14ffda452b6cef2a00d |

  Total: 449,659 frames. The repeated TZX attachment is byte-identical.
- Inferno.z80: extracted from the recording's embedded Z80 snapshot with
  `python nexclash.py rzx extract`; MD5 `338a35ccf625f820c0cd6a2a4175aab2`.
- Snapshot: 48K, PC 0x0038, SP 0x86CF, IM 1, interrupts disabled, I=0xFE.
  The stack returns to RAM at 0xECF8; retained BASIC does not prove a running loader.
- No existing Inferno engine, notes, evidence record or private reference folder at intake.
- Game data stays in specnext; no sprite build or visual design has been approved.
- GitHub reports specnext as public. The user explicitly authorised publishing these Inferno
  recordings, snapshots, previews and builds there on 2026-11-05; do not re-ask in this session.

## Status and open items
- Intake complete for the sampled gate. Per-recording 2,000-frame surveys are preliminary
  drawing analyses, not full coverage or sprite verification; full raw replays are separate.
- All eight FULL recordings replay to the end in SkoolKit without desync (449,659 frames);
  results and end snapshots in specnext/reference/inferno/replay_checks.txt.
- Level 1: 2,001 frames analysed, no replay desync, sampled caller gate OK. Its first survey
  predates the diagnostic fixes below (the "unknown" engine advice and loader warning are stale).
- `identify` and the dedicated-engine detectors find no supported engine.
- All eight sampled caller gates PASS (2,001 analysis frames each, 16,008 total); all plain
  survey boot checks PASS. The default-tail builds for levels 1-6 have no proven tail location:
  they are diagnostic only and are not published. Use the corrected flat Inferno.nex below.

  | Level | Sampled frames | 0x9790 calls | Median / max T per copy |
  |---|---|---|---|
  | 1 | 2001 | 308 | 200191 / 264235 |
  | 2 | 2001 | 390 | 211045 / 253282 |
  | 3 | 2001 | 381 | 207683 / 237473 |
  | 4 | 2001 | 367 | 201141 / 268022 |
  | 5 | 2001 | 61 | 212139 / 214693 |
  | 6 | 2001 | 347 | 208663 / 274392 |
- Rendering (observed, level 1 first 1,000 frames): 0x9790 consumes a two-byte tile map at
  0x9A80-0x9F7F, then writes screen pixels with stack copies. The tile consumer uses 10-bit
  indices, graphics based at 0xDC00 and attributes based at 0xFC00. Trace producers next;
  do not treat the whole screen copier as one figure.
- `scan --writers --stop 1000` found 20 instructions writing the tile map. Figure ownership,
  buffer readers, graphics lifetime and redirectability are still unclassified.
- Full level-1 `rzx_census.py`: all ten selected sites (0x8F70/73/76/7C/7F/82/85/92,
  0x93A7 and 0x93C7) reached 13,869 times; no desync. Raw JSON in the reference folder.
  0x933C has callers 0x93A7 and 0x93C7; 0x93BF is called at 0x8F76; 0x9790 at 0x8F92.
- Runtime snapshot at frame 1000 shows a five-byte draw-list loop at 0x93E0. The producer
  reads a graphic-pointer table based at 0xC000 and writes tile IDs plus flags. The operand
  at 0x9419 changes from 0 to 0xFC; avoid treating adjacent code as immutable.
- Level-1 mixed title/game ISR sample: IY+1/+7 read in the ROM handler, alternate registers
  used, stack switches and up to 334 bytes below interrupted SP. Determine safety per hook site;
  the survey's union of title and game behaviour does not prove any one site's conditions.
- Plain `Inferno.nex`: explicit 79-byte tail at 0x9A80-0x9ACE, below 0xC000. All these map
  bytes are written before read in the initial 1,000-frame scan; `nextboot.check` PASS.
  MD5 `0a3bde4734c5b3f15ad0f2a55cc81e19`; replaces the first survey's unproven default-tail build.
- Shared diagnostics: `selftest.py --tools` PASS (including three interrupt/BASIC cases and
  unknown-engine survey regression, C/Python frame-only capture with autosaves and a buffer);
  `selftest.py --canary` PASS (Chuckie Egg rebuilt unchanged).
- Original contact sheets sample the intro, every level and the ending across their full
  recordings. Overview: specnext/reference/inferno/recording_overview.png. These are original
  frames, not a proposed sprite render. Level 4 reaches a full-screen equipment/shop grid.
- TZX: BASIC, main CODE 24200:29499, then pairs named level 0a/0b through 6a/6b (CODE at
  50000 and 44000). A complete release must preserve these transitions and game state;
  independently launching the supplied snapshots does not establish continuous-game behaviour.
- Ending sample: 0xBE69 scrolls the background, 0xBCDF draws text/medal content, and 0xBC64
  clears the display. Preserve this ULA sequence when designing the front end.
- No test cheat or game patch has been applied.

## Hardware checklist
- Plain level-1 Inferno.nex: try CSpect first, then the Next; check title/text to gameplay,
  controls, scrolling, sound, death/restart and the shop. Boot is software-checked only.
- This is a plain conversion, with original colour clash; it does not provide subsequent
  tape loads. No sprite build or all-level hardware test is ready.

## Stage-1 entry
Refresh from main per docs/LEARNING.md before continuing. Then:
```bash
python tools/probes/rzx_census.py ../specnext/reference/inferno/Inferno2.rzx --pc 0x8F70,0x8F73,0x8F76,0x8F7C,0x8F7F,0x8F82,0x8F85,0x8F92 --json
```
Follow each producer through the tile map and graphics tables; classify whole / partial figures,
effects and scenery before picking a patch card. Main-copy counts are not figure counts.
The stage-1 question must cover bullets/explosions/pickups, solid versus see-through bodies,
outlines, original depth/colours, and hiding new layers for the shop and text screens.
Preserve the intro/title beeper ISR; the sampled intro handler touches all MMU slots.

## Lessons
- [tool nexclash.snapinfo] Observed: the level snapshots start at the ROM IM 1 entry with
  a RAM return address and retained BASIC. Report the return; do not assert a running loader.
- [tool nexclash.survey] Observed: identify's literal "unknown" was treated as a known engine;
  the report now directs stage 1. A synthetic detector result checks this in selftest.
- [tool nexclash.simrun] Demonstrated: unhighlighted previews need frame callbacks only;
  opt-in C simulation avoids instruction/memory tracing. The same 300-frame contact sheet
  is byte-identical; profiled time fell from 19.238 s to 0.724 s. Autosave/buffer parity is tested.
- [doc docs/MAINTAIN.md §Commit, PR and the reference files] Observed: specnext is public,
  contrary to the instructions. The user authorised publication; corrected the visibility wording
  in the maintainer guide, CLAUDE.md and the reference index rather than retaining that assumption.
- [local: Inferno startup] Demonstrated for level 1: the tile map is write-first, so a plain
  startup tail can use 0x9A80 without corrupting data the game needs from the snapshot.

## Friction
- reuse: [none: intake uses the existing survey and extraction commands]
- retries: [tool nexclash.survey] Corrected unknown-engine advice and the interrupt-entry loader
  inference before the remaining surveys; shared tools tests and the canary pass.
- environment: [local: this managed executor] The prescribed deliverable directory under /codex
  is not writable and sudo is unavailable. Assets are delivered through the authorised specnext branch.
- hand-rolled: [none: snapshot extraction uses the existing CLI]
- scratch: [tool nexclash.preview] Profiling used transient work files, with timing/image parity
  recorded above; no bespoke analysis scripts were saved. Existing census and preview tools sufficed.

## Technique use
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: eligibility is unknown until figure producers and readers are classified.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.

## Stage log
- 2026-11-05: stage 0 complete (~40 min, ~120 tool calls, 3 user rounds), knowledge from nexclash
  9484427 / specnext 6bce6aa. Full raw replays and all sampled gates PASS; tools/canary/doccheck PASS.
  No engine module read: flagged game copy/producer instructions and shared diagnostic functions
  inspected to fix their reports and profile the preview. Next stage starts in a fresh session
  at this natural boundary (PLAYBOOK Sessions); no sprite engine or approved design yet.
