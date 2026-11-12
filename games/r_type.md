# R-Type (128K) - intake

## Next session
Stage: 1 (feasibility), design approved; continue implementation without a new design round.
Branch: add-r-type in both repos; main f92662e, no incoming changes.
Inputs: ../specnext/reference/r_type/Rtype.{z80,rzx,tap}. Do not repeat completed intake,
caller/capacity or full ISR/access scans. No engine/profile/registry/record/sheets yet.
Draft PRs: https://github.com/bleughb/nexclash/pull/235 and
https://github.com/bleughb/specnext/pull/93. Current sources/results are on these branches.
Read CLAUDE.md, PLAYBOOK3d/6, the continuation below and the reference intake README.

Native1bpp text-tile baseline: peak1.32% (worst20 2.27%); scoped RGB/RAM/R/IRQ/pause
proofs below. ULA scenery/HUD/text; bank7 art relocates to24. No live painted route,
hardware-ready build or full-recording verification.

Completion directions: reference intake/continuation/completion-review.md.
Cached IDs pass320 ABI/R/RAM/credit and15 signed cases; old peak fails10.75%.
publication_inlined.asm is unfinished WIP with placeholder costs; never deliver it.

Latest: reference intake/continuation/live-budget-review.md and live-budget.json.
Fresh peak9cfed755/no-input sample: original10.516s, static10.652s (+1.29%),
cached IDs11.665s (+10.925%, FAIL); needs9.386ms/update savings. Different fixture
from old10.75% test. Markers preserve101 clocks/380 bytes;378 match across routes,
IRQ wait/star counters differ. Known SMC writes match; no watched hook/art writes.
Legacy clone/clear/copier/paper costs14.176ms; identity checks/bridge9.961ms.
Actual pixel scroll0.984ms supersedes nominal0.61ms estimate. No new renderer.

Latest consumer proof: reference intake/continuation/background-consumer-review.md.
7E00 owner/8100 dirty maps are IRQ-read; independent BG stream atC4BC identified.
24 native initializations match across eight levels. Actual flip table01->00
exposes painted compiler mismatch; RGB still unproven. Initial BG uses live plotters
with SMC destination/clip modes. Next price retained semantics/native-time/R credit,
BG progression and fallback before one bounded combined experiment. Gross14.176ms
is not spare time; no further per-cell tuning/new backends by default.
Require LIVE painted peak<=2%, ABI/R/IRQ/RGB, stale-source/ownership and pause/menu/DI
before engine, sheets/recolour, quick checks and final full verify. No new intake scans.

Setup: /workspace/work/{nexclash,specnext}; /workspace/work/venv101/bin/python
(SkoolKit10.1, Pillow13); bundled pinned sjasmplus only. JNext1.2.0 executable:
/workspace/work/jnext-bin/root/usr/bin/jnext; isolated home /workspace/work/r_type_jnext_home.
Private card /workspace/scratch/cspect-next-2gb.img mode444, outside BOTH Git repos;
every emulator run uses --sdcard-readonly. Never commit it or JNS card metadata.
SD and JNext1.2.0 restored here. Generated files and isolated home stay in work.
Reference scripts reconstruct cached fixtures only when absent; README gives commands.

## Inputs
The attached TAP is a tape, not a snapshot. The build start state was extracted from the
attached RZX with `nexclash.py rzx extract`, as MAINTAIN specifies. Originals and derived
game files stay in specnext, never this repository.

| File | Bytes | MD5 |
|---|---|---|
| Rtype.tap | 132823 | 2d1e17efa08a303dc4bb783278f8cfd9 |
| Rtype.rzx | 320136 | fb4a142aa9fee684dfbfd7650d6b22bf |
| Rtype.z80 | 111966 | 5a2179b4006d7888a1f7f821a4316bf5 |

## Facts and evidence
- Observed: 128K snapshot, PC BE24, SP FFF6, IM 2, I=84, interrupts disabled;
  7FFD=10 (ROM 1, bank 0), technical-specification screen. No existing engine recognises it.
- Observed: one RZX segment, no autosave snapshots, 90,102 frames (30:02.04 at 50 Hz).
  Full C-simulator screen/caller replay completed without desync. Contact sheet samples
  frames 1, 500, 2000, 5000, 10000, 20000, 30000, 40000, 50000, 60000, 75000, 90000;
  later levels and a return to the level-1 loading sequence are visible.
- Observed in the first 2,001 frames: screen refresh 8842 copies/clears dirty cells from
  a buffer at screen address +2000 and shifts selected screen spans. 8979 calls it at entry.
  BE97 draws the stars; C084 prints text. FDEF clears memory, not a figure plotter.
- Observed in original frames 2000-2500: buffer scan flags 8D2F..8D4B and 8E06/8E0F;
  disassembly identifies four cell plotters, 8CFD / 8D65 / 8DD3 / 8E29, with flip variants.
  The shared 8EC2 path also performs collision-related cell checks; 8EA2 changes cell maps.
  Removing original plotter effects has NOT been proven safe.
- Observed: full caller census reaches 8979 18,202 times and 8842 18,576 times;
  C290 (the level-transition caller) eight times. The initial survey falsely marked the
  CALL at 8979 unreached: its tracker skipped CALLs at routine entry. The tracker is fixed.
- Plain: Rtype.nex, MD5 657362a108b54e5080cb88ccf2dcfdc6, 147,968 bytes; tail 5B00..5B4E.
  `intake/plain.py` restores printer data in the stub before copying the tail. Rainbow's 128K
  checker and nextboot pass with/without NEXLOAD, including a separate R check. Removing restoration
  from the built stub catches 176 RAM differences (5B4F onward). Owner reports this supplied plain
  build working in JNext and on real hardware, 2026-11-10. No sprite build yet.
- Full access scan: 90,102 frames; ROM 1F00..3FFF never accessed; printer spans 5B00..5B63 and
  5C4C..5CAF never accessed. Tail 5B00..5B4E fits. Full ISR proof below.

## Coverage
Full C-simulator census: 90,102 frames, no desync, all 17 static CALL candidates to the
four figure plotters reached. Initial-only gaps A540, 9183 and 9A11 are covered by later play.
This establishes observed caller coverage, not an assertion that every game branch was visited.
Banked high-address PC counts do not distinguish code images; hook-site byte validation remains required.

| Plotter | Calls | Static caller candidates (all reached) |
|---|---|---|
| 8CFD | 328871 | 917A, 959A, 9A01, 9A9D, A540, C3A9, C443, F591, F6D9, FF52 |
| 8D65 | 17323 | 9183, 9A11 |
| 8DD3 | 30591 | 918C, 959F, 9A09 |
| 8E29 | 9147 | 9191, 9A19 |

The corrected bounded survey covers the first 2,501 frames; the buffer scan covers 500
original frames from 2000. The full survey started with the old tracker was cancelled when
its defect was found; a separate full-recording access scan subsequently completed (Facts above).
921E / 9227 / 9230 call the memory clearer, not a figure plotter; none runs in the full RZX.
The corresponding clear sequence needs a later unit test; it is not missing figure coverage.

## Design approval (2026-11-10)
Approved together: every figure (ship, Force, enemies, bosses); scenery/HUD/text on ULA;
original depth and pace; original inks until painted; added graphics off for menus/pause.
Explicit answer: all effects as sprites, see-through figures, no outlines.
The original-recording contact sheet is the intake preview, not a simulation of a sprite build.

## Feasibility
Historical feasibility below; current directions are in Next session. The shared
routine_skip probe is48K-only and cannot establish removal safety here.
Preliminary pacing census on frames 2000-2500: 150 updates; 113 take 3 frames, 26 take 4,
11 take 5; median 205,413 T, maximum 360,652 T (uncontended). Wait at 868C polls 7A8A
until >=3; main loop 8649 resets it. Measured slack on 47 waits: min 333 T, median 26,797 T.
The probe reports beeper writes at FAA2 and FB52. These are NOT a whole-game hook budget.
Removal (`intake/removal.py`): 35 live copier states sampled every 2,500 frames through 87,444.
Clear selected source pixels/paper, run original 8842, restore temporary sources: all registers
including R, non-ULA RAM and the predicted clean ULA agree exactly. This proves the sampled algorithm
without interrupts, not an assembled hook. Nonlinear pixels occupy 6000..6FFF plus the low 128 bytes
of each page 7000..7700; never restore 6000..77FF wholesale (gaps hold variables such as 71D0).

Initial protected old+new proposal exceeds128 patterns; corrected census after400
THANK-YOU text draws:105 sprites/103 simultaneous patterns/183 protected patterns.
See intake/review/REVIEW.md for earlier counts/packing alternatives. Never exclude
owner88 globally: it also draws enemies. Text identity:8CFD from917A, HL=CAFF,
D=21,E=24, frame32 via8E85/C4BA=D99C. The approved reviewer recommends single-bank
publication outside160 play lines; old+new coexistence is not a user requirement.
Staged publication runs the original copier into shadow slot2 first.
The full ISR scan completed:90,102 frames,86,553 interrupts,0 unreturned;478 instructions,
26-byte interrupted-stack depth; slots1/6 untouched. R reads at BEDB/BF36 require care.
No ISR reads/writes the actual5120 source pixels. It writes588 source attributes at7820..7A7D:
never blanket-save/restore those. Crucially slot2 also contains live non-display variables:
ISR reads314/writes157 addresses in5B64..5D01, so shadowing slot2 requires their copy-back.

Baseline gameplay fixture at RZX frame2000:100 updates,15.83updates/s in original and plain,
penalty-0.04%; IRQ49.83/s; longest original IRQ gap40.5ms. No state lockstep assertion.
A bounded4000-frame ISR capture finds70,819 native T at frame3620. JNext native IRQ samples
include21.19ms; this is not a full-game maximum. Raw evidence stays with the reference inputs.

`intake/publication_irq.py`:105 prepared4bpp patterns +5120 ULA pixels +640 attrs +525 sprite
attribute bytes. Ordinary DMA5.556ms passes; CPU-only35.150ms with a native20.267ms IRQ misses
rows2..9 (without IRQ CPU14.771ms passed row deadlines). Reject CPU-only for this architecture.
No-blitter means ordinary DMA, so it is not rejected. Unsupported DMA configurations must be
refused explicitly; never silently drop figures. Core3.03 DDMA is not exercised by JNext's older core.

`intake/publication_shadow.py`: actual copier, temporary foreground pixel clearing, exact pixel
restoration, shadow slot2 retained during a native~20.27ms IRQ. At NR150 DI, map live slot2 and
copy its1280 non-display bytes from shadow; at NR160 publish patterns/clean ULA/attributes.
Ordinary DMA attribute batching reduces the visible publication to5.100ms (default preference
falls back to ordinary DMA:5.084ms); tail-copy lead0.640ms; preparation31.057ms includes the IRQ.
The next native IRQ starts about0.63ms after publication ends. All actual5120 source pixels,
non-pixel source holes, ULA5120+640,1280 tail bytes, unchanged HUD and105 pattern images match.
A forced sentinel at the proven ISR-written5B64 exercises tail propagation; removing only the
runtime tail copy catches that lost byte. This is one synthetic-pattern/captured-game state,
not an integrated engine, full-hook pace proof or full RZX sprite verification.
Next gate: dynamic ZX-to4bpp preparation + register/R/stack proof + full-hook timing and pace.
The prepared-shadow protocol avoids retaining old+new patterns concurrently.
Detailed evidence: specnext/reference/r_type/intake/review/REVIEW.md and packing-text-classified.json.

DMA/DDMA remains an evaluation, not a selected route: the four plotters copy 8-pixel cell
graphics and update collision maps; DDMA cannot generate those maps or unpack ZX bits.
Evaluate cached sprite uploads with ordinary DMA and eligible rectangle work with gated DDMA,
using the shared policies (including no-blitter and CPU fallback), during integration; ordinary DMA is the measured no-blitter fallback.

Earlier dynamic/bridge results remain in reference intake README; the complete bank/IRQ
checks below supersede early scopes. Quiet0.82% pace does not replace peak acceptance.

### Integrated native-tile continuation (2026-11-10)
- `publication_tilemap.asm`: 40x32 hardware text map,511 foreground8-byte glyphs,
  map/definitions7168 bytes via ordinary DMA. Observed105 occupied16x16 blocks imply
  at most420 occupied8x8 cells. Standard4bpp tile definitions were too small at the
  measured274 binary patterns (263 after flip normalisation). No hardware claim.
- `tilemap_bank_check.py`:80 bank/edge/R cases; full paging-port census confirms all
  bank7 reads use8F21. Original assets move to physical bank24, MMU0 aliases48/49.
- `irq_equivalence.py`:218 supplied-R reads across14 native IRQ states,14 wrong-R
  controls caught. Wrapper retains selected NextReg, MMU0/clock; body runs native.
- `copier_equivalence.py`: all caller registers/R, eight logical game banks and
  clean ULA/pixels exact in23/105-sprite states.18 dead stack bytes converge before
  any read through the real caller and first normal IRQ. `interrupt_boundaries.py`:
  113543 injections,841 PCs; wrong-MMU negative caught, private SP minimum3CD6.
- `text_check.py`:80 identity/ABI/R cases; `tilemap_geometry.py`: empty/edge/all-ink,
  511-glyph capacity and512 overflow, broken actual bound caught. `tilemap_preview.py`:
  all49152 paper RGB pixels match independently; one runtime glyph-bit error caught.
- `integrated_check.py --asm publication_tilemap.asm`:100returns in each mode, all
  checked registers and42240 RAM bytes exact;100 wrong-IY negatives. Peak pace1.32%
  over100updates,2.27% worst20 window, state equality each update,50Hz IRQs both.
- `pause_check.py` checks actual converter CALL bytes,12 ABI/R/ULA cases; holding
  pause must save/fold only once. `pause_jnext.py`:261 pause calls, one resume,
  added layer off/on and DI native continuation correct. Future source may already
  describe the next frame, so pause folds the last published glyphs/attributes.
- Owner approved one independent reviewer after two pace failures. Review found the
  builder's pause JP/CALL mismatch (fixed) and rejected broad producer credit:
  new overhead was multiplied as original work. Retained trial7.83% slow,13.37%
  worst20. Compact review and results are in reference intake/continuation/.
- `cell_check.py`:160 cell cases, all four legal continuations, force ink, R rollover;
  exact descriptor/source/flip/ink/owner/level, all caller registers/R/live banks.
  Credit equals measured original minus complete hook CPU, including its own cost;
  fractional scanline credit is retained across updates.64 whole-plot comparisons
  pass including DI fallback. Current prototype latches clock once per plot.
- Hardware alternatives: ordinary DMA already moves bulk state. DDMA stays gated
  to3.03 and untested on JNext's older core. Layer2 can replace whole painted cells;
  scrolling cannot replace the game's ownership/collision producers, and Copper
  scheduling does not remove colour-expansion work. Painted-route cost is still open.

### Live colour-path continuation (2026-11-11)
- The one approved reviewer also checked the colour bottleneck. Static all-painted
  Layer2 first-frame oracle:7369 painted pixels, all49152 RGB pixels exact, one
  corrupted runtime pixel caught. Whole-hook pace21.46%, unrolled17.17%, bounded
  debt polling11.81%: rejected as the current full-colour implementation.
- Static preexpanded4bpp comparison includes111-pattern publication. Per-block debt
  polling fixes missed timing-accounting wraps:15.56% ->1.52% over100 peak updates,
  all state samples/FE writes equal,50Hz IRQs. It is a cost trial, not live painting.
- Bulk ULA publication is being evaluated: the retained full ISR footprint writes
  no HUD pixels/attributes, so unchanged HUD bytes can accompany the whole8192-byte
  shadow in one DMA. Both publication modes100returns/42240 RAM bytes pass; measured
  IRQ-free intervals remain bounded. Hardware proof remains open.
- The source-only colour corpus captured385512 plots over90102 frames, no desync.
  Filtering yields8711 cell variants,1288 plots and1825 whole-figure views. Join
  parts only with an actual9-byte object and owner; shared low owner flags alone
  merge independent shots incorrectly. Individual other plots remain whole figures.
- Original bank1 unpacker reconstruction, with its persistent state across levels,
  reproduces all9789 captured raw cell variants at their actual source addresses
  from the supplied snapshot. No captured art needs embedding in engine code.
- Live guarded hash lookup finds17573/19017 foreground lookups in the peak sample
  but15.26% pace fails. A timer-IRQ checkpoint trial did not help (15.42%) and is
  disabled. Direct dispatch also failed15.26%; cached producer IDs failed10.75%;
  every current level/source/ink key has one bitmap in the recording. Native fallback
  for unknown/changed art remains necessary. Engine/final verify pending.

## Checks
- Live ledger/SMC:100 intervals each route; instrumentation/watch controls preserve101 clocks/380 bytes.378 match; two IRQ/star counters differ. Native SMC sequence matches, zero watched hook/art writes. No full RAM/RGB/sound proof; reference live-budget-review.md.
- Source follow-up:1288 plots/65030 mutations/16 CPU-M1 cases/352-image guard PASS; source-identity-review.md retains scopes. Earlier dynamic/bridge0.82% was quiet-only and is superseded by later peak gates.
- Earlier canary PASS; tools survey/golden PASS but unchanged Inferno IFF audit FAIL (asm/inferno_hooks.asm5722/5726/7563). No other game's code modified. Historical logs/results remain in reference intake.
- Full recordings replayed by both caller censuses: 90,102 frames each, no desync.

## Hardware checklist
Plain above: owner reports JNext and real hardware PASS (2026-11-10); issue/core versions and
individual checklist items were not supplied. Sprite pace, music, controls,
level transitions, death/restart and display
checks belong to the eventual sprite build; no hardware result is claimed.

## Technique use
- optimise.pattern-cache: no help: protected union exceeds128; immutability/invalidation warning reused, staged single-bank protocol retained.
- patch.display-atomic-switch: helped: checks require complete old/new pictures; single-bank publication remains a measured alternative outside the play area.
- patch.preserve-r: used: actual copier M1 span repairs return R; isolated assembled bridge passes, IRQ consumers remain a separate proof.
- detect.pacing-structure: used: preliminary census locates the three-interrupt wait and beeper writers.
- detect.routine-removal: helped: identifies the required dependency experiment; existing probe is 48K only.
- detect.buffer-layout-producer: helped: separated final copier, nonlinear source cells and non-pixel holes.

## Lessons
- [local: total budget first] Live costs14.176ms legacy display and9.961ms identity/bridge. Consumer/native-credit budget precedes replacement; gross CPU/waits are not free. See live-budget-review.md.
- [local: native code modes] Initial BG changes plot destination8EBF, RET condition8F10 and four clip operands; native flip table01->00 exposes compiler mismatch. Preserve live modes/table and original-time/R credit; see background-consumer-review.md.
- [local: packed source lifetime] Uniqueness is not immutability. Validate packed bytes/attributes/skip markers per invocation; unknown art/generation needs native fallback. Dispatch/invalidation remain open.
- [local: book comparison]96-byte SCROLL6 matches8914. Binary follow-up identifies owner/dirty maps with IRQ readers and independent BG stream;24 native initializations pass. Ingest labels alone were insufficient.
- [local: review of encoded pause sites] A test must inspect converter output: separately emitting the right CALL masked the builder's wrong JP. Actual-key testing also found repeated pause calls; save/fold once per pause.
- [local: timing credit includes its cost] Broad timer windows counted wrapper work as original producer time and regressed pace. Cell credit is checked against complete original/hook CPU costs; retain fractional units and remeasure natural play.
- [local: hardware text tile route] Native1bpp tiles remove ZX-to4bpp expansion while preserving exact visible colours; per-pixel painting still needs a separately measured override path.
- [local: clone entry phase] Fixed170 waiting added9.80%; guard below210/from249. Current peak pace is recorded above.
- [local: empty pattern quadrants] Demonstrated: ordinary-DMA zero fill avoids per-cell blank writes; live23-sprite preparation47.687ms including native IRQs, down from66.915ms.105-sprite component also passes.
- [local: source-hole oracle] Demonstrated: post-IRQ sentinel expectations must count IRQs through the wait to the tail transition; broad restoration loses the sentinel and the negative fails.
- [doc docs/CHECKS.md §Setup] Observed in JNext1.2.0: execute-triggered JNS requests save at a frame boundary. Exact hook ABI/RAM tests use execute-time logs/dump_mem instead.
- [tool nexclash.isrinfo] Expose data-read/write address sets in the API, retaining text output;
  this distinguishes safe pixel scratch from ISR-mutated attributes and shadow-slot variables.
- [local: publication timing] Native beeper IRQs break CPU row schedules; stage copier/ULA and non-display state before IRQ-free DMA publication.
- [tool nexclash.survey] Observed: a CALL as a routine's first instruction was never tracked;
  R-Type 8979 -> 8842 exposed the false coverage gap. Removed the early return and added a golden check.
- [local: tile plotters] Observed: screen-writer ranking identifies the refresh, not the figure
  plotters; scanning its source buffer locates the four tile drawers. No removal-safety claim yet.
- [local: credits share an enemy slot] Independent review: peak owner-grid scene includes THANK-YOU
  text. Graphic identity, not global owner exclusion, gives105 sprites in the full corrected census.

## Friction
- reuse: [none: existing survey, scan, preview and census tools provided the investigation paths]
- retries: [local: measurement boundaries] JNext can report an execute address again after IRQ; one-shot phase flags and nested-ledger negatives prevent double accounting. All101 clocks/380 bytes agree with uninstrumented controls. Earlier guard/stack and source-hole fixes retained in reference.
- environment: [local: remote continuation] SkoolKit10.1/Pillow13.0.0, official JNext1.2.0 and new owner SD restored read-only outside Git. Old peak/profile absent; new9cfed755 recipe is explicit, not an old-result reproduction. Main f92662e.
- hand-rolled: [none: disassembly used sna2skool; screen images used the existing preview renderer]
- scratch: [local: per-game feasibility evidence] Game-specific experiments kept beside the inputs
  in specnext/reference/r_type/intake; none added as an untested shared toolkit probe.

## Stage log
- 2026-11-11 Consumers: BG interface/SMC/native credit traced;24 initialization and8 flip cases expose compiler mismatch. No renderer or intake scans; price retained semantics next.
- 2026-11-11 Book (~5min/~8 calls/0 rounds): SCROLL6 matches8914; no PDF/scans/build.
- 2026-11-11 Stage1 live ledger (~3h/~50 calls/1 steering round): restored private SD/JNext; no new renderer. Exclusive100-update ledger, unchanged-clock controls and targeted native-SMC/art/hook watch pass. Fresh live pace fails10.925%; source/consumer and native-credit cut remains next. No intake scans or engine promotion.
- 2026-11-11 Stage1 (~45min/~100 calls/2 steering rounds): refreshed f92662e; read full decode/normalization/catalogue for provenance. Guard passes; whole-update ledger/Inferno correction saved in reference review. No intake scans/emulator/engine.
- 2026-11-11 Checkpoint/reassessment: cached-ID bounded test fails10.75%;320 producer and15 signed-budget cases pass. Existing knowledge remains main dace0cc; refresh deferred while checkpointing dirty experimental work. No new intake scans or renderer variants.
- 2026-11-10 Stage1 continued: approved reviewer; pause CALL/held-key fixed, native tile proofs/peak pace measured; successful-cell provenance/credit trial. Colour route/engine pending; no intake rerun.
- 2026-11-10 Stage1 (~30min/~100 calls/0 rounds): refreshed dace0cc;23/105 DMA, early100-return/R bridge pass; quiet pace0.82%. IRQ/RAM/stack/peak proofs pending then; no hardware build.
- 2026-11-10 Stage1 handoff: owner requested fresh agent; branches/prototypes pushed. Dynamic preparation/equivalence/pace pending then; design approved.
- 2026-11-10 Stage1 continued: SD extracted read-only; original/plain pace and full ISR scan complete. CPU route rejected; staged DMA publication/controls pass. Dynamic/R/stack/pace pending then; no sprite build.
- 2026-11-10 Stage 0: ~13 min wall, ~65 tool calls, one design round pending. Source refreshed
  at 931458b; original attachments preserved, snapshot extracted, full screen replay and
  caller censuses, bounded surveys, tracker fixed and regression checked. No sprite build yet.
- 2026-11-10 Stage 1 in progress: owner approved all effects, see-through, no outlines; authorized
  one capacity reviewer. Full access scan and plain NEXLOAD boot/negative proof pass.
- 2026-11-10 Stage1 checkpoint: owner confirms plain JNext/hardware; corrected capacity retained. Card policy403 blocked timing; ISR scan interrupted then. No sprite build.
