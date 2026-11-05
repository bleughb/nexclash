# Inferno

## Next session
Stage: 2 (renderer, continued)    State: capture kernel tested; replacement display NOT built
Inputs: specnext/reference/inferno/    Branch: codex/inferno (both existing checkouts)
Start with: refresh main; read capture results below and specnext build/README.md.
Read: nexclash/inferno.py CapturePatch/run_capture/capture_log/model_verify; asm/inferno_hooks.asm.
Next implementation: content-validated pattern cache and budgeted Layer 2/sprite renderer using
  the retained whole-image run lists. Keep original game memory/ULA writes; complete modal hooks,
  original-BASIC startup installation and all-level continuation before exposing auto detection.
Open: total rendering/upload timing; full resource maxima; painting/recolour/sheets; original
  startup-tail lifetime; Nb initialization/game/ending continuity; full ROM-reader coverage.
Next prompt: "Continue Inferno stage 2 renderer from the tested capture kernel, using the existing
nexclash/specnext checkouts on codex/inferno. Follow CLAUDE.md and games/inferno.md. No sprite
NEX is ready; complete the replacement display and remaining build gates."

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
- Game data stays in specnext; the visual design is now approved, but no sprite build exists.
- GitHub reports specnext as public. The user explicitly authorised publishing these Inferno
  recordings, snapshots, previews and builds there on 2026-11-05; do not re-ask in this session.

## Status and open items
- Intake gates PASS: all eight raw recordings replay to the end (449,659 frames, no desync;
  specnext replay_checks.txt). Each sampled survey covers 2,001 frames (16,008 total), caller and
  plain boot gates PASS; these are preliminary analyses, not sprite verification. No supported
  engine was detected. Default-tail level builds are diagnostic only; use the flat Inferno.nex.
  Original copier sample costs: median 200,191-212,139 T, max 214,693-274,392 T (per-level surveys).
- Initial renderer/writer/caller surveys and full producer census are retained in specnext;
  Stage-1 findings below supersede their preliminary ownership/layout conclusions.
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

## Stage-1 findings (2026-11-05; detailed captures in specnext design/README.md)
- C000 five-byte scenery lists: 9385/938E/93BF. C100 actor lists: player 9535 (IX=AC44),
  projectiles 9766 (AC5C) and 973D (ACC4), actors 953B (D449); actor stride self-modifies 15/10.
- Actor pointer = C100 + unsigned (IX+4), second byte wraps within C1xx. Header low two bits
  select tile page; rows are width/signed dx/signed dy/tile bytes, zero ends the WHOLE image.
  Width 1 is specialized, not partial. IX is the live record. Analysis captures at 9599/969F;
  runtime hooks now use the following single lookup instruction at 959B/96A1.
- x=(IYl+dx+j)&255, y=((IX+2)+dy)&255, then clip x=0..31/y=0..17. Tile map =
  9B00+64*y+2*x (9A80 is lookup storage); graphics DC00+8*(low+256*(high&3)), attributes FC00+tile,
  screen y=48+8*y. Actor tiles overwrite in original order after scenery.
- Metadata points into 9A00: 9701 updates health via tracked records/IX/IY+5, and 9306 consumes
  the tracking list. Preserve all original tile-map and ULA writes, including invisible stale bytes.
- Initial 25 ticks across six levels reconstruct all 36,864 viewport pixels; later quick runs below
  extend this and correct missing eight-bit x wrap. The initial 35-chunk estimate was sample-only.
- Sampled hooks have IFF=1/IM2. IRQ uses FFFF/FFF4 trampoline to 998B; handler pushes AF/EI and
  its 9994 path switches SP/unwinds copy stacks. Mixed title/game scans used up to 334 stack bytes.
- Level-4 setup touches all C000-FFFF (232 writer PCs); no scratch span there is proven. Runtime
  graphics/cache lifetime needs content checks. Original 9535 list x367: median/max 1,732 T,
  not the cost of every image. Full level-2 loop census: 11,921 ticks, no desync.

## Approved design
- Figures: capture every C100 actor image in original order, including BOTH projectile lists,
  effects and collectables. Track one complete run-list per draw ordinal and IX;
  do not collapse several draws by owner or count 9790 as a figure. Keep C000 scenery intact.
- State: execute original producers, collision logic and ULA copier unchanged. At 8F7C retain
  the clean scenery tile map. Build a Layer 2 view of that scenery over y=48..191, opaque black
  included, and hardware sprites from actor images. Top 48 rows remain transparent so the
  original ULA HUD shows. This is the exception to the usual ULA-only scenery display: original
  scenery bytes remain on the ULA underneath, while the displayed clean copy masks the old figures.
  No virtual screen reader or collision rewrite is needed because original memory stays intact.
- Display: preserve actor draw priority and tile colours; approved option B adds enclosed black
  interiors to coloured ink (solid silhouette), with no added outline. Deliberate rectangular
  tile knockouts outside the silhouette disappear. Option A remains in the comparison only.
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
  state comparisons, plus Next hardware testing in stage 3. At design approval no loader was implemented; the foundation below is now available.

## Stage-2 loader foundation
- Original TZX/BASIC reaches first USR 24200 before compressed main runs; bootstrap snapshot
  MD5 `9814983816aafb2b9efd99344dd8c221`. No synthesized BASIC or independent level-start restores.
- Loader at 386E-3944, register block 3945; alt-ROM sources 24/26, immutable tape pages 32-55,
  descriptors/cursor page 68. Replace only 0562 (original bytes checked), preserve the 7319 wrapper.
- Abstract byte-decoder units: 16,946,824 hook instructions; load/verify/capacity/error/EOF/wrap
  and two broken controls PASS. Pulse-level extension and seven Na/Nb prefixes are below.
- Bootstrap tail 5D30-5D65 is untouched only in the initial 2,000-frame scan (span 5D30-5E59).
  Later lifetime and continuous Nb/game/ending behavior remain unproved. Source/recipes: build/README.md.

## Stage-2 capture kernel results (2026-11-05; mid-stage checkpoint)
- New capture code: 352 bytes at 3A00-3B5F, in the exact original alt-ROM image. Patches:
  8F7C CALL 9535, 8F92 CALL 9790, and single DD 6E 04 lookups at 959B/96A1. Original LD H,C1
  instructions remain intact; legitimate ISR resumes between those instructions are preserved.
- Page 68: SP save/flags at 03F0, scenery 0400-087F, whole run-list log from 0900, private stack
  below 1FF0. DI before mapping/28 MHz, original mapping/registers/SP and 3.5 MHz before EI.
  CALL return bytes reproduced exactly: no game-stack or game-RAM exclusions in the hook check
  beyond the explicitly compiled replacement bytes (which must retain their expected values).
- All six 2,000-frame capture checks PASS in one process: 12,000 frames, 16,903 hook events,
  4,038,809 hook instructions, 13,194 actor draws, 1,854 original tile checks and 1,850 complete
  visible-ULA checks (68,198,400 viewport pixels). No desync or state/log/reconstruction mismatch.
- Units per level: 40 capture-coordinate cases; inactive/full/overflow/ordinal/commit guards;
  four snapshot-site refusals; four actual IRQ entries plus four forced stack-unwind cases.
  IRQ tests execute FFFF/FFF4 and the handler through RET (the earlier bounded test missed the
  trampoline). Broken DI, interior jump and live-game-byte writes are detected using their own data.
- Wrong-coordinate control detected 841 times; dropped-writer control 1,666 times. B model units
  cover closed/open interiors, whole-image fill across a tile seam, palette, overwrites, content
  cache keys and clip/wrap. These do NOT constitute a runtime sprite rasterizer test.
- Sample maxima: 21 image calls, 58 visible 16x16 chunks, 56 distinct patterns, 64 old+new pattern
  union. Graphics-region bytes have 9-109 distinct states per quick run; no permanent pointer key.
  Dirty-cell histograms count tile IDs only; source-content invalidations remain extra work.
- Capture-only added cost upper model: 3,562.625 equivalent 3.5 MHz T for scenery, <=758.375 per
  actor, 97.75 commit; max tick 8,342.625. Includes one extra 28 MHz cycle per modeled memory read,
  conservatively charges speed transitions. NOT a hardware measurement or total renderer budget.
- Per-event simulators use pooled distinct slots; pooled/unpooled 810-frame results are identical.
  Original intro and level-4 scans (2,001 frames each) never read/write either new ROM region.
  Other levels/full-recording ROM-reader coverage remains open.
- Pulse oracle now executes unmodified ROM against TZX timings (no fast load or accelerators).
  Fixed canonical C from 22 to 7E: 32 loads +32 verifies +3 failure cases strictly match CMP/live RAM.
  All seven physical-pulse loading prefixes match at every 731C return and the 718C handoff,
  with equal R inputs at the beeper. Reference polarity 0 only; timeout/other polarities unproved.
- Loader-only bootstrap and capture-only snapshot NEX builds pass NEXLOAD/foreign-ROM3 boot checks.
  Neither enables replacement layers or is a hardware candidate. Checksums/recipes: specnext build/.
  Original plain Inferno.nex is unchanged. No auto registration, sprite build or full verify/stamp.

## Design decision
Approved 2026-11-05: user said "all design decisions approved" after clarification of item 5
(continuous loads preserving score/health/equipment and original modal/intro/ending screens).
Every figure/effect/pickup, original colours/depth, B solid enclosed interiors/no outline, and
clean Layer 2 scenery with original ULA retained are settled in Approved design above.
Technical proof gates remain required. The comparison is a design simulation, not a sprite build.

## Stage-1 results
Preview MD5 `cf3fda58c14e87d91c55fe2773165d6a`, model_checks.json
`e2b72180a10af6a7261fab91a131ca69`, level-2 census `46261ceb27a13580bddf0ea50d67ec5b`.
Asset checksums: specnext design/manifest.json. Tools/canary/doccheck PASS, diff clean;
no engine, full sprite verification, stamp or new sprite NEX at stage 1.

## Lessons
- [tool nexclash/inferno.py] Demonstrated: IRQ injection must execute the FFFF/FFF4 trampoline,
  not stop before the handler. Actual and forced-unwind paths now run through RET; single-
  instruction actor sites retain original interrupt-resume entrypoints.
- [local: Inferno pulse return state] Demonstrated: byte-decoder comparison alone missed wrong
  canonical C/AF'. Actual TZX pulse emulation establishes 7E; strict return-register checks pass.
- [tool nexclash/inferno.py] Per-event verification uses distinct pooled machines; A/B output
  matches unpooled. RAM comparison checks compiled site bytes and detects a broken live write.
- [doc docs/LEARNINGS.md §2.6 Process / tokens (this sandbox)] Observed: stdin /dev/null overrides
  a Python heredoc driver. The warning is incorporated; retained capture-all CLI runs detached.
- [card detect.drawing-parameters §Probe and stop] Demonstrated: broader Inferno quick ticks need
  eight-bit x wrap before clipping (255+1=0). The former 25-tick model missed this; the incorrect
  transform now fails against original map writes and visible ULA on held-out ticks.
- [local: Inferno 0562 decoder] Demonstrated: the flag consumes a tape byte but not DE capacity;
  original ROM instruction oracle caught a missing compensating DEC DE in the first hook draft.
- [local: Inferno ROM destinations] Demonstrated: slot-0 payload mapping must not change original
  reads/writes below 4000 on address wrap; explicit guarded store/ROM peek passes boundary tests.
- [local: Inferno continuation input] Observed: 7C37 consumes R for the beeper, so excluding R from
  register checks is insufficient. Prefix tests synchronize and report every R input; physical
  timing and continuous-game equivalence remain open instead of excluding derived state.
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
- retries: [tool nexclash/inferno.py] Pulse emulation caught canonical EAR state; complete IRQ
  tracing caught the truncated ISR test. Actor hooks now replace one complete lookup instruction.
- environment: [local: managed executor] Waited for startup, installed requirements, cloned both
  complete branches and refreshed main. Reproducible evidence lives in the authorised specnext branch.
- hand-rolled: [local: Inferno verification] Uses SkoolKit's original ROM/pulse loader and native
  RZX source; per-engine hook/log/model comparisons remain in the engine, not a parallel toolkit.
- scratch: [local: Inferno probes] Kept structured checks, scans and diagnostic builds; temporary
  pulse/trace/source-insertion scripts dropped. Batch replay is retained as capture-all.

## Technique use
- patch.display-atomic-switch: no help: renderer not implemented; double-buffered commit still required.
- optimise.pattern-cache: helped: measured content keys and pending-pattern union; runtime cache remains unbuilt.
- verify.model-reconstruction: used: quick tile/ULA closure, dropped-writer and incorrect-coordinate controls.
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: original tile writes carry collision ownership and must run unchanged.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.
- detect.drawing-parameters: helped: captured IX/IY and live run lists distinguish whole actors from tiles.
- detect.buffer-layout-producer: corrected: visible colour checks distinguish black-masked stale bitmap data.

## Stage log
- 2026-11-05: stage 2 capture checkpoint (extended session, ~100 tool calls, 0 design questions).
  Knowledge refreshed: nexclash main 9484427 / specnext main 6bce6aa, already included. Six quick
  replays, original RAM/register comparisons, actual IRQ/forced-unwind units, pulse transport and
  seven loading prefixes PASS. New engine sections only; no other engine module changed.
  Canary, pinned assembly, doccheck and diff checks PASS. No full verify/stamp.
  Stage 2 remains incomplete: renderer, colour workflow and continuous frontend are next.
- 2026-11-05: stage 2 loader-foundation checkpoint (~25 min, ~80 tool calls, 0 user rounds).
  Knowledge refreshed from main (already included); original decoder unit checks, all seven Na/Nb
  handoff prefixes and diagnostic bootstrap checks PASS. Engine module is new and contains the
  loader, independent ROM oracle and prefix harness; no other engine module read whole or changed.
  asm2profile/doccheck/diff checks PASS. Stage 2 remains INCOMPLETE: no sprite build, quick RZX sprite verification or full proof/stamp.
  Natural boundary after loader checks; continuing build starts from this block in a fresh session.
- 2026-11-05: stage 1 analysis/proposal ready (~18 min, ~80 tool calls, 0 user answer rounds);
  nexclash knowledge main 9484427, specnext main 6bce6aa. Full level-2 census PASS; 25-tick
  six-level original-image model PASS; tools/canary/doccheck PASS. All design decisions approved
  after one clarification (item 5) and one approval round; stage 2 starts in a fresh session.
  Revised one detection card and the existing census;
  no engine module read or written. Disposable game preview calculations dropped; captures retained.
- 2026-11-05: stage 0 complete (~40 min, ~120 tool calls, 3 user rounds), knowledge from nexclash
  9484427 / specnext 6bce6aa. Full raw replays and all sampled gates PASS; tools/canary/doccheck PASS.
  No engine module read: flagged game copy/producer instructions and shared diagnostic functions
  inspected to fix their reports and profile the preview. Next stage starts in a fresh session
  at this natural boundary (PLAYBOOK Sessions); no sprite engine or approved design yet.
