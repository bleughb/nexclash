# Pentagram (Ultimate Play The Game, 1986)

## Next session

Stage 3: software release candidate, original monochrome default and optional approved Enhanced.
Source baseline `6dbfaad`, merged locally at `e11dbbe`; branch `game/pentagram-release`.
Do not regenerate over the owner's editable PNG. Use its matching compatibility layout for edits.
All software gates and the real loader are recorded below. Physical Next testing and a complete
natural playthrough remain unverified. No pushes or shared-card writes were made.

## Input and approved appearance

Exact archive `Pentagram (1986)(Ultimate Play The Game).z80`, MD5
`75b969b9da612b72c7780e11a862dbdd`; 48K, PC C352, SP5DFE, IM1/I=3F, IFF0.
Original loading-screen TAP MD5 `25a607235780039bd2133f2801a1501a`.
The original menu selects keyboard/Kempston/cursor/Interface II; 0 starts play.

Default keeps the original monochrome picture and gameplay. Enhanced is optional and off by
default. Jon approved the part-based colours by editing PENTAGRAM_PAINTING_SPRITES on 7 November.
The frozen import honours 271 edits, including 59 mask-only black pixels and one enclosed rune
pinhole at ID93/native(20,10). That single visual opacity exception is explicitly whitelisted;
original geometry/mask/game RAM never changes. No exterior outline or external conversion is used.
Patch and Enhanced colours: Jon Attree. Built with NexClash by Dean Woodyatt (Bleugh.biz).

## Engine and memory

The original masked plot uses OR when byte-aligned and XOR when shifted. Nine source ink pixels
lie outside their masks; the compiler/oracle retains that original difference instead of silently
normalising it. Graphics table6DD7: 172 slots, 144 nonempty IDs, 86 unique masked graphics.
Ready plot B3EA writes the bottom-up 32x192 buffer D88F; full copy B178, partial renderer B19E.

Default uses five guarded sites, shared IFF/R/incoming-speed preservation, renderer pace K100,
and fast cold copies. Enhanced adds the actor span, original-order tagged colour canvas, exact
16x16 tile history, clipped hardware figures and double-buffered Layer2 static scenery. Exact
opaque black remains owned even when its RGB is black. All source orientations and draw order
are retained. Cache hash matches require full byte equality; old visible patterns remain protected.
If more than 64 unique patterns or the protected cache union cannot fit, an exact Layer2 frame
stages publication. Candidate redraws and stale display-buffer tiles have separate flags.

Enhanced source pages28..51/64..67, canvas52..57, displays58..63/70..75, directory76/77,
history78..83, auxiliary code84, pattern backing88/89 and complete hidden ROM94/95.
Both packaged modes have highest 16K bank47 and NEX memory flag0: the 1MB layout.
The self-erasing loader tail is below C000 and restores every original RAM/register/R value;
ordinary and NEXLOAD bootstrap paths are checked. The complete Sinclair ROM is independent of
NextZXOS v2.10 (26.11)'s hidden ROM contents. No physical-hardware claim follows from this.

Shared hlib_iff, HLIB_R_IN/OUT, HLIB_SPEED_IN/OUT and hlib_pace are used unchanged. Every actual
recorded hook enters with IFF0. Synthetic ABI matrices cover both IFF states and all four incoming
clock values; they do not establish accepted-IRQ/R behaviour during a hypothetical IFF1 game.
Actor K104 and renderer K84 accumulate one target, with one final wait after publication. Whole
beeper effects/tunes restore the original clock and are excluded from accelerated timing. The
outer sort checkpoint prevents missing raster wraps. Exceptional long busy targets saturate;
they cannot wrap and create false debt. Abandoned actor spans are cancelled before any new speed
latch, including room-init/full-copy paths. This fixes the transition clock leak caught by soak.

## DMA decision

The original AND/OR/XOR shifted renderer cannot be replaced by byte-transfer DDMA. Default keeps
its CPU copy loop. Enhanced uses the shared ordinary DMA path for linear canvas/pattern copies,
with a CPU fallback; it sends no core3.03 DDMA extensions. Both publication paths pass exact pixel,
opaque-black, live-cache, 40-to-40 union, 64/65-pattern overflow and removal fixtures. No hardware
throughput claim or dependency on a later blitter core is introduced.

## Verification

Final runtime ROM page SHA256 `dc03242395132e6b77522bc1e7af4e4f78898ee58d3be26bdc2f251efefa6152`.
Prototype and generic emitted code/assets/setup are byte-identical. Generic auto, registry,
record, original-screen output, editable/reference sheets and guarded recolour are integrated.
The final generic selftest --verify --stamp passes all six rebuilt output hashes, both full
replays, assembler identity and bidirectional recolour; the record is stamped verified.
Both fresh-sheet and actual owner-sheet readback rebuild the approved NEX exactly; empty-map to
approved-map roundtrip is exact. Wrong source geometry, hook version and exterior paint are refused.

Both modes replay all 18,000 original input frames: 6,476 default and 10,279 Enhanced completed
outer hooks. All registers including R, original bitmap and full 48K RAM match except the exact
patch bytes, checked live hook return words and measured dead stack below the original SP.
All already-started final calls are closed by 9,313 original input-free instructions; no unfinished
hook remains. Enhanced compares 26,448 ordered plots and 1,970 complete published pictures,
including hardware coordinates, visible pattern bytes, opacity and Layer2. The independent original
stack-liveness pass has zero reads before overwrite; scalar/slice negatives are detected.

There are 512 caller ABI cases and 144 whole-effect cases with 379,904 exact FE edges and exact
intra-effect intervals. R, speed, bitmap, source orientation, opaque black, role classification and
sprite-position negatives are all detected for their intended reason. The lifecycle regression
adds 32 abandoned-span cases and catches a deliberately omitted cancellation. The pixel primitive
suite compares 113,246,208 canvas pixels across 2,304 plots plus 104 clears.

Matched native tests compare 2,652 player states/registers/R and 8,972 FE writes at original clock.
The player probe deliberately lies inside the 28MHz actor span: execution clock is not claimed
identical to the original at that point. Beeper high-half-wave median delta is zero; native
contention introduces at most 48 master-cycle jitter. Entire effects remain original-clock.

Nine main trials use three R seeds in each scene. Warmed quiet16 is 0.304% faster and quiet0C
1.387% faster; busy6B is 8.93-8.97% faster. All scene aggregates are faster, quiet within 2%.
Cold init is 33-38% faster, and every first14 entry interval is faster independently of later debt.
Supplementary held-jump 5C-to-5B trials have exact states/input and average about 4% faster.
Individual update jitter remains: the worst supplementary interval is 21.99% slower, the worst
10-update window 3.67% slower; every 20-update window is within 1.08%, and every 50-update window
is faster. Five isolated original-fast intervals are not a sustained quiet-scene proof. Do not
claim every update is faster or hide transient results in scene averages.

Beam publication: 96 unchanged native publications, zero unsafe intervals, maximum17,463 master
cycles. A debugger-only skipped-wait negative catches nine unsafe publications out of32. Stable
native PNGs exactly reconstruct from all49,152 tagged canvas bytes, front Layer2 and hardware
patterns after the correct viewport crop and RGB333 quantisation. Union bounds include previous
figures, new figures and changed scenery; retired sprite coordinates are retained until disabled.

The final original-menu Enhanced native soak runs 18,000 gameplay-scheduled frames: 2,139 updates,
seven rooms, 17 deaths, four starts (three restarts) and three gameovers. All105,793 FE writes use original clock,
with zero clock errors or emulator errors; menus, game over and restart pictures were inspected.
This is lifecycle/visual coverage, not an input-identical pace comparison or full game completion.

## Trainers and loader

All trainers are off by default and tested individually against the exact48K archive:
Infinite Lives C2FD=201 preserves four lives after death (original four-to-three);
Mega Jump C63F=0 reaches Z248 instead of Z156 with the actual held DOWN/jump control;
Start with9 lives patches initial immediate AFA8=10, before the original initial decrement.
The archive's `Immunity` name is misleading: it prevents life decrement, not collisions.
Compatibility OUT FD at B952 becomes JR+0, preserving R/AF unlike the archive's two NOPs.
Eight keyboard-row fixtures and all native paired states verify that translation.

The final .nxc is reconstructed byte-exact at ram_top47 by the host and the actual .NEXCLASH
loader on disposable private NextZXOS v2.10 card copies: default, Enhanced and Enhanced with all
three trainers (167/171/171 player updates respectively). Each individual trainer changes only its specified bytes in either mode.
Release NFO includes Known issues: and Missing:. Original game/ROM/card payloads are not bundled.

## Technique use

- detect.graphics-record-layout: used: live object table and masked source packing.
- detect.drawing-parameters: used: coordinates, temporary orientation and source identity.
- verify.paint-follows-drawing: used: parts along original lines, exact owner-edit import.

## Lessons

- [local: exact source semantics] Aligned OR and shifted XOR differ for ink outside the mask;
  retain live original ink in the independent oracle rather than normalising malformed masks.
- [local: pixel ownership] Black pixels and approved mask-only edits need exact tagged ownership;
  RGB nonblack tests lose wholly black tiles. Candidate versus stale dirty flags must be separate.
- [local: lifecycle clock latch] Cancel an abandoned actor span before latching a room-copy clock;
  a nested clear restoring it later is too late. Verify actual recorded FE clock against zero,
  not only against a potentially corrupted saved latch. Long soak found what steady fixtures missed.
- [local: long pace windows] Sort checkpoints prevent raster-wrap loss; saturating exceptional
  targets prevents wrapped debt. Whole-effect timing exclusions must cover silence and tail-JPs.
- [local: stack lifetime] Compare live return words exactly and derive dead stack from actual SP;
  retain address census and a separate original read-before-write audit.
- [local: native publication evidence] Deferred snapshots need a stable return-point spin for pixel
  identity. The640x512 native frame's active crop is(64,64,576,448), with rounded RGB333 channels.

## Friction

- reuse: [none: shared helpers reused unchanged] IFF, R, speed, pace, ordinary DMA, generic sheets and recorder.
- retries: [local: full bootstrap and lifecycle gates] Short alt-ROM spans must include the tail
  restorer; lifecycle sound checks must independently validate the incoming original clock.
- environment: [local: queued native image writes] Do not exit in the same event as a snapshot;
  pure timing probes avoid queued images, pixel probes freeze and wait three frames.
- hand-rolled: [local: required game oracle] Persistent MMU/cache/sprite model and original masked
  draw oracle are engine-specific; Z80N installation and shared libraries remain generic.
- scratch: [local: retained release evidence] Native timing/beam/loader fixtures stay in the release
  evidence bundle; supported build, verify, sheets and recolour are in the generic engine.

## Stage log

- 2026-11-07: original survey, approved owner import, default and Enhanced implementation, exact
  original-input/negative/native gates, current-main merge, generic integration and release packaging.

## Hardware checklist

No hardware result is claimed. On a real1MB Next, select default then Enhanced, exercise
room changes/death/restart, compare movement and beeper sound, and test each trainer separately.
Known issues: individual-update raster/publication jitter remains; complete natural game completion
is not verified. Missing: physical Next testing. See the run's release evidence for exact hashes.
