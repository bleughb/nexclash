# Inferno

## Next session
Stage: 1 (design)    State: proposal and six-level preview ready 2026-11-05; awaiting design answer
Inputs: specnext/reference/inferno/    Branch: codex/inferno
Start with: record the user's answer under Design decision; then stage 2 in a fresh session.
Read: docs/PLAYBOOK.md stage 2, Proposed design below, design/README.md in the reference folder.
Open: explicit effects / body / outline choices; no engine or sprite build before approval.
After approval: "Continue Inferno stage 2 (build). Clone bleughb/nexclash and bleughb/specnext
side by side, checkout codex/inferno in both, and follow nexclash/CLAUDE.md and games/inferno.md."

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
- Proposed sprite release: check intro beeper speed; title/start; all six continuous loads with
  score, equipment and health retained; scrolling/depth, bullets, explosions, pickups, death;
  shop/pause/messages with no stale layers; ending scroll/text/medals; no slowdown or tearing.

## Stage-1 findings (2026-11-05)
- Knowledge refresh: both clean branches fetched main and merged (already up to date).
  Knowledge is nexclash main 9484427, branch e95a804; specnext branch fdde27e.
- FULL level-2 census: 51,574 frames, no desync; each of the eight prescribed main-loop sites
  executes 11,921 times (first frame 439, except copier entry 440). These are game ticks, not figures.
- Observed, runtime code and 25 complete captured ticks around frames 10,000-10,020 across
  levels 1-6: 0x9385, 0x938E, 0x93BF compose five-byte scenery lists using C000 pointer table;
  0x9535 player (IX=AC44), 0x9766 projectiles (AC5C), 0x973D second projectile/effect list
  (ACC4), 0x953B actors (D449) use C100. The shared actor loop patches its stride: 15 / 10 bytes.
  Five-byte lists include the decorative planets/clouds/terrain; shop icons are a ULA screen.
  Semantic labels beyond player/projectile bases are inferred; no per-weapon ID catalogue yet.
- Observed: actor graphic = little-endian pointer at C100 + unsigned (IX+4), with low-byte
  wrap on the pointer's second byte. Header low two bits select tile page. Each following row
  is width, signed dx, signed dy, width tile bytes; width=0 ends the WHOLE image. Width=1 is
  a specialised path, not a partial figure. IX identifies the live record, not a graphic pointer.
  Capture at 9599 / 969F (normal / wrapped horizontal path), after IYl receives base x.
  x=IYl+signed dx+j, y=((IX+2)+dy)&255; clip to x=0..31 and y=0..17.
- Observed: tile address 9B00+64*y+2*x; low byte + 256*(high&3) selects graphics
  DC00+8*tile (eight consecutive pixel rows), attribute FC00+tile; screen y=48+8*y.
  9A80 is a lookup area, not the visible tile-map origin. The startup tail there is transient.
- Observed: actors replace tiles in draw order. Their upper metadata bits identify record
  pointers in 9A00; 9701 uses those pointers and IX/IY+5 to update health during composition.
  9306 also consumes the tracked-record list. The tile map is gameplay state: never redirect
  or suppress these writes. Later actors cover earlier ones; scenery was composed first.
- Demonstrated within the captures: replay every decoded actor's tiles over the pre-actor
  map (8F7C) and compare with pre-copy map (8F92): zero differences in low bytes / high&3.
  Render that map and compare with actual ULA after copier return (8F95): zero differences
  in all 36,864 viewport pixels, on all 25 ticks. HUD is outside this model. Proof is about
  original-image reconstruction, NOT sprite hooks, interrupts, full coverage or hardware.
- Observed: empty/black cells leave old screen bitmap bytes under black attributes. Raw
  bitmap comparisons disagree while rendered colours match. Preserve every original byte.
- Captured ticks contain 2-17 image calls; estimated visible 16x16 chunks peak at 35 (level 4).
  These are samples, not full-game resource maxima; no promise that every later boss fits yet.
- All 326 point captures have IFF=1, IM=2. Gameplay handler 998B pushes AF then EI; its flag
  path at 9994 switches SP and unwinds copy stacks. A hook must not treat a callable EI/RET
  handler as harmless. No permanent RAM-slot mapping is justified; the intro touches all slots.
- Level-4 2,001-frame graphics-region scan: all C000-FFFF touched, 232 writer PCs.
  This includes setup/decompression, stacks and code; there is no proven scratch span there.
  Graphics cache entries require content/lifetime checks, not a pointer-only permanent key.
- Original cost (level-4 first 2,001 frames): player-list entry 9535 x367, median/max 1,732 T;
  this is ONE list, not all sprites. Full-copy sampled costs are in the intake table above.

## Proposed design (unapproved)
- Figures: capture every C100 actor image in original order, including BOTH projectile lists,
  effects and collectables if approved. Track one complete run-list per draw ordinal and IX;
  do not collapse several draws by owner or count 9790 as a figure. Keep C000 scenery intact.
- State: execute original producers, collision logic and ULA copier unchanged. At 8F7C retain
  the clean scenery tile map. Build a Layer 2 view of that scenery over y=48..191, opaque black
  included, and hardware sprites from actor images. Top 48 rows remain transparent so the
  original ULA HUD shows. This is the exception to the usual ULA-only scenery display: original
  scenery bytes remain on the ULA underneath, while the displayed clean copy masks the old figures.
  No virtual screen reader or collision rewrite is needed because original memory stays intact.
- Display: preserve actor draw priority and tile colours; two preview options are coloured ink
  only (see-through), or that ink plus enclosed black interiors (solid silhouette). Neither option
  adds an outline. Deliberate rectangular tile knockouts outside the silhouette disappear.
  Keep shop, menu, pause, message and intro/ending screens entirely original: disable BOTH new
  layers before their first draw; re-enable only on a complete new gameplay image, not at a text
  print return. Exact transition hooks and every alternate entry remain stage-2 proof obligations.
- Patch plan: no catalogue patch card is eligible. scratch-redirect would disturb the collision
  map; XOR cards reject this overwrite tile composer. Use explicit table-based composition with
  original state retained. buffer-layout-producer / tracked-unit / drawing-parameters supplied
  the observed interfaces. No patch card is claimed applied or validated by the preview.
- Time: build inactive Layer 2 / pattern data and commit sprite attributes last, retaining the
  old complete image during construction. Aim <=35,000 equivalent 3.5MHz T per game tick of
  TOTAL added work (including uploads), <=2,000 equivalent T bookkeeping per visible image;
  the latter is a sub-budget, not additional. Measure at 28MHz with memory-read wait costs,
  cache unchanged patterns, and fail the gate on overflow or slowdown. These are targets, not
  measured hook timings. Raster atomicity and per-instruction interrupt safety remain unproved.
- Memory proposal: alt-ROM hooks outside 3D00-3DFF, retaining every original ROM reader;
  page 24 boot source, tape payload pages 32-55, Layer 2 double buffers pages 56-67,
  scratch/state pages 68-71 (all <=95). This allocation is provisional until bootstrap and ISR
  checks pass. Do not map a scratch page across an interrupt until its safety is demonstrated.
- Multiload front end: one original-game launch with original intro/title, levels 1-6 and ending;
  automatic loads, no independently restored level snapshots or new level-select menu.
  TZX has 190,814 bytes of standard header/data blocks (24 packed 8K pages). Retain block
  names, flags, checksums, order and actual transfer lengths; startup must reproduce BASIC setup.
  Original 7131 sequence loads named level Na at 50000 (request capacity 6912), executes it,
  loads Nb at 44000 (capacity 21536), then calls 44000. Actual tape lengths differ from capacities.
  7319 calls ROM 0562 for headers/data; don't assume every call is to 0556. Preserve the original
  loader's return contract and live score/health/equipment. Reapply hooks / clear graphics caches
  only after new code is installed. Independent RZX segments do not prove these transitions:
  stage 2 needs original-tape versus bank-loader continuation tests, success/failure checks and
  state comparisons, plus Next hardware testing in stage 3. No loader has been implemented.

## Design decision
Pending ONE user answer (preview in specnext/reference/inferno/design/design_comparison.png):
1. Default: every figure a sprite; explicitly include bullets, explosions, other effects and pickups?
2. Original scenery/HUD/text appearance; accept clean Layer 2 gameplay scenery with original ULA retained?
3. Original draw depth, including actor order and behind anything the original draws later?
4. Original per-tile colours until painting; choose A see-through or B solid enclosed interiors;
   add outlines or none? Recommended proposal: B, no added outline; effects/pickups included.
5. Original shop/pause/messages/intro/ending with both new layers off; full continuous-game automatic loads?
The comparison contains original, A and B for each level; it is a software design simulation,
not a sprite build. The existing plain Inferno.nex is the hardware baseline, level 1 only.

## Stage-1 results
- Preview MD5 `cf3fda58c14e87d91c55fe2773165d6a`; model_checks.json MD5
  `e2b72180a10af6a7261fab91a131ca69`; full level-2 census MD5
  `46261ceb27a13580bddf0ea50d67ec5b`. Asset sizes/checksums: specnext design/manifest.json.
- `selftest.py --tools` PASS (including point captures and bounded-hit smoke checks);
  `selftest.py --canary` PASS (Chuckie Egg rebuilt unchanged); `tools/doccheck.py` PASS;
  `git diff --check` clean. No engine/runtime/shared render change, full sprite verification,
  evidence stamp, new NEX or hardware result is claimed at this stage.

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
- [card detect.buffer-layout-producer §Probe and stop] Demonstrated: black attributes hide stale
  bitmap bytes in Inferno's copier. The card now asks for visible-colour comparison while retaining
  original State bytes; 25 ticks match across six levels. Migrated the revised candidate to schema 4.
- [tool tools/probes/rzx_census.py] Demonstrated: bounded register/mapped-memory captures before
  selected instructions expose whole-image ownership and run-list parameters without a new tracer.
  Smoke checks cover exact frame/PC/code bytes, per-frame bounds and absent sample frames.
- [local: Inferno collision tile metadata] Observed: 9701 consumes object pointers encoded in the
  tile metadata; retain all original tile and ULA writes and separate the displayed image.
- [local: Inferno transfer capacities] Observed: loader capacities exceed the named TZX block
  lengths. A bank loader must reproduce header lengths and 0562 entry behaviour, not copy capacities.
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
- reuse: [tool tools/probes/rzx_census.py] Extended the existing census with bounded point captures;
  no parallel game tracer. Existing flags/output are preserved when capture is not requested.
- retries: [card detect.buffer-layout-producer §Probe and stop] Raw pixel-byte comparison initially
  counted invisible stale pixels as errors; rendered-colour checks resolve it without changing data.
- environment: [local: this managed executor] The prescribed deliverable directory under /codex
  is not writable and sudo is unavailable. Assets are delivered through the authorised specnext branch.
- hand-rolled: [local: Inferno run-list preview] Disposable offline calculations decoded this game's
  tile records and compared 25 original ticks. Scoped results/captures retained in specnext/design;
  they are not a reusable runtime renderer or a hook verifier.
- scratch: [tool tools/probes/rzx_census.py] Reusable capture support kept in the existing probe;
  game-specific preview scratch script dropped after rendering, derivation recorded above.

## Technique use
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: original tile writes carry collision ownership and must run unchanged.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.
- detect.drawing-parameters: helped: captured IX/IY and live run lists distinguish whole actors from tiles.
- detect.buffer-layout-producer: corrected: visible colour checks distinguish black-masked stale bitmap data.

## Stage log
- 2026-11-05: stage 1 analysis/proposal ready (~18 min, ~80 tool calls, 0 user answer rounds);
  nexclash knowledge main 9484427, specnext main 6bce6aa. Full level-2 census PASS; 25-tick
  six-level original-image model PASS; tools/canary/doccheck PASS. The one design question is
  awaiting an answer; stage 2 remains gated. Revised one detection card and the existing census;
  no engine module read or written. Disposable game preview calculations dropped; captures retained.
- 2026-11-05: stage 0 complete (~40 min, ~120 tool calls, 3 user rounds), knowledge from nexclash
  9484427 / specnext 6bce6aa. Full raw replays and all sampled gates PASS; tools/canary/doccheck PASS.
  No engine module read: flagged game copy/producer instructions and shared diagnostic functions
  inspected to fix their reports and profile the preview. Next stage starts in a fresh session
  at this natural boundary (PLAYBOOK Sessions); no sprite engine or approved design yet.
