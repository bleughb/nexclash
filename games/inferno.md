# Inferno

## Next session
Stage: 2 (continued)    State: immutable source components pass; total timing FAIL
Inputs: specnext/reference/inferno/    Branch: codex/inferno (build/CONTINUE.md)
Start: refresh main; read build/actor_jobs.md, actor_b_compiler.md, actor_packing.md and frame_pipeline.md.
Read: inferno.py run_actor_job/actor_job_checks/model_verify/run_actor_pack and matching ASM.
Next: make exact live validation affordable; prove any source-lifetime deduplication. Then assembled
  stream dispatch, runtime content cache/allocator and safe early hook/preparation schedule.
  Page 78 pins ordered original run-list/bitmap/attribute bytes in page 122. Page 75 accepts copied
  raw tiles. Six quick correctness runs PASS: 128 captures / 13,066 exact validations / 128 B fills.
  Host selects cache entries; no installed cache/scheduler. Never accept pointer/hash-only validity.
  Source work alone reaches 24.650 ms/update; cold snapshot-inclusive L1 899.447 / L6 84.289 ms,
  target 10 ms TOTAL, excluding lookup/allocation/uploads/queue/wrappers. Long DI walker is not safe.
  Page 77: physical DDMA high staging 216–223; DMA/CPU fallback (build/actor_high_dma.md).
  Physical stalls/ownership/IRQ proof remains open. Keep current AND pending pattern allocations.
Workflow: Inferno6.rzx --quick 2000; six original level replays at milestones; targeted level-4 shop.
Open: pattern layout/protected uploads/complete-frame switch, FLASH/modal/frontend/ROM lifetime,
  recolour/sheets and hardware/whole-tick timing. Apply caller-speed/R and ORIGINAL-pace before build.
Next prompt: "Continue Inferno stage 2 from build/actor_jobs.md and CONTINUE.md. Preserve pinned exact
live data, original RAM/registers/priority and approved B visuals. Solve validation cost and safe live
preparation, retain profitable gated blitter/DMA paths; keep sprites disabled until complete."

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
- Game data stays in specnext; the visual design is now approved, but no sprite build exists.
- GitHub reports specnext as public. The user explicitly authorised publishing these Inferno
  recordings, snapshots, previews and builds there on 2026-11-05; do not re-ask in this session.

## Status and open items
- Intake PASS: eight original recordings, 449,659 frames, no desync (replay_checks.txt); sampled
  surveys 2,001 frames each (16,008 total), caller/plain boot gates PASS. No supported engine.
  Original copier median 200,191-212,139 T, max 214,693-274,392 T across sampled levels.
- Initial surveys/full producer census remain in specnext; Stage-1 findings supersede preliminary
  ownership/layout conclusions. Runtime draw-list loop 93E0 reads C000 and writes tile IDs/flags;
  operand 9419 changes 0 to FC, so nearby code cannot be assumed immutable.
- Mixed title/game IRQ sample reads IY+1/+7, alternate registers, switches stack and uses up to
  334 bytes below interrupted SP. Its union does not prove safety at a particular hook.
- Plain Inferno.nex uses 79-byte tail 9A80-9ACE, below C000: initial 1,000-frame write-first and
  nextboot checks PASS, MD5 0a3bde4734c5b3f15ad0f2a55cc81e19. Default-tail survey builds superseded.
- Original full-recording contact sheets: recording_overview.png; level 4 reaches the equipment
  shop grid. Ending BE69 scrolls, BCDF draws text/medals, BC64 clears. Preserve the ULA sequence.
- Shared tools/canary passed intake/capture checkpoints (Chuckie unchanged). No test cheat or game
  patch. Independent level snapshots do not establish continuous TZX transitions; see Approved design.

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
  scratch/state initially 68-71, scenery baseline through 73. Expanded pages 96-223 are now
  user-authorized for caches/tables; hardware display stores remain bounded. Allocation awaits bootstrap and ISR
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

## Stage-2 loader foundation (build/README.md)
- Original TZX/BASIC reaches first USR 24200; bootstrap MD5 9814983816aafb2b9efd99344dd8c221.
- Decoder 386E-3944, registers 3945, alt-ROM 24/26, tape 32-55, descriptors/cursor 68.
  Replaces only checked ROM 0562; retains 7319. Byte/pulse oracles, seven Na/Nb prefixes and
  negative controls pass; canonical C=7E. Continuous Nb/game/ending and physical timing unproved.
- Tail 5D30-5D65 only has an initial 2,000-frame lifetime scan. Loader/capture diagnostic NEX boot
  checks pass with NEXLOAD/foreign ROM3; neither installs the frame/actor pipeline or is a release.

## Stage-2 frame pipeline (build/frame_pipeline.md)
- Textmap compiler replaces the historical 130.069 ms Layer 2 path with live one-bit tiles.
  Private page 69, double-buffered maps/definitions page 14. Worst L6 scenery 6.547 ms.
- FramePatch at 8F95 runs after the original copier, preserving main/alternate registers, RAM,
  stack and mappings. Readiness stays zero until the complete actor pipeline exists. Pending
  Copper owns its buffers until acknowledged; incomplete captures cannot prepare a frame.
- Six original quick replays: 1,850 hooks / 68,198,400 pixels, 16,903 capture events PASS. Source
  lifetime sampled in 1,850 scenery / 13,159 actor cases; not permission for persistent pointer keys.
- Setup copies actual nine-bit ULA ink AND paper palettes; clip/scroll and 294,912 RGB pixels pass
  across banks/buffers/FLASH phases. FLASH inverts bitmap bits, not palette indices. Actual ULA
  FLASH clock remains open. One-time setup 2.030 ms; hardware video/raster/IRQ proof remains open.
- Copper commits complete attributes/map/ack at line 224 and HALTs. Synthetic attributes only;
  actor pattern compilation remains open. Late commits, serial wrap, busy/count/ready guards pass.
- Original L4 gameplay return, frame 51,805: 9019 hook stops Copper, hides all replacement layers,
  invalidates capture and reproduces LD SP,86D5. 256 bit cases/four negative controls PASS. Other
  pause/message/intro/ending paths remain open. Hide 0.035 ms.
- Capture + preparation max 8.715 ms; 58-sprite queue ~0.55 ms (~0.64 shrinking). Full capacity/
  FLASH-heavy cases exceed 10 ms before actor work. No total timing PASS or NEX integration.
- ROM code: capture 3A00-3B80, modal 3B90-3BDF, frame 3BE0-3C30; all below 3D00.
- Historical colour-only packer: 233-byte page 75, generic 128 KiB row table 96-111, canvas 112-115;
  build/actor_packing.md records that checkpoint's checks/cold costs. Culling remains a host model.

## Immutable job checkpoint (2026-11-07; build/actor_jobs.md)
- Page 78 / stream page 122 captures ordered original geometry, IDs and bitmap/attribute bytes.
  Exact byte/length/phase/paint comparison preserves pinned data; malformed/overflow jobs never publish.
- Page 75 pinned input forbids original graphics reads. Host dispatch/cache selection remain models.
  Six quick replays: 128 captures / 13,066 validations / 128 complete B fills pass; no display enabled.
- DMA/DDMA prepared-span evaluation adds 27 cases. Single spans <64 bytes bypass setup with CPU;
  larger copies/uploads keep gated shared backend, no-blitter and CPU fallback. Stalls remain unknown.
- Snapshot-inclusive cold totals FAIL: L1 899.447 / L6 84.289 ms, target 10 ms total, excluding
  lookup/allocation/uploads/queue/wrappers. Source work alone peaks at 24.650 ms/update. No safe hook.

## Whole-image B / prepared transfer checkpoint (2026-11-06)
- Page-76 bitset flood fills complete images before clipping; masks 116/117, generic lookup 128-135.
  Four-unit service <=0.204 ms sampled, excluding external wrapper. Private DONE never enables display.
- Six original quick replays: 128 assembled B fills / 108,288 actor pixels, 1,319 decoded tiles,
  16,903 capture and 1,850 post-copy comparisons PASS. Seam/capacity/resume/negative units pass.
- All 128 sampled first-use keys exist >=85 recorded frames early in live C100 data. This is a
  host census, not a safe preparation hook, schedule, catalogue or installed exact-content cache.
- Page 77 reuses PR #93's gated DMA functions for prepared rectangles and protected hardware pairs.
  Both current/pending owners are guarded. Policy 1 disables blitter; narrow ordinary-DMA rows use
  CPU. CPU costs: 128-byte rectangle 0.338 ms / DDMA setup 0.148 ms; pair 0.267 / DMA setup 0.068 ms.
  Transfer stalls, real ownership/IRQ safety and integrated allocation remain UNPROVED.
- Cold capture/scenery/colour/fill FAILS 10 ms total: L1 882.151, L2 70.787, L3 131.485, L4 387.688,
  L5 74.742, L6 77.563 ms; excludes cache validation/allocation, uploads, queue and service wrapper.
- No NEX includes this work. Runtime snapshots/cache/prewarming, actor pattern layout, full switch,
  FLASH/modal/frontend/recolour/hardware remain open. Recipes/evidence: build/actor_b_compiler.md.

## Capture foundation (historical; build/README.md)
- Hooks 8F7C/8F92/959B/96A1 preserve original CALL stack and LD H,C1; page 68 owns state/log/stack.
  Original RAM/register/IRQ/unwind and negative checks pass. Sampled maxima: 21 calls, 58 chunks,
  56 patterns and 64 old+new union. Mutable graphics forbid persistent pointer-only keys.
- Intro/L4 ROM scans cover 2,001 frames only; startup/reader lifetime remains open.

## Stage-1 results
Approved preview/model/contact-sheet hashes and recipes: specnext design/manifest.json and
build/README.md; intake tools/canary/doccheck passed. No sprite stamp.

## Lessons
- [local: Inferno immutable sources] Pin complete ordered original bytes before resumable work;
  exact validation can itself exceed the budget. DI component correctness does not prove safe entry.
- [local: Inferno B fill] Bitset connectivity preserves whole-image fill; a bounded call is not a cold
  latency/schedule proof. Frame-boundary source availability does not establish a safe hook.
- [local: Inferno blitter] Physical SRAM includes 040000 aperture offset; high staging is 216–223.
  Tiny copies prefer CPU. Charge stalls separately; protect current AND pending pairs/allocations.
- [local: Inferno cold actor construction] Exact reuse is high; first-use work exceeds 10 ms. Prewarm
  live snapshots, never a recording catalogue; retain exact-content validation.
- [local: Inferno frame pipeline] Post-copy restoration/Copper shop cancellation pass sampled checks;
  real FLASH, other modal entries and synthetic-attribute replacement remain open.
- [local: Inferno representation] Hardware one-bit expansion cuts sampled scenery 130.069 to 6.547 ms;
  capacity, display integration and total timing remain separate gates.
- [local: Inferno validation loops] Aligned flags, DI stack clearing/unrolled comparisons save 13.35%
  on unchanged L6 scenery; this does not solve cold or total cost.
- [local: Inferno scenery budget] Validate distinct sources once; retain failed total gates instead
  of calling primitive timings or host scheduling a full-render pass.
- [tool nexclash/inferno.py] Retain scratch across cache tests; same-ID/attribute/FLASH/collision mutations
  and broken-clear controls detect stale validation.
- [tool nexclash/inferno.py] IRQ injection must traverse FFFF/FFF4/998B through RET, including unwind;
  single-instruction actor sites preserve interrupt-resume entrypoints.
- [local: Inferno pulse return state] Actual TZX pulse oracle caught wrong C/AF'; canonical C=7E.
- [tool nexclash/inferno.py] Distinct pooled machines match unpooled checks; whole-RAM comparison checks
  compiled sites and catches a broken live write.
- [doc docs/LEARNINGS.md §2.6 Process / tokens (this sandbox)] /dev/null stdin overrides a Python heredoc;
  warning incorporated. Detached CLI drivers retain logs/status.
- [card detect.drawing-parameters §Probe and stop] Apply eight-bit x wrap before clipping (255+1=0);
  original-map/ULA negative controls catch the earlier 25-tick model's error.
- [local: Inferno 0562 decoder] Tape flag consumes a byte, not DE capacity; compensate DEC DE.
- [local: Inferno ROM destinations] On address wrap, preserve original below-4000 ROM semantics;
  guarded stores/ROM peek pass boundaries while slot 0 maps payload.
- [local: Inferno continuation input] Beeper 7C37 consumes R; synchronize/count inputs and guard dead
  stack reads. Prefix equality does not prove continuous-game or physical timing.
- [card detect.buffer-layout-producer §Probe and stop] Black attributes hide stale bitmap bytes;
  compare visible colours while retaining original bytes. Candidate migrated to schema 4.
- [tool tools/probes/rzx_census.py] Bounded register/mapped-memory captures expose whole-image ownership;
  exact PC/frame/code, per-frame bounds and absent samples have smoke checks.
- [local: Inferno collision tile metadata] 9701 consumes object pointers in tile metadata; keep all
  original map/ULA writes and render separately.
- [local: Inferno transfer capacities] Preserve actual TZX lengths and 0562 behaviour, not capacities.
- [tool nexclash.snapinfo] RAM return/retained BASIC in snapshots does not establish a running loader.
- [tool nexclash.survey] Literal unknown is not a known engine; synthetic detector regression added.
- [tool nexclash.simrun] Opt-in C frame callbacks avoid tracing; 300-frame preview stays identical,
  profiled 19.238 to 0.724 s. Autosave/buffer parity tested.
- [doc docs/MAINTAIN.md §Commit, PR and the reference files] specnext is public; user authorized Inferno
  publication. Corrected visibility guidance in place.
- [local: Inferno startup] L1 map is write-first, permitting plain tail 9A80. Later lifetime is separate.

## Friction
- environment: [local: Inferno source jobs] Restored archived work only into absent work/, merged both mains
  preserving Inferno status/process guidance; measured shared adapter spans instead of new DMA code.
- reuse: [local: Inferno shared DMA] Reused upstream library/model/selfchecks; merged remote 6aa2992
  after its concurrent main refresh, retaining upstream tests and the packet labels needed here.
  No other game's output changed. New game/reference data stays in specnext.
- reuse: [tool tools/probes/rzx_census.py] Extended the existing census with bounded point captures;
  no parallel game tracer. Existing flags/output are preserved when capture is not requested.
- retries: [tool nexclash/inferno.py] Pulse emulation caught canonical EAR state; complete IRQ
  tracing caught the truncated ISR test. Actor hooks now replace one complete lookup instruction.
- hand-rolled: [local: Inferno verification] Uses SkoolKit's original ROM/pulse loader and native
  RZX source; per-engine hook/log/model comparisons remain in the engine, not a parallel toolkit.
- scratch: [local: Inferno probes] Preserve structured checks/scans/builds; insertion scripts stay local.

## Technique use
- optimise.pattern-cache: helped: full-content census finds early live candidates; runtime snapshots,
  cache and scheduling remain open. Prepared uploads now reject both current/pending pattern owners.
- patch.display-atomic-switch: helped: front-bank/visibility guards pass; runtime atomic commit remains open.
- verify.model-reconstruction: used: quick tile/ULA closure, dropped-writer and incorrect-coordinate controls.
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: original tile writes carry collision ownership and must run unchanged.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.
- detect.drawing-parameters: helped: captured IX/IY and live run lists distinguish whole actors from tiles.
- detect.buffer-layout-producer: corrected: visible colour checks distinguish black-masked stale bitmap data.

## Stage log
- 2026-11-07: stage 2 continued; pinned sources and physical high-SRAM DDMA added, scratch preserved.
  Six quick correctness, shop, assembly/tools/canary PASS; high-DMA units/L6 regression PASS. DMA span
  evaluation removes tiny-copy setup. Total timing FAIL (899.447 / 84.289 ms L1/L6); no sprite NEX.
- 2026-11-06: continued from GitHub; restored work; integrated remote 6aa2992 (main 3efa10f),
  specnext main cc9c7df. Added quota-serviced whole-image B fill, live prewarm census and
  shared gated blitter/CPU prepared transfers. Six quick correctness runs and shop units PASS;
  total cold timing FAIL (L1 882.15 ms / L6 77.56 ms). No sprite NEX; stage 2 remains incomplete.
- 2026-11-05: resumed; merged main 7e9b31c (workflow fixes), canary PASS. Added checked actor
  packing and exact-content/culling census; six-level evidence in build/actor_packing.md. No sprite NEX.
- 2026-11-06: resumed preserved workspace; six quick frame-hook replays, display/queue/modal
  units and source-lifetime checks PASS. Evidence in build/frame_pipeline.md; sprites remain open.
- 2026-11-05: textmap architecture checkpoint. Reviewed Next instruction/DMA/tilemap/memory
  references and local board benchmarks. New standalone worker, six quick replays, palette/
  capacity/negative units PASS; shop census exposes missing modal hook. Expanded RAM authorized.
  Assembly/doccheck/diff PASS; main unchanged; no sprite NEX. Evidence: build/timing_architecture.md.
- 2026-11-05: earlier stage-2 checkpoints built the bank loader, pulse continuation, capture and
  scenery components. Bundled assembly, bounded/six quick differential checks, tools/canary/doccheck
  passed at the recorded checkpoints; timing and continuous release remained open. Detailed counts,
  hashes, recipes and individual checkpoints are retained in build/README.md and the evidence record.
- 2026-11-05: stages 0/1 intake/full raw replays and approved design; six-level model/level-2 census
  and tools/canary/doccheck PASS. Cards/diagnostics revised; evidence in specnext design/.
