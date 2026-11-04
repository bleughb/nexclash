# Inferno

## Next session
Stage: 2 (build, continued)    State: loader foundation committed; sprite engine NOT built
Inputs: specnext/reference/inferno/    Branch: codex/inferno (both repositories)
Start with: refresh from main, then read Stage-2 build design/results below and build/README.md.
Checks: python -m nexclash.inferno --loader-tests ../specnext/reference/inferno/Inferno.tzx
Read: PLAYBOOK stage 2; nexclash/inferno.py (loader/oracle/prefix tests); asm/inferno_hooks.asm.
Open: pulse-level ROM equivalence; continuous startup/play through Nb initializers and ending;
  full startup-tail lifetime; actual sprite/Layer 2 hooks, modal transitions, interrupts and timing;
  colour maps/sheets; engine auto/verify/unit contract, registry entry and quick RZX sprite checks.
Next prompt: "Continue Inferno stage 2 (build) from the loader-foundation checkpoint. Clone
bleughb/nexclash and bleughb/specnext side by side, checkout codex/inferno in both, and follow
nexclash/CLAUDE.md and games/inferno.md. Stage 2 is incomplete; no sprite NEX is ready."

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

## Stage-2 build design (in progress)
- Loader foundation before display hooks: `nexclash/inferno.py`, `asm/inferno_hooks.asm`,
  profile `inferno.json`. Unregistered until sprite `auto`/verify/colour contract is implemented.
- Only alt-ROM 0562 changes (original bytes checked). The 7319 wrapper already exchanged AF
  and disabled interrupts. Relocate the original 05A9-05E2 decoder into FF space below 3D00;
  preserve alternate registers, IX/DE, flags and failure behavior. Canonical byte-boundary tests
  exclude physical pulse acquisition/EAR phase; the original decoder is the independent oracle.
- All 32 flag/payload/checksum blocks stay immutable in pages 32-55; descriptors/cursor in page
  68. Map slot 0 only while DI, restore FF before return, never borrow a game RAM slot. EOF fails.
- Bootstrap is the original TZX/BASIC at first USR 24200. Cursor starts at raw block index 4.
  Prefix tests compare original 7131 through Na execution/Nb load, stopping before CALL Nb.
- Renderer interfaces: 8F7C clean scenery map, 9599/969F actor runs, 8F92 commit preparation;
  preserve every producer/metadata/ULA write. Modal hooks, resources, interrupt safety, atomic
  commit, cache lifetime, colour-map integration and measured timing remain unimplemented.

## Stage-2 loader foundation results (2026-11-05; mid-stage checkpoint)
- Source: `nexclash/inferno.py`, `asm/inferno_hooks.asm`, `docs/profiles/inferno.json`.
  Unregistered deliberately: no `auto`/sprite verifier, colour maps or sheets yet. The evidence
  record is excluded from automatic rebuild/verification planning; it has NO verified stamp.
- Assembled decoder: 215 bytes at 386E-3944, register block starts 3945; never enters 3D00-3DFF.
  Two alt-ROM source pages (24 and 26), payload 32-55, state page 68. Original ROM bytes checked
  at 0562 before its JP is installed; every original byte outside the hook/entry areas retained.
- Byte-decoder tests PASS: 32 real blocks + 32 verify blocks, 9 capacities, wrong flag,
  bad checksum, verify mismatch, exhaustion, 3 ROM/wrap destinations + 3 verify boundaries;
  2 broken assembled controls detected (missing store, wrong parity comparison).
  16,946,824 hook instructions audited; no mapped slot 0 with interrupts enabled;
  tape payload unchanged, only state cursor written. All CMP registers/live RAM match original
  ROM instructions under canonical byte-boundary inputs. This is NOT pulse-level equivalence.
- Seven crafted original 7131 loading calls PASS to 718C: 4 ROM loads each, original Na initializer
  executed, Nb installed but NOT executed. Per case: 208,567-210,270 outer instructions,
  16,393 original I/O writes; all registers/live RAM/I/O match. Thirteen differing dead-stack
  bytes per case are never read before the handoff (writes remove the read guard).
  Original beeper 7C37 reads R 16,384 times per case: synchronize those nondeterministic inputs
  explicitly, not their derived registers/memory. No timed-interrupt or full-game claim.
- Bootstrap: execute ORIGINAL TZX/BASIC to first USR 24200 (compressed main still intact).
  Snapshot MD5 `9814983816aafb2b9efd99344dd8c221`; diagnostic loader-only NEX MD5
  `33791e6ffafce8b8a447092476cd776b`. Boot registers/RAM/ROM match with NEXLOAD printer-buffer
  damage and both Sinclair and foreign system ROM3. Tail 5D30-5D65: untouched in the original
  initial 2,000-frame scan (298-byte free span 5D30-5E59); later lifetime remains unproved.
- Prefix tests intentionally stop before Nb initialization: running farther enters a modal
  any-key loop (ECF7/ECF9 in level 0), then additional game code. The temporary keyboard/HALT
  experiments were dropped; do not substitute prefix equality for continuous-game proof.
- Reports, reproducible recipes, bootstrap snapshot and diagnostic NEX: specnext `inferno/build/`.
  Diagnostic build is NOT a hardware candidate. The existing flat Inferno.nex remains unchanged.
- `asm2profile --check inferno`, byte checks, seven prefix checks and bootstrap checks PASS.
  Final doccheck/diff checks are recorded in the Stage log. No sprite quick run or full verify ran.

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
- retries: [local: Inferno byte protocol] The independent original-ROM oracle caught flag capacity
  and ROM destination errors. Prefix experiments exposed a modal wait beyond the tested handoff;
  removed the temporary keyboard/HALT scheduler rather than reporting that as continuous proof.
- environment: [local: managed executor] Waited for startup, installed requirements, cloned both
  complete branches and refreshed main. Reproducible evidence lives in the authorised specnext branch.
- hand-rolled: [local: Inferno ROM oracle] Engine-specific byte/prefix tests execute the original
  ROM decoder independently of hook bytes; no copied generic tracer or shared simulator implementation.
- scratch: [local: Inferno bootstrap probes] Kept scan report, bootstrap assets, counts and recipes;
  dropped temporary disassembly/keyboard experiments. The per-engine loader/oracle tests are retained.

## Technique use
- patch.display-atomic-switch: no help: renderer not implemented; double-buffered commit still required.
- optimise.pattern-cache: no help: mutable graphics prohibit pointer-only cache keys; no runtime cache yet.
- verify.model-reconstruction: no help: original reconstruction evidence retained; no sprite verification claimed.
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: original tile writes carry collision ownership and must run unchanged.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.
- detect.drawing-parameters: helped: captured IX/IY and live run lists distinguish whole actors from tiles.
- detect.buffer-layout-producer: corrected: visible colour checks distinguish black-masked stale bitmap data.

## Stage log
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
