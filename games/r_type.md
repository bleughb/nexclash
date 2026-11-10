# R-Type (128K) - intake

## Next session
Stage: 1 (feasibility), design approved; dynamic preparation and early whole-copier
integration measured. This is NOT the R-Type engine or a hardware-ready sprite build.
Branch: add-r-type in both repos. Started from nexclash0fba3b9; refreshed/merged main
at dace0cc (Movie-only incoming changes), specnext main already included.
Inputs: ../specnext/reference/r_type/Rtype.{z80,rzx,tap}; hashes below.
No pending design answers. Do not repeat intake, caller/capacity or full ISR/access scans.
Read: CLAUDE.md, PLAYBOOK3d/6, Feasibility below, then
../specnext/reference/r_type/intake/README.md (Dynamic preparation and early integration).
Reference evidence commit: specnexte6d7a1f.
Draft PRs: https://github.com/bleughb/nexclash/pull/235 and
https://github.com/bleughb/specnext/pull/93. Latest evidence lives on these branches.

Completed this continuation: actual ZX-to4bpp preparation (23 and105 sprites), both DMA
publication modes, four runtime corruption controls; early integrated converter/copier;
100-return ABI/tail/source checks in each mode;24 isolated register/R bridge cases;
100-update natural-play pace penalty0.82% (worst20-update window1.72%). Details below.
No full recording sprite verify, state lockstep, new hardware result or release stamp.
No engine/profile/registry entry/record/colour sheets have been created.

First next gate: supplied-R equivalence for BEDB/BF36 IRQ consumers during prep, complete
banked RAM and stack convergence/instruction-level IRQ proof, and observed105-sprite
scene INTEGRATED pace (only component timing was measured there). Then wire the measured
per-plot text classifier (the current prototype table stays empty), source paper handling,
and entry-IFF0 support before promoting the experiment into the additive engine.
Do not treat the passing isolated R bridge as an in-IRQ R proof. Diagnostic sources:
publication_dynamic.asm/.py, publication_integrated.asm/.py, integrated_check.py,
register_bridge.py in specnext/reference/r_type/intake. Worst-state capture helper:
refresh_capture.py; replays only to the already-known peak, and only if its fixture is absent.

Setup: /workspace/work/{nexclash,specnext}; /workspace/work/venv101/bin/python
(SkoolKit10.1, Pillow13); only bundled pinned sjasmplus. JNext1.2.0 executable:
/workspace/work/jnext-bin/root/usr/bin/jnext; isolated home /workspace/work/r_type_jnext_home.
Private read-only card /workspace/scratch/cspect-next-2gb.img, outside BOTH repos.
On workspace replacement recover owner ZIP Sediment ID file_0000000073c0820ba21cc0b36230394a
and extract privately. Never commit/publish it or JNS captures containing its metadata.
Generated game snapshots/NEX/JNS/raw logs stay under /workspace/work; compact results
and reproducible per-game experiments are in specnext. Diagnostic MD5 a300a51515aa39534e3047ef18e16db9.

Reproduce checks from nexclash using ../venv101/bin/python followed by
../specnext/reference/r_type/intake/{refresh_capture,publication_dynamic,register_bridge,integrated_check}.py;
README gives the peak-state argument and exact scope. Integrated fixture:
/workspace/work/r_type_integrated/play.z80; diagnostic.nex in that same folder.
Set NEXCLASH_JNEXT to the executable above; shared pace command uses --original play.z80
--probe 0x8649 --updates 100 --max-frames 1500 --card <private-card> --jnext-home <isolated-home>.
Prior synthetic CPU route remains rejected; no-blitter means ordinary DMA. Core3.03 DDMA
is untested. NR64=0, NL311; retain shadow through prep IRQs, tail copy at150, publish160,
restore MMU6/speed/IFF before247. Guarded clone entry is below210 or from249; component
probe still uses fixed170. No accepted IRQ occurred in measured clone/publication intervals.

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
Visual design approved; no architecture selected. Required next: caller/text classification,
whole-hook timing budget and DMA/DDMA ownership/fallback evaluation (docs/DDMA.md).
The shared routine_skip probe supports only 48K, so it cannot establish removal safety here.
Preliminary pacing census on frames 2000-2500: 150 updates; 113 take 3 frames, 26 take 4,
11 take 5; median 205,413 T, maximum 360,652 T (uncontended). Wait at 868C polls 7A8A
until >=3; main loop 8649 resets it. Measured slack on 47 waits: min 333 T, median 26,797 T.
The probe reports beeper writes at FAA2 and FB52. These are NOT a whole-game hook budget.
Removal (`intake/removal.py`): 35 live copier states sampled every 2,500 frames through 87,444.
Clear selected source pixels/paper, run original 8842, restore temporary sources: all registers
including R, non-ULA RAM and the predicted clean ULA agree exactly. This proves the sampled algorithm
without interrupts, not an assembled hook. Nonlinear pixels occupy 6000..6FFF plus the low 128 bytes
of each page 7000..7700; never restore 6000..77FF wholesale (gaps hold variables such as 71D0).

First screen-aligned 16x16 proposal: 126 sprites, so a 64-pattern split buffer fails; protected
old+new patterns peak at 221 (canonical review: 219), above 128. PLAYBOOK 3d review requested;
owner explicitly authorized one reviewer. The worst frame is THANK-YOU text plus flying figures.
Text belongs on ULA: owner 1..DB alone misclassifies it. Owner88 is text here but normal enemies
elsewhere: never exclude that owner globally. Text plot: 8CFD from917A, HL=CAFF, D=21,E=24,
frame32 resolved by8E85, C4BA=D99C. Corrected full census:105 sprites,103 simultaneous patterns,
183 old+new patterns (screen grid);400 text draws identified. Owner-min111/104/176 and
owner-best108/101/174 do not fix protected capacity. The review recommends single-bank publication
outside the160-line play area. Old+new coexistence is an implementation choice, not a user requirement.
Staged publication experiment now runs the original copier into a shadow slot2 before publication.
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

Dynamic continuation (component + early integrated diagnostic, 2026-11-10):
- Real source pixels generate23 sprites at captured native IRQ state3620 and105 at the
  previously measured peak29405. Per-bit host oracle matches every active packed pattern
  and attribute; default/no-blitter publish in5.084/5.100ms with no row deadline failures.
  Preparation includes IRQs:47.687/71.758ms. No105-scene integrated pace claim.
- Two ordinary-DMA zero fills replace blank-cell CPU writes;23-state prep improved from
  66.915 to47.687ms. The guarded whole-hook clone entry removes the fixed170 wait:
  100-update penalty9.80% ->0.82%, worst20-update window1.72%. Both original/diagnostic
  15.83updates/s,49.83IRQ/s, longest IRQ gap40.5ms; no gameplay state lockstep.
- Runtime negatives: corrupt LUT813/5392 packed bytes; omit foreground clear328/1887
  ULA bytes; omit tail or restore source holes wholesale each loses one forced sentinel.
  Expected source-hole state includes IRQs through the publication wait.
- Integrated100 returns per mode:12 copier-output register fields exact; SP/MMU6/IFF
  restored;34048 RAM bytes identical from tail to return;0 accepted IRQ in measured
  clone/publication intervals. Broken IY restore caught100 times. Max observed hook64.42ms,
  publication interval101.31ms; no dropped copier return in this sample. Private SP minimum
  3CE4 on positive runs, not an instruction-level interrupt-headroom proof.
- The real copier's M1 span repairs return R.24 isolated bridge cases (both captured
  states, six R seeds with bit7, positive and wrong-R controls) compare all caller registers
  exactly, IRQ excluded. BEDB/BF36 supplied-R/consumer proof remains open. The integration RAM check
  excludes C000..DFFF and does not establish original-vs-hook IRQ effects before the tail.
- Shared converter/compact tail boots the diagnostic; MD5 a300a51515aa39534e3047ef18e16db9.
  Text hooks, source paper handling, entry-IFF0 support, full banked RAM/stack/IRQ proof,
  worst-scene integrated pace, colour/recolour and final engine remain open. No delivery claim.
Evidence: specnext/reference/r_type/intake/{publication_dynamic-timing,publication_peak-timing,
integrated-check,register-bridge,integrated-pace,integrated-summary}.json and README recipes.

## Checks
- Continuation: dynamic component/negative controls, integrated100-return checks and isolated
  register/R bridge PASS;100-update pace0.82%. No shared runtime code changed; prior
  canary/tools results below are retained, not rerun. Doccheck PASS (148 docs).
- `selftest.py --canary`: PASS, both Chuckie Egg rebuild checksums unchanged.
- `selftest.py --tools`: new entry-CALL regression PASS; existing Chuckie survey golden PASS;
  overall FAIL on the unchanged Inferno IFF audit (asm/inferno_hooks.asm lines 5722, 5726, 7563).
  Neither that source nor hooklib.py differs from the session base. No other game was modified.
- `tools/doccheck.py`: PASS (147 docs; existing warning about a split module name in another game's notes).
- Full recordings replayed by both caller censuses: 90,102 frames each, no desync.

## Hardware checklist
Plain above: owner reports JNext and real hardware PASS (2026-11-10); issue/core versions and
individual checklist items were not supplied. Sprite pace, music, controls,
level transitions, death/restart and display
checks belong to the eventual sprite build; no hardware result is claimed.

## Technique use
- optimise.pattern-cache: no help: temporal protected union exceeds128; dynamic preparation uses the staged single-bank protocol; no cache claim.
- patch.display-atomic-switch: helped: checks require complete old/new pictures; single-bank publication remains a measured alternative outside the play area.
- patch.preserve-r: used: actual copier M1 span repairs return R; isolated assembled bridge passes, IRQ consumers remain a separate proof.
- detect.pacing-structure: used: preliminary census locates the three-interrupt wait and beeper writers.
- detect.routine-removal: helped: identifies the required dependency experiment; existing probe is 48K only.
- detect.buffer-layout-producer: helped: separated final copier, nonlinear source cells and non-pixel holes.

## Lessons
- [local: clone entry phase] Observed: fixed170 entry waiting adds9.80% integrated pace cost; guarding clone below210/from249 yields0.82% over100 updates. Worst-scene integrated pace remains open.
- [local: empty pattern quadrants] Demonstrated: ordinary-DMA zero fill avoids per-cell blank writes; live23-sprite preparation47.687ms including native IRQs, down from66.915ms.105-sprite component also passes.
- [local: source-hole oracle] Demonstrated: post-IRQ sentinel expectations must count IRQs through the wait to the tail transition; broad restoration loses the sentinel and the negative fails.
- [doc docs/CHECKS.md §Setup] Observed in JNext1.2.0: execute-triggered JNS requests save at a frame boundary. Exact hook ABI/RAM tests use execute-time logs/dump_mem instead.
- [tool nexclash.isrinfo] Expose data-read/write address sets in the API, retaining text output;
  this distinguishes safe pixel scratch from ISR-mutated attributes and shadow-slot variables.
- [local: publication timing] A native beeper IRQ breaks an otherwise passing CPU row schedule.
  Move the actual copier before publication; batch sprite attrs via ordinary DMA and copy all
  shadowed non-display state before the IRQ-free visible upload. Whole-hook pace remains unproven.
- [tool nexclash.survey] Observed: a CALL as a routine's first instruction was never tracked;
  R-Type 8979 -> 8842 exposed the false coverage gap. Removed the early return and added a golden check.
- [local: tile plotters] Observed: screen-writer ranking identifies the refresh, not the figure
  plotters; scanning its source buffer locates the four tile drawers. No removal-safety claim yet.
- [local: credits share an enemy slot] Independent review: peak owner-grid scene includes THANK-YOU
  text. Graphic identity, not global owner exclusion, gives105 sprites in the full corrected census.

## Friction
- reuse: [none: existing survey, scan, preview and census tools provided the investigation paths]
- retries: [local: boundary oracle] Fixed the post-IRQ source-hole oracle to include the publication wait; return-R counts include both M1 fetches of LD SP,(nn). Earlier survey entry-CALL regression remains fixed.
- environment: [local: resumed workspace] Recovered both branch tips, pinned SkoolKit10.1 and JNext1.2.0; owner SD upload extracted read-only outside Git. SkoolKit10.2 callback incompatibility remains avoided.
- hand-rolled: [none: disassembly used sna2skool; screen images used the existing preview renderer]
- scratch: [local: per-game feasibility evidence] Game-specific experiments kept beside the inputs
  in specnext/reference/r_type/intake; none added as an untested shared toolkit probe.

## Stage log
- 2026-11-10 Stage1 continued (~30min, ~100 tool calls,0 user rounds): refreshed main dace0cc;
  live23/105-pattern DMA probes and controls pass; early integrated100-return checks and
  isolated R bridge pass;100-update pace0.82%. In-IRQ R, complete RAM/stack proof and
  worst-scene integrated pace remain open; no full scans repeated or hardware build delivered.
- 2026-11-10 Stage1 handoff: owner requested a fresh agent for cost efficiency. Branches and
  prototypes pushed; this Next session block is the single current handoff. No pending design
  question; remaining gates are dynamic preparation, integrated equivalence and pace.
- 2026-11-10 Stage1 continued: owner SD ZIP extracted privately/read-only; JNext original/plain
  pace measured. Full ISR scan completed. Synthetic CPU route rejected with native audio;
  staged shadow-copier/default+no-blitter publication passes byte/deadline and omission controls.
  Dynamic preparation, R/stack equivalence and integrated pace still gate stage2. No sprite build.
- 2026-11-10 Stage 0: ~13 min wall, ~65 tool calls, one design round pending. Source refreshed
  at 931458b; original attachments preserved, snapshot extracted, full screen replay and
  caller censuses, bounded surveys, tracker fixed and regression checked. No sprite build yet.
- 2026-11-10 Stage 1 in progress: owner approved all effects, see-through, no outlines; authorized
  one capacity reviewer. Full access scan and plain NEXLOAD boot/negative proof pass.
- 2026-11-10 Stage 1 checkpoint: owner confirms plain in JNext and on hardware; corrected full
  capacity census retained. Cloud publication timing blocked on unavailable NextZXOS card (policy403).
  Full ISR scan interrupted during session pause; no completed result claimed. No sprite build delivered.
