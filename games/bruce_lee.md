# Bruce Lee (U.S. Gold, 1985, 48K)

## Next session

Frozen release source 239f429 passed selftest --verify --stamp on 2026-11-10. Work from
release-20261108, not the historical attempt. Current main dace0cc is merged. The engine has
the normal auto entry, editable PNG import, unit tests, continuous display-composition proof
and evidence record. Source data stay external.

The unchanged C2EC dirty copier and C1F8..C216 room composer run inside shared hlib_pace
windows. The original ISR, game logic and sound remain unchanged at the caller's speed.
A private IM2 bridge allows interrupts during added work and restores the incoming speed/I.

Latest fix: CAC0 marks game over; the following native display commit hides figures. Room/title
entry clears the marker. Without it, stale descriptors left ghost figures after game over.
Default native game-over captures now match the original pixel for pixel; Enhanced keeps its
painted room. The hook's entry and unmapping exits are inside the hidden-ROM patch span.

The final 1.0 package passed all seven real-loader modes on disposable 26.11 cards and is ready
for packaging review. Preserve the documented randomized-key/global-R limitations. Do not
claim natural completion or hardware testing. The run's packaging handoff names exact artifacts.

Build needs the checked archive plus colour-source.256, source-palette.pal and BRUCE.scr beside it.
Set NEXCLASH_BRUCE_PAINTING to an optional folder of native editable PNGs. Existing sheets are
never overwritten. The public auto command supplies the default, Enhanced, loading and trainers.

## Inputs and ownership

- Archive Z80: MD5 6e088cc665d1cdbcd32effa061ad6e8e, genuine 48K release.
- Colour master: MD5 eba01279d6c7bf307a28b25782aa2083. Enhanced colours:
  Armando Quaranta (Spec256). The menu will say Enhanced, off by default.
- All 8192 figure graphics/mask bytes at A000..BFFF match the colour master's ninth
  plane. Other live state and some scenery attributes differ; never import its code.
- Original loading screen from the archive TAP: MD5 fd3cce1f2481373716de0fed62335674. Integrated and checked.
- Game files, recordings, colour data and generated builds stay outside this repository.
- Requested credits: patch by Jon Attree; NexClash / Dean Woodyatt (Bleugh.biz).

## Engine facts

The archive enters ROM PAUSE before the original E200 loader. The build runs the original
prefix to that boundary and restores the printer buffer, including the font at 5B00.
Both hidden ROM images are complete. Code/data own Next page 24; packed patterns use
pages 26..28, source scenery pages 30/31 and Layer2 pages 32..37. The startup tail stays below C000. Highest game bank 18; hidden ROM banks 46/47.

The original composer plots to E000..FAFF, then copies dirty rectangles to the ULA.
Commit C7D2 is after the three visible copies; C3CB is too early for a displayed position.
Room entry C16E and title entry C4BD hide all 12 hardware sprites. Each figure occupies four
16x16 parts, with original mask transparency and opaque black interior pixels. No added edge.
Ninja CB1C, Yamo CBBE and Bruce CCA5 each have 22 frames and two orientations. Actual player
update counting uses C82B after IX is loaded with CCA5, not the three-figure movement routine.

The candidate can NOP the three pixel stores and one figure-attribute store in the original
plotter. Its other calculations remain. Hardware sprites replace those writes over clean scenery.
C2AC commits full copies; C3CB records whether a figure has actually been plotted. A partial
copy that misses a newly positioned figure retains the previous visible sprite instead of hiding
it: the original ULA retains that image too. Room/title hooks reset the drawn state.

Enhanced scenery comes from 256 tiles at 9800..9FFF, byte-identical to the source colour master.
All 20 room descriptors use that table. Layer2 caches tile IDs and updates after C2B8 tile writes
and D636 lantern restoration. The original HUD remains on the ULA. Source colour 223 quantizes
to the default global transparency colour, so an unused colour key 1 is selected instead.
Native editable sheets: 132 figure images in 480x440 and 256 scenery tiles in 128x128. Import is lossless for untouched source pixels, has no blending, rejects partial alpha/overflow, and never overwrites a master.

## Checks so far

These are development checks, not a release proof:

- Exact E200 boot: every 48K RAM byte, registers including R, MMU and both hidden ROMs
  match through both simulated loader entry paths.
- First 1000 continuous replay frames: 564 hook events/R comparisons, zero differences.
- Hook ABI matrix: 192 cases, all four incoming speeds, both interrupt states and eight R
  boundary values. Wrong R, wrong MMU and fixed-speed exit controls are caught.
- Independent original C3CB plotter comparison: 792 frame/position/background combinations.
- Packed renderer: 792 figure comparisons per mode, including repeated cached frames and
  all 22 frames in both directions at three offsets. Exact source-palette pixel equality.
- Native JNext reaches play with Enhanced figures. No hardware claim.
- Three 300-player-update native trials from one original checkpoint: +0.0022%, +0.31%,
  effectively 0% total penalty, with matching game state at every update. Quiet/busy/window
  tables are retained in the run. This is limited scene coverage, not final pace acceptance.
- Longest interrupt gaps in those trials equal the original (20/39.9/20ms). The earlier
  whole-image uploader produced an extra 20ms gap and one divergent trial; keep that failure.

Latest additional checks (development evidence, not release acceptance):

- Clean-scenery composition: 6000 continuous frames, 21,685 events, 5,438 exact original bitmap
  comparisons, no differences. Eight dead-stack differences were individually proven overwritten
  before their next read, with interrupts included; no blanket stack exemption.
- Enhanced scenery: 6000 frames, 21,695 hook/R comparisons, 5,436 background screens and 11 changed
  tile maps, no differences. All 20 isolated original room layouts match 49,152 expected pixels.
  A deliberately omitted lantern notification is caught. Full room recolouring costs about 49ms
  in the model while the original room initializer has interrupts off; this is not hardware timing.
- Latest ABI matrix: 384 cases across six observed sites, no failures, wrong R/MMU/speed controls
  caught. C2B8 has not executed in this recording and still needs a dedicated matrix state.
- Latest native late-speed-restore trials, 300 updates each: total +0.342%, +0.419%, -0.002%;
  quiet +0.023%, +0.724%, -0.007%; busy +0.998%, +0.515%, about 0%. State matches at all 301 samples.
  Worst 20-update windows are +4.985%, +3.849%, about 0%. **Gate held:** maximum interrupt gaps
  39.9 vs 20ms and 59.9 vs 39.9ms in the first two trials; third remains 20ms.
- An earlier fast-wrapper candidate diverged at update 10 at CCB0 (input direction). Applying
  test input at C7A4 instead of C82B fixes that early difference, but a later trial diverges at 220.
  Preserve both logs; do not present shortened lockstep as a complete pace pass.
- Original archive lives alternative CA53 is valid; the primary addresses alter HUD instructions.
  Isolated translated trainers: infinite lives holds 1/4/10/99, no walking sound removes only the
  CEE9 routine's port write with registers/R equal, movement reload changes 10 to 30 dispatches in
  30 ticks. No-enemies call sites C7FA/C801 are verified, behaviour still pending. None are packaged.

The figures above describe historical candidates. Current development evidence:

- Private-stack interrupt bridge: 103 isolated cases and 3,263 instruction-boundary injections
  pass, including clock restoration, R contribution, game RAM and identical sprite/Layer2 output.
  Hardware-pushed return bytes are exempted only after individually proving write-before-read.
  Maximum added masked interval is 6.14us in the ideal-clock model, formerly 35.36us.
- Current 448-case ABI matrix and wrong R/MMU/speed controls pass. The full copier separately
  passed 384 branch/clock/IFF/R/row-carry cases before the private-stack-only change.
- Current 2000-frame replay: 10,795 hook/R comparisons, 1,547 background screens and 4 changed maps
  pass, including both complete hidden-ROM boot paths. Native 2104-hook trace, including 9 IRQs,
  has zero boundary-R errors. Native global R sequences can still differ through idle-loop and
  interrupt phase; do not describe them as globally identical.
- Current room 0 default/Enhanced three-seed300-update tests match all 301 tracked states.
  Overall penalty -0.0141..+0.1571%; quiet -0.0437..+0.2704%; busy -0.0305..+0.1987%;
  worst 20-update window +1.7151%. Actual original ISR and beeper writes remain at 3.5MHz;
  sound event values/order/update match, but several beep intervals differ by up to 2.86us.
- Room 1 randomized-key seed 2 differs first in the player's sampled input at update 10.
  Moving key events earlier gives the same failure; applying them at ISR keyboard entry moves
  it to update 13. These failed trials are retained, not valid pace comparisons. Seeds 5/11 reach
  all 301 tracked states. R-derived decisions also need longer coverage.
- Recorded room 0/1 entry through first player update: default +0.1403/+0.1708%; Enhanced
  +27.9899/+37.5070%. The full background repaint is a real remaining regression, not an
  interrupt-wrapper failure. No release timing pass is claimed.

Current shared hlib_iff, speed latch and hlib_pace are unmodified. I=23 selects the private
vector only while page 24 is mapped; original I and clock return before unmapping. The original
ISR runs on a reserved private stack and contributes its own R fetches. This release is 48K
beeper; no AY version is substituted.

The room-window candidate supersedes the preceding repaint timings:

- C1F8..C216 is copied byte-for-byte from the checked owner input to 2380; its absolute call
  still executes the original C2C0 tile routine. 704 tiles cost 423151T/52100M1. The four final
  CALL/PUSH stack bytes are reproduced exactly. Only display composition runs faster.
-64 room-window cases pass both modes, two recorded rooms, all four incoming clocks, both
  IFFs and R wrap edges. Exact game RAM/registers and 49152 colour pixels match. Native R
  delta is 4 in both rooms/all three modes. Layer2 remains hidden until the original full copy.
- Current 512-case ABI plus wrong R/MMU/speed controls, 3279 IRQ injection cases, and 2000-frame
  replay pass: 10798 hook/R comparisons, 1547 background screens, 4 changed maps, both boot paths.
- Native room 0/1 entry: default 213.757/212.887ms, Enhanced 213.782/212.827ms; original
  213.334/212.441ms. All four default/Enhanced entry captures are pixel-identical to the
  earlier slower candidate. No earlier reveal of the newly painted room.
- Two scenes, three held-input trials per scene, default and Enhanced: all 301 tracked states
  match in each of 12 runs. Quiet -0.0555..+0.0112%; busy -0.0100..+0.0216%; worst 20-update
  window +0.0924%. Held inputs avoid the key-transition sampling race; they do not erase the
  failed randomized-input evidence. Original ISR counts and sound events match in every run;
  one busy sound trial has 608 beeper writes and 350 interrupts. Idle room 1 still differs in
  some R-derived values despite matching tracked state; retain that finite-coverage limit.

## Feasibility

The game waits on an ISR-updated flag but still runs asynchronous keyboard debouncing and
R-based enemy decisions. Extra idle-loop iterations can change global R even when every hook
preserves its displaced fetch count. Drawing replaces only display writes; source logic remains.
The unchanged C2EC copier provides a measured original-time window for ordinary hook cost.
Shortening DI and then using a private IRQ stack closed injected register/R/stack failures.
Full-room repaint alone failed the timing budget. Accelerating the unchanged C1F8..C216
composer provides 120.9ms of original work; painting and padding inside that window brings
the two native room entries within 0.21%, with exact scope effects and entry pictures.

## DMA evaluation

Read docs/DDMA.md and DDMA_IMPLEMENTATION.md. Removing uploads is the first measured step:
116 packed parts stay resident and 12 spare parts are owned by the 12 active sprite pieces.
Packed default uses 150 unique patterns; Enhanced 157. Total residency exceeds 128, so a complete
preload is impossible without a different encoding. Identical parts and X/Y mirrors share data.
In the exhaustive cache sequence, the largest changed upload is 512 bytes, versus 3072 bytes
for three complete 8-bit images. DMA is not enabled in this prototype. A DMA backend must
prove interrupt pulse behaviour, capability gating and identical pixel/port effects before use;
peak transfer estimates do not establish a whole-hook gain.

## Current integration checks

- Unchanged editable sheets rebuild byte for byte. Edited red/yellow pixels retain their exact
  RGB333 values; partial alpha is rejected. Loading screen and each trainer combination boot.
- Four verified trainers: infinite lives CA53; walking sound off CF00; movement reload CCA6;
  no-enemies calls C7FA/C801, retaining player call C808. Original archive addresses were
  translated where necessary. Each trainer alone and all together reconstruct byte-exact NEXes.
- Private 1.0-dev NXC: default/Enhanced and six trainer selections per mode apply byte exactly,
  with highest game bank 18 and hidden ROM46/47. The actual .NEXCLASH loader on disposable
  26.11 cards passed default, Enhanced and Enhanced plus all trainers before the game-over fix.
  That earlier package is historical; the changed package must be retested.
- New original 60000-frame recording covers rooms 0/1, five life-loss entries and one actual
  CAC0 game-over entry. Its earlier scenery-only proof passed 72463 hook/R boundaries and 8511
  background screens; the current full composition proof adds original-vs-sprite pictures.
- Game-over64-case matrix: both modes, all four clocks, both IFFs and four R boundaries.
  Missing marker is detected in both modes. Native default captures at three points match
  the original bitmap exactly; Enhanced shows no remaining figure sprites.
- Current 3539 instruction-boundary IRQ injections pass, including CAC0. Maximum masked
  interval remains 6.14us in the ideal-clock model; this is not a hardware measurement.
- Standard 1000-frame auto check: 3940 hook/R comparisons per mode, 448 ABI cases and 792
  independent figure-pixel cases per mode. Wrong R, MMU, clock, position and game-over marker
  are caught. Complete hidden-ROM audit passes after separately proven E200 prefix entry.

- Final renderer pace rerun: 12 native trials, 300 player updates each, all 301 tracked samples
  identical. Quiet -0.05520..+0.00627%; busy -0.01441..+0.02307%; worst 20-update +0.09427%.
  Original interrupt counts and beeper event sequences match. Individual beeper intervals differ
  by at most 2.572us. Global R and some R-derived decisions still differ; no trajectory identity claim.

## Missing release work

- Full frozen verification/stamp passed: 66,000 frames per mode, 110,399 hook/R comparisons
  per mode, 15,825 exact default composed pictures and 13,947 Enhanced background screens.
  Both recordings passed the complete hidden-ROM audit; all five output NEXes rebuild exactly.
  Each recording/mode also passed 512 ABI cases, 24 isolated INT-window cases, 792 figure-pixel
  cases, two lifecycle cases and all five broken-build controls. The natural recordings do not
  reach C2B8; its separate 128-case synthetic ABI matrix and instruction-boundary IRQ injections
  pass. Synthetic coverage is not a natural later-room playthrough.
- Final package SHA256 cf4a4eb0cfab2fe22e0a241f56089fb0e883cd0a859815cbaff000366b4f8217:
  all 12 default/Enhanced trainer combinations reconstruct byte exactly. Actual .NEXCLASH on
  disposable 26.11 cards passed default, Enhanced, all trainers and each of four trainers alone.
  Every extracted NEX matches the selected direct build; all modes reach thousands of player
  updates, no accelerated beeper writes, and no enemies when that trainer is selected.
  The original HUD remains visible: 16,384 native pixels match the ULA and three exact-package
  default/Enhanced HUD captures match. A misleading preview prompted a clip experiment;
  pixel evidence showed no defect, so the experiment was discarded and verified source restored.
- Natural play has not completed later rooms or two-player transitions. All 20 room layouts
  have isolated original-composer/pixel checks; no completion claim.
- Randomized asynchronous input and global R trajectories are not identical. Held-input pace
  checks preserve tracked game state; finite coverage and retained failures are explicit.
- Hardware and other emulators untested. User review and packaging remain separate.

## Technique use

- detect.buffer-layout-producer: helped: survey identified buffer and original dirty-copy order.
- detect.drawing-parameters: helped: registers and descriptor tables establish frame geometry.
- detect.gameplay-screen-readers: helped: initial survey found no ULA game-logic readers;
  more coverage is required before treating all draw buffers as disposable.

## Lessons

- [local: Bruce exact-entry requirement] Resume before E200 and preserve the original prefix.
  A convenient title checkpoint hides loader state and is not an archive-to-build boot proof.
- [local: Bruce renderer boundary] Hardware positions belong after C7D2's visible copy,
  not the next back-buffer plot. Match the displayed frame, not the newest logical position.
- [local: Bruce pattern budget] Deduplicate packed parts and mirrored forms before deciding
  that all frames need uploads. Retain 12 spare slots so any active part can change safely.
- [local: Bruce pace evidence] Compare game state at every player update and retain failed
  trials. Packed transfers removed the observed extra interrupt gap in three repeat trials;
  that is not a proof that every possible interrupt arrival is safe.
- [local: native snapshot inspection] JNext ordinary RAM pages have a physical SRAM offset;
  reconstruct CPU RAM through the MMU and dedicated bank 5 VRAM, not raw ram.bin offsets.

- [local: Bruce partial-copy visibility] A figure newly drawn outside its dirty rectangle must retain
  its last displayed image after a full copy. Hiding it produced 43 incorrect screens; retaining it
  closes all 5,438 comparisons in the continuous recording.
- [local: Bruce separate tile writers] Lantern restoration writes the tile map at D640, independently
  of C2B8. A single-address write trace identified the missing notification; the negative control
  reproduces the 47 stale pixels.
- [local: Bruce clock boundary] Fast-clock accounting alone omits wrapper instructions at 3.5MHz.
  Moving speed restoration later improves pace but changes interrupt arrival phase; shorter hooks
  are not proof that interrupts cannot be lost.
- [local: pooled simulator units] Copy result registers/memory before reusing a simulator pool slot.
  Keeping the mutable simulator reference made two trainer outcomes appear equal.
- [local: Bruce hidden-ROM bounds] The model must expose only the actual hidden-ROM span when
  page 24 is unmapped. Exposing its whole private page hid two native entry/exit failures.
- [local: Bruce temporary vector] A private IM2 vector permits the original ISR during hook
  work without rewriting C003. Save its actual interrupted clock and use a separate IRQ stack.
- [local: Bruce idle refresh] Per-hook native R checks pass while original idle/IRQ phase changes
  global R and some random decisions; the local assertion is not global trajectory identity.
- [local: Bruce room budget] Steady-play averages hid 60..80ms of extra room-entry time.
  The unchanged original tile composer supplies enough time for repainting; pacing that window
  reduced both native entries to within 0.21%, with identical entry pictures and original R.

- [local: Bruce game-over visibility] Correct descriptors and pixels are insufficient when the
  native display intentionally removes every figure. Mark CAC0, hide at the original final
  copy, clear at room/title entry, and compare native original/default game-over pictures.
- [local: isolated interrupt modelling] A direct-opcode scope must set int_active=0 when it
  does not deliver interrupts. SkoolKit otherwise clears P/V on both LD A,I reads inside its
  raw-T signal window without running the ISR. Preserve IFF comparisons; test real delivery
  separately with the instruction-boundary injection matrix. The captured 69476T failure passes.
- [local: Bruce stack wait] At C2EC the differing FFF4 byte is below SP and is first
  overwritten by the original ISR at C02D. A no-interrupt lookahead stalled in the game wait
  loop and could not prove this. Deliver the original periodic interrupts during first-access
  tracing; retain every byte until its own first write is observed.
- [local: native sheet import] Preserve unedited palette indices, allocate edited solid RGB333
  colours explicitly, and reject partial alpha and the Layer2 transparency key. Sheet labels
  and padding are not game pixels; keep native image dimensions and frame identity stable.

## Friction

- reuse: [local: Bruce stage2] shared survey, recorder, nextboot, hooklib and pace tools used.
- retries: [local: Bruce stage2] corrected periodic ENTER input which paused the first recording.
- environment: [local: Bruce stage2] private JNext config/temp folders; shared card read-only.
- hand-rolled: [local: Bruce stage2] original-plot and packed-pixel oracles are game-specific.
- scratch: [local: Bruce stage2] ABI, packed-pixel, lifecycle, PNG import and continuous composition promoted into the engine; private native/injection probes retained with evidence.
- retries: [local: Bruce record integration] Generated checksum entry exceeded the historical verification-file budget. Consolidated only its generic introduction; kept all game evidence and generated hashes.

## Stage log

- 2026-11-08: fetched current main; exact-source intake, figure compatibility, continuous 6000-frame
  recording and native overlay. Packed resident/cache prototype replaces whole-image uploads.
  Stage2 remains open; no package, upstream push or shared-card write.

- 2026-11-08: full composition and 20-room colour checks pass. Multiple upload and wrapper approaches
  measured. Latest candidate held at missed-interrupt gate; no packaging claim. Batch continues Exolon.
- 2026-11-08: resumed after merging main a99feab. Private IM2/IRQ stack, bounded DI and paced
  original copier pass the current development checks above. Room transition and native input
  phase remain open. No source freeze, release record, NXC or shipping handoff yet.
- 2026-11-08: room composer window closes the measured entry regression. 64 new scope cases,
  512 ABI cases, 3279 IRQ injections, 2000-frame combined replay and 12 held-input native trials
  pass. Original source function checked before cloning; no game bytes added to source files.
  Remaining work is coverage, trainers, artwork import and release integration/loader proof.

- 2026-11-10: refreshed main dace0cc; implemented editable import, loading/trainer integration,
  standard auto/record/unit/composition paths and private NXC/real-loader trials. Recorded
  natural death/game over, fixed stale game-over figures and the isolated-INT harness fault.
  Current source is a release candidate; final freeze/stamp and loader rerun still required.

- 2026-11-10: extended standard composition exposed FFF4 dead-stack residue at seven
  additional boundaries. Original ISR C02D writes it before any read; interrupt-aware
  lookahead closes the proof. Targeted 6000-frame regression: 37935 events, 5438 exact
  pictures, 14 separately proven dead-byte observations, zero differences. The first
  frozen verification was stopped and is retained as a failure; it is superseded only
  when the next complete selftest passes. Build bytes did not change.
