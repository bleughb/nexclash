# Inferno

## Next session
Stage: 2 (hybrid sprite build on main, not released)    Branch: main (PRs #201, #207, #230 merged)
State: full game from the tape on the Next: tilemap scenery + hardware sprites committed by Copper at line 224,
  copier write-out replaced, G3 masks, RAM SAVE/LOAD (page 123), English option (--cw-english), sprite store
  reused on a same-level restart. JNext: level ends 1-5 reach the next level, L6 the ending.
Inputs: specnext/reference/inferno/ (Inferno_masked.nex, Inferno_english_masked.nex)
Start: specnext build/hybrid.md (current handover); CONTINUE_copier_window.md is history.
Read: asm wk_select, wo_go, modal_exit, wi_stub; inferno.py copier_window_build (--cw-driver --cw-full).
Next: Kempston joystick (user 2026-11-10: not working; not fixed on main); freshness readout on hardware
  (publication rate, longest miss run, display age); shop and level-to-level carry-over on hardware; records.
Gate: copier-window gate 0 failures (OUT/9907 within tolerance) + boot checks; replay game RAM with supplied
  LD A,R values (equivalence: PLAYBOOK 6); pace, sound and freshness on hardware.
Boundary: 8EF9 follows original DI, before IM2 setup; the pause gate preserves all registers/R/RAM/
  stack and caller clocks (six RZX initialization states). Reject 86C5 (decompressor, overwritten).
Memory: copier window 80, driver 81, selection/store 82-95, saves 123. Older component pages (owned
  cache 136-215, pinned 122, DDMA 216-223): check the build uses them before relying on them.
Workflow: failed states, 1/10 sample, ONE gate (--jobs 6); JNext headless before hardware rounds.

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
- Game data stays in specnext; design approved; the hybrid sprite build plays on the Next (2026-11-09).
- GitHub reports specnext as public. The user explicitly authorised publishing these Inferno
  recordings, snapshots, previews and builds there on 2026-11-05; do not re-ask in this session.

## Status and open items
- Intake PASS: eight original recordings, 449,659 frames, no desync; sampled surveys and
  caller/plain boot gates PASS. No supported engine.
- Initial surveys/full producer census remain in specnext; Stage-1 findings supersede preliminary
  ownership/layout conclusions. Runtime draw-list loop 93E0 reads C000 and writes tile IDs/flags;
  operand 9419 changes 0 to FC, so nearby code cannot be assumed immutable.
- Mixed title/game IRQ sample reads IY+1/+7, alternate registers, switches stack and uses up to
  334 bytes below interrupted SP. Its union does not prove safety at a particular hook.
- Plain Inferno.nex uses 79-byte tail 9A80-9ACE, below C000: initial 1,000-frame write-first and
  nextboot checks PASS, MD5 0a3bde4734c5b3f15ad0f2a55cc81e19. Default-tail survey builds superseded.
- Contact sheets: recording_overview.png (L4 reaches the shop). Ending BE69 scrolls, BCDF draws
  text/medals, BC64 clears. Preserve the ULA sequence.
- No test cheat or game patch; level snapshots do not prove continuous TZX loads.

## Hardware checklist
- Plain level-1 Inferno.nex: try CSpect first, then the Next; check title/text to gameplay,
  controls, scrolling, sound, death/restart and the shop. Boot is software-checked only.
- Inferno_copier_window_*_diagnostic.nex (m2..m3d; NOT releases): play each
  beside plain Inferno.nex for a minute of level 1: same speed, same beeper sound, no hang at the
  first gameplay frame, no extra border stripes. Report core/video mode.
- Plain conversion: no later tape loads.
- Sprite build (Inferno_masked.nex; still to confirm): check intro beeper speed; title/start; all six continuous loads with
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
- Superseded in part (user brief 2026-11-09, build/hybrid.md): the copier's display work is replaced,
  scenery is a tilemap (not Layer 2), and the 35,000 T target is void (never measured). Masks and order stand.
- Figures: capture every C100 actor image in original order, including BOTH projectile lists,
  effects and collectables. Track one complete run-list per draw ordinal and IX;
  do not collapse several draws by owner or count 9790 as a figure. Keep C000 scenery intact.
- State: execute original producers, collision logic and ULA copier unchanged. At 8F7C retain
  the clean scenery tile map. Build a Layer 2 view of that scenery over y=48..191, opaque black
  included, and hardware sprites from actor images. Top 48 rows remain transparent so the
  original ULA HUD shows. This is the exception to the usual ULA-only scenery display: original
  scenery bytes remain on the ULA underneath, while the displayed clean copy masks the old figures.
  No virtual screen reader or collision rewrite is needed because original memory stays intact.
- Display: preserve actor draw priority and tile colours. Mask G3 (user, replaced B): black is see-
  through only via gaps >= 3x3 from outside; explosions B2-B8 keep B (enclosed black only).
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

## Copier window (2026-11-07; details and numbers: specnext build/copier_window.md)
- Pacing: the copier calls the 9907 limiter after row 6 (97FB); 9907 runs the beeper filler until
  the next IRQ resumes the copier (998E written only at 8F32/9914/9995). Slack after 9907, p10:
  2.9-13.2 k T, so +10 ms of hook work slips 56-81 % of updates a frame; "10 ms total" is no gate.
- The copier head 9790..97FB (416 cells, 25.2-30.8 ms) OUTs the A700 beeper buffer per cell.
  Head T = 79,477 + 101*G; per-OUT T in cw_out_t. Graphics are mutable (F400-FA36, L3 ED00-F0AF).
- Milestones (cards patch.timed-side-effect-replay / patch.work-in-timed-gaps): m2 OUTs at original T
  (CTC ch 3 polled, 32 T ticks), 9907 at the original time; model OUT -24..+56 T, 9907 -25..+43 T.
  m3a hooks time themselves (CW_X), cw_cal, lost-IRQ accounting, map copy by zxnDMA; stub
  register-block crash fixed. m3b 8F95 work as a cw_wait coroutine; m3c unfinished work dropped
  (12 %, runs to 6). m2/m3 pace and sound = plain on hardware. Exact R/IRQ later shown unneeded (hybrid).
- Never-read rule: window CALLs/IRQ pushes leave bytes only in the 4 below the copier's SP, which
  9907's PUSH DE / PUSH HL overwrite first (checked by running them; 9907 = D5 E5 in all 88,187).

## Stage-2 loader foundation (build/README.md)
- Original TZX/BASIC reaches first USR 24200; bootstrap MD5 9814983816aafb2b9efd99344dd8c221.
- Decoder 386E-3944, registers 3945, alt-ROM 24/26, tape 32-55, descriptors/cursor 68.
  Replaces only checked ROM 0562; retains 7319. Byte/pulse oracles, seven Na/Nb prefixes and
  negative controls pass; canonical C=7E. Full game from the tape runs on the Next (2026-11-09).
- Tail 5D30-5D65 only has an initial 2,000-frame lifetime scan. Boot checks pass with NEXLOAD/foreign ROM3.

## Stage-2 frame pipeline (build/frame_pipeline.md)
- Textmap compiler replaces the historical 130.069 ms Layer 2 path with live one-bit tiles.
  Private page 69, double-buffered maps/definitions page 14. Worst L6 scenery 6.547 ms.
- FramePatch at 8F95 runs after the original copier, preserving main/alternate registers, RAM,
  stack and mappings. Pending Copper owns its buffers until acknowledged; incomplete captures
  cannot prepare a frame.
- Six original quick replays: 1,850 hooks / 68,198,400 pixels, 16,903 capture events PASS. Source
  lifetime sampled in 1,850 scenery / 13,159 actor cases; not permission for persistent pointer keys.
- Setup copies actual nine-bit ULA ink AND paper palettes; clip/scroll and 294,912 RGB pixels pass
  across banks/buffers/FLASH phases. FLASH inverts bitmap bits, not palette indices. Actual ULA
  FLASH clock remains open. One-time setup 2.030 ms; hardware by eye only.
- Copper commits complete attributes/map/ack at line 224 and HALTs; live since 2026-11-09 (hybrid).
  Late commits, serial wrap, busy/count/ready guards pass.
- Original L4 gameplay return, frame 51,805: 9019 hook stops Copper, hides all replacement layers,
  invalidates capture and reproduces LD SP,86D5. 256 bit cases/four negative controls PASS. Other
  pause/message/intro/ending paths: hybrid modal_exit at 901C (hardware ok). Hide 0.035 ms.
- Capture + preparation max 8.715 ms; 58-sprite queue ~0.55 ms (~0.64 shrinking). Judged then against
  the 10 ms target, which was void (Copier window).
- ROM code: capture 3948-39F2 + 3A00-3B72, modal 3B90-3BDF, frame 3BE0-3C30; all below 3D00.

## Sprite pipeline (build/pipeline.md, build/hybrid.md)
- Driver, page 81, from the 8EF9 gate: 256 C100 indices, snapshot, exact-stream duplicates (shared
  payload), colour, B, store; valid last. Model = independent oracle, all six levels; 3.2-6.9 s (L6).
  Installed, with loading bars; skipped on a same-level restart. Nothing reads CAP_LOG before the window.
- Dispatch, page 69 1800, coroutine after the scene: each log record = entry + exact live compare,
  polled per tile. Gate 0 failures, 0 misses; 14.9 % dropped (12.3 % before), runs to 14. NEX m3d.
- Selection, pages 82-95: 8EF9 chunk index by content; 128-slot protected store (recency list, both
  pattern-RAM halves); FLASH phase 1 for the four L1 FLASH images. Gate 0 failures, margin 109 T.
  On hardware since 2026-11-09. Drop figures predate the write-out reclaim; freshness unmeasured.

## Historical components (build/actor_jobs.md, actor_b_compiler.md, README.md)
- Pages 78/122 pin source bytes; 75 tiles; 76 whole-image B; masks 116/117, lookup 128–135; 77 gated
  DMA/DDMA with current AND pending guards. Hooks keep the CALL stack; page 68 owns state/log/stack.

## Lessons
- [local: Inferno JNext tape trap] JNext rewrites A at ROM PC 056B while its tape trap is on: new code in old tape ROM must avoid that PC. Hooks at 04C6/0574.
- [card detect.routine-removal §Use / do not use] Skipping the copier kept game RAM equal (L1-4, L6) once
  LD A,R values were fed: exact R/IRQ/copier-RAM preservation was unneeded; disassembly found 9804 logic.
- [card patch.work-in-timed-gaps §Probe and stop] Every added coroutine stage raises the drop rate: report drops and runs.
- [local: Inferno driver oracle] A loader driver's dedupe is exact streams, not the host's tile tuples:
  row splits differ, so the exact validator (not the tuple) defines duplicates.
- [card patch.work-in-timed-gaps §Use / do not use] Finishing deferred work after the limiter eats the slack the window
  saved; drop the frame instead (display keeps the last one) and count run lengths of drops.
- [card patch.work-in-timed-gaps §Contract] A loop using SP as data pointer yields without CALL: save SP + live regs.
- [local: Inferno copied routine] Compare every hand-copied asm routine's results with the original.
- [doc BRIEFING A1] Hook code under the stub's register block (rom_end) is lost
  at boot; models without the stub cannot see it: compare hook bytes after a simulated boot.
- [card patch.timed-side-effect-replay §Probe and stop] Calibrate tick-quantized constants over all CTC phases (5 phases left
  K 7 T off a hook); constants holding NEXTREG 7,x need the machine's own figure (cw_cal).
- [local: Inferno IRQ anchoring] Hooks shift the game, so a wall-time IRQ meets other instructions;
  compare against the original IRQ at the same game instruction (RZX semantics) where code reads R.
- [card patch.timed-side-effect-replay §Use / do not use] A replay cannot follow the code that produces it when the first
  event is due sooner than that code takes: interleave (lockstep); defer only what the tail can't fit.
- [local: Inferno IRQ in a timed window] The IM2 JR at FFFF reads its offset from 0000: the slot-0
  page owns the IRQ; count the original's no-op ISR (T, M1) rather than lose it under DI.
- [card detect.pacing-structure §Use / do not use] Find where the frame is paced before setting a hook budget; here the
  limiter is inside the copier, which also plays the beeper. Prove immutability on full recordings.
- [local: Inferno runtime attribution] Keep per-update totals; row span proofs cut bounds checks,
  never byte equality; repeated streams do not authorize reuse across draws.
- [local: Inferno initialization pause] 86C5 is an overwritten decompressor; 8EF9 DI/IM1 permits a
  private pause with exact R/clock restoration; not proof of timed continuous loading.
- [local: Inferno owned cache] Append whole streams in 136–215, publish valid last, validate live
  bytes; dispatch is a candidate; no reset with current/pending owners.
- [local: Inferno immutable sources] Loading-time preparation removes sampled cold construction;
  exact validation exceeded the (void) 10 ms target.
- [local: Inferno B fill] Bitset connectivity preserves whole-image fill; a bounded call is no
  cold-latency proof.
- [local: Inferno blitter] Physical SRAM includes 040000 aperture offset; high staging is 216–223.
  Tiny copies prefer CPU. Charge stalls separately; protect current AND pending pairs/allocations.
- [local: Inferno cold actor construction] First-use work exceeds 10 ms: prewarm live snapshots.
- [local: Inferno frame pipeline] Post-copy restoration/shop cancellation pass; FLASH/modal open.
- [local: Inferno representation] One-bit expansion cuts sampled scenery 130.069 to 6.547 ms.
- [local: Inferno validation loops] Aligned flags/unrolled compares save 13% on unchanged L6 scenery.
- [local: Inferno scenery budget] Validate distinct sources once; keep failed total gates.
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
- [local: Inferno continuation input] Beeper 7C37 consumes R; count inputs, guard dead stack reads.
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
- [card patch.work-in-timed-gaps §Failure lookup] A 64-slot scan per new pattern cost 2.5k T and doubled drops; a recency list fixed it. Measure cold frames.
- [card patch.whole-altrom-image §Recognise] The intro uses IM 2 with I = 3B: ROM 3BFF-3C00 is its vector. Hooks must leave them FF; JNext headless found it.
- [card patch.work-in-timed-gaps §Failure lookup] Busy L1 windows are nearly full: per-chunk cost, not cold frames, set the run length. Profile before planning. Store cache keys must cover all code they hold.
- [local: Inferno startup] L1 map is write-first, permitting plain tail 9A80. Later lifetime is separate.

## Friction
- retries: [local: Inferno timing reconciliation] Require one timing row per completed hook and
  reconcile component sums; an empty timing list must not look like successful profiling.
- environment: [local: Inferno Windows checkout] JNext 1.2.0 headless runs here (user's copy); doccheck
  counts CRLF bytes unless core.autocrlf is false.
- reuse: [local: Inferno shared DMA] Upstream DMA library/model/selfchecks reused; data in specnext.
- reuse: [tool tools/probes/rzx_census.py] Extended the existing census with bounded point captures;
  no parallel game tracer. Existing flags/output are preserved when capture is not requested.
- retries: [tool nexclash/inferno.py] Pulse emulation caught canonical EAR state; complete IRQ
  tracing caught the truncated ISR test. Actor hooks now replace one complete lookup instruction.
- hand-rolled: [local: Inferno verification] Uses SkoolKit's original ROM/pulse loader and native
  RZX source; per-engine hook/log/model comparisons remain in the engine, not a parallel toolkit.
- scratch: [local: Inferno probes] Checks/builds stay in inferno.py; one-off probes (pacing, OUT,
  window timeline) live in specnext build/copier_window/, edit scripts stay local.

## Technique use
- optimise.pattern-cache: helped: 128-slot protected store, recency list; uploads reject current/pending owners.
- detect.routine-removal: helped: the copier skip replay settled what gameplay needs (build/hybrid.md).
- detect.pacing-structure: helped: the pacing census found the limiter inside the copier.
- patch.hybrid-display-replacement: used: tilemap + sprites, write-out replaced, modal_exit hides layers.
- patch.timed-side-effect-replay: used: copier window head, beeper OUTs at original T.
- patch.work-in-timed-gaps: used: cw_wait coroutine, unfinished work dropped.
- patch.display-atomic-switch: helped: one Copper commit at line 224 ended the ghosting (hardware, by eye).
- verify.model-reconstruction: used: quick tile/ULA closure, dropped-writer and incorrect-coordinate controls.
- detect.buffer-layout-producer: helped: followed the 0x9790 copier to its tile map and source tables.
- detect.tracked-unit: helped: the screen-copy routine is not a figure; producers remain to classify.
- patch.scratch-redirect: no help: original tile writes carry collision ownership and must run unchanged.
- tools/probes/rzx_census.py: helped: full-recording producer/call-site counts without a new tracer.
- detect.drawing-parameters: helped: captured IX/IY and live run lists distinguish whole actors from tiles.
- detect.buffer-layout-producer: corrected: visible colour checks distinguish black-masked stale bitmap data.

## Stage log
Moved to [inferno_stage_log.md](inferno_stage_log.md); new entries go at its top.
