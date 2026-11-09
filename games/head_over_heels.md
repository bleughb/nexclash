# Head Over Heels (Ocean, 1987)

## Next session

Stage: 4 (hardware). Hardware: untested. v1.0 published as .nxc 1.0 (2026-11-08, nxc repo 4a18183) at the owner's request, not yet played by him. Default is the original monochrome look; Enhanced colours are a menu option, off by default.
Inputs (staged by the record, never in this repo): the 128K snapshot (MD5 757bbabf), three recordings, the tape's loading screen `head_over_heels.scr` (MD5 9ce8b2d5) and the colour data derived from Anthony Lycett's Spec256 set, `colours.bin` (MD5 eccfadb4) and `palette.bin` (MD5 d57f9dfb).
Build: `nexclash.py auto` writes `NAME.nex` (733570c0) and, with the colour data, `NAME_enhanced.nex` (4e8ba81e), equal to `nxc.py PATCH GAME --bare [--colours Enhanced]` of the published patch byte for byte.
Checks: `selftest.py --game head_over_heels --verify`: both rebuilds and boot checks, replay of the walk, death and game-over recordings with R, game banks and pixels, the broken builds. Native pace, soaks and real loader runs are the review run's (Evidence).
Pending: hardware review; natural completion; channel C effect phase.

## Inputs and presentation

- Exact128K archive Z80: MD5 757bbabf443a643cbe376ebfb11baa79,46,256 bytes, eight RAM banks.
  PC0051/SPFFDA is a captured ROM interrupt, not a BASIC loader; IM2/I97/DI, port7FFD10.
- Supplied colour source MD5 eba2dc3cc6717b60d31a97adef51318e;128K reference SNA
  2923ed7ce912bee0d52b7b29ed3d39c7. Every ninth monochrome byte matches its reference.
  All70 figure bitmap/mask families match the archive exactly after four horizontal flips.
  The128K executable and AY music are retained; no conversion executable is transplanted.
- Enhanced colours: Anthony Lycett (Spec256). Menu label is Enhanced; off by default.
  Patch by Jon Attree; NexClash / Dean Woodyatt (Bleugh.biz). No added outline or repaint.
- Default keeps the original monochrome presentation. No colour-clash-removal claim.
  Enhanced covers room art, figures, floors, constructed doors and static HUD icons.
  Game-built and fixed UI glyphs retain the original ULA text/attributes.
- Loading TAP MD5 a550220f26615e452d2e27384801cd18, block5; extracted6912-byte screen
  MD5 9ce8b2d53cd49ed8341a39a8de6c2e1c, included with a50-frame display delay.
- Archive POK MD5 96fa7154f6c45130715db4e6dd0dd7a5. Eight optional verified trainers:
  lives42195=0; immunity41837=24; ammo35315=0; spring35333/35334=0; mega43132=0;
  respawn34803=134; retain hush36944=0; starter templates41602=7/41609=153.
  First archive lives alternative42198 still decrements. Runtime starter pokes are reset;
  use the templates. Conflicting starter variants are consolidated into all items/99 shots.

## Runtime and memory

- Keep every original bitmap and game-state write. The independent colour model follows
  AND/OR masks, shifts, mirrors, XOR animation, door construction, tiled/stored columns,
  UI copies, screen clears and absolute dirty rectangles. Masks contain painted bits too.
- Buffer B800-B8FF is mirrored by a2048-byte ring at2000. B900 is the bit-reversal LUT;
  BA00 onward is scene state, never a discardable drawing buffer.
- Original shifts9EF6-9F36 and pure composition A0B6-93E8 run at28MHz; colour hooks restore
  the speed they entered. Both IRQ bridges retain the outer game clock for AY playback.
  The original final ULA copy and sound/delay code keep their original clock and instructions.
- Shared hlib_iff, HLIB_SPEED_IN/OUT and hlib_r. The original70F1 four-IRQ wait is unchanged.
  hlib_pace supplies a1220-scanline real-time floor at A59A, below the original quiet interval.
  IRQ hold/resume ticks prevent unseen frame wraps. Long busy updates earn no later speed-up.
- The actual update probe is A597. Normal IM2 path FFFF->FFF4->7376 and private IM1 forwarding
  both run the original ISR7376-7394 and banked AY routine. Pending pulses are checked between
  short drawing spans. A spare page25/MMU2 interrupt stack survives original7FFD writes.
- Page24 code and companion buffer; page25 IRQ stack; page26 low helper code/private vector;
  expanded colour pages28-75; Layer2 pages76-81. Full hidden ROM banks46/47. Highest bank47:
  default and Enhanced fit1MB. Temporary NEXLOAD5B00-5BFF workspace is restored completely.
- Reserve duplicate palette index71 for transparency, mapping painted71 to identical63 only
  at final display copy. Preserve visible white255 and reset ULA bright-black entry24 to black.
- DMA/DDMA evaluated against docs/DDMA.md: neither replaces the required per-pixel AND/OR
  and shifts. CPU copies avoid extra core gating and interrupt latency; no DMA claim is made.

## Evidence and scope

- Boot: exact registers including R and all131,072 game RAM bytes (outside intentional hook
  bytes), both converter startup and NEXLOAD overwrite, with NextZXOS26.11 system ROM.
- Frozen source selftest passes all15,400 recorded frames, including the final menu-text
  correction and normal music-handler R checks. Per-record counts are in the private report.
- Death1200 frames:7568 hooks/274048 pixels. Game-over2200 frames:2398 hooks/8704 pixels.
  These start from an actual captured collision entry with seeded collision/lives state;
  all subsequent game execution is original and recorded, with no runtime intervention.
- R is compared at every recorded hook, including complete normal music-handler calls.
  The normal-handler reference uses the same reserved stack; all original game banks compare. Private/normal ISR ABI and nested render IRQs
  are separately injected, covering four incoming clocks and both caller interrupt states.
  IRQ controls use a reserved reference stack; the actual interrupted return word in original
  RAM is explicitly excluded in those injection cases. This is not full native RAM lockstep.
- Full compositor checks cover eight captured rooms/rectangles through return:34 cases.
  Combined nested-render IRQ suite41 cases. Mutation108, columns142, final copy291, private
  vector28, shared pace50. The otherwise unreached76DB LDDR is covered by32 engine units.
  Recorded wrong-source, wrong-position and wrong-R builds fail; reverse-copy and pace units
  also contain negative controls. The source-only replay proof is nexclash/head_over_heels.py.
- Per-event replay keeps colour state continuous but supplies original elapsed frame time to
  independent player-hook calls. Actual waits are checked by beam-driven units and native trials.
- Native pace: two scenes, three seeds,200 player updates each. Quiet -0.0111% to+0.0056%; busy
  -0.4144% to+0.0037%; worst20-update window+0.0158%. All201 tracked states agree per trial.
  Final menu-corrected build passes. Effects are counted after original DI at967C.
- Each native trial has800 actual music-handler calls at3.5MHz and17600 AY port writes.
  Music channelsA/B match; asynchronous channelC effects differ in interrupt phase. Hardware
  acknowledgement counters omit software-forwarded pending pulses; use actual handler gaps.
- Known issues: channelC sound-effect phase differs after accelerated drawing. No full ordered
  AY-stream identity claim. Native raster/physical hardware behavior remains untested.
- Missing: a natural full-game completion and hardware testing. Finite replay/capture coverage
  is not a claim that every room or possible game path has been visited.

## Rebuild and artwork

- `python -m nexclash.head_over_heels SOURCE.z80 OUT.nex` builds the original presentation.
  Add `--assets DIR --loading SCREEN.scr` for private derived Enhanced pixels and loading art.
  DIR contains colours.bin393216 bytes and palette.bin512 bytes; source files are never bundled.
- `auto` recognizes the exact128K hook signatures. It uses private colours.bin/palette.bin and
  matching-stem .scr beside a staged snapshot, or NEXCLASH_HEAD_OVER_HEELS_ASSETS/SCREEN.
  The manifest names default and optional Enhanced explicitly. Replay and negative proofs run
  through the engine, with full memory/R and displayed pixel checks, not stored pass flags.
- Editable artwork stays in pilot out/HEAD_OVER_HEELS_PAINTING_SPRITES.png. The private
  importer preserves that file, rejects edits outside each original edge, and exports drawing
  ranges only (9D03-9D44, A349-A354, C050-FB27); other colour memory starts empty.
- Never commit snapshots, recordings, ROMs, colour planes, derived artwork or NEX files.
  The source contribution contains code, profile, evidence metadata, notes and integration diff.

## Hardware review (not yet performed)

Check the original loading screen and menus, both presentations on a 1MB Next,
busy room changes with AY music, door/foreground occlusion, death and game-over,
restart and all eight trainers under NextZXOS v2.10 (26.11). Verify raster stability
and the full hidden-ROM startup on the actual target. No board result is recorded.

## Technique use

- detect.buffer-layout-producer: used: classify all writers feeding the final dirty rectangle.
- detect.drawing-parameters: used: capture actual clipped dimensions and source addresses.
- detect.gameplay-screen-readers: used: retain all original game memory and original screen writes.
- patch.iff-safe-read: used: shared safe reads and exact caller-IFF restoration.
- patch.preserve-r: used: refresh wrap/bit7, original IRQ credits and failing negative controls.
- patch.restore-speed: used: four clocks plus nested rendering and original AY clock.
- patch.pace-limiter: used: shared minimum guard alongside the original four-IRQ cap.
- patch.isr-deferral: no help: timely forwarding is required throughout long drawing spans.

## Lessons

- [local: Head Over Heels entry] PC0051 is a captured interrupt, not sufficient evidence of a
  loader. Original simulator execution reaches the menu and rooms; retain the exact archive source.
- [local: Head Over Heels colour source] Its colour reference really is128K and every ninth
  monochrome byte matches its snapshot. All70 figure families match after four horizontal flips; the archive executable is retained.
- [local: Head Over Heels masks] Colour masks are not binary transparency. Ignoring their painted
  bits made the first offline colour image hollow; preserve the original AND/OR composition per plane.
- [local: Head Over Heels boot] Restore the entire256-byte NEXLOAD printer buffer, not only the
  shorter startup tail. Exact eight-bank comparison passed with the temporary workspace erased.
- [local: Head Over Heels trainers] Runtime data pokes can be valid yet disappear at new-game reset.
  Translate them to the original nine-byte template and test the complete menu-to-play path.
- [local: Head Over Heels dynamic art] A static sprite match does not cover animation XORs or
  constructed doors. The independent monochrome companion exposed both; model their original
  writes before judging a colour picture complete.
- [local: Head Over Heels render budget] A renderer can fit normal update intervals and still
  slow room changes substantially. Include full-room work periods, and label estimates separately
  from native pace measurements. Direct expanded copies avoid the costly bit-plane transpose.
- [local: Head Over Heels IRQ stack] Original7FFD writes replace MMU1, so a forwarded music ISR
  cannot retain a private stack at3Exx. A separate stack in spare page25/MMU2 survives those writes;
  the original ISR's observed memory footprint excludes MMU2. Cover the entry stack switch too,
  before the safe IFF read, and bypass the normal bridge when a private bridge calls the original.
- [local: Head Over Heels interrupt evidence] Injection checks alone missed the native stack race.
  Run the known failing later-room input again; count original handler entries as well as hardware
  acknowledgements when a pending latch can forward a missed pulse. Equal counts do not prove
  equal timing: the25.132ms gap required a separate per-row poll.
- [local: Head Over Heels refresh vector] The actual IM2 route is FFFF to FFF4 to7376. Start the
  reference at interrupt acknowledgement rather than assuming a refresh count at the ISR entry.
- [local: Head Over Heels sound scope] AY channelsA/B match while asynchronous channelC effects
  differ in native traces. Report that distinction; equal write rates alone are not sound proof.
- [local: Head Over Heels NextREG reads] An ISR can change the shared register-select port between
  OUT243B and IN253B. The mutation selector is now latched during the existing entry DI window;
  boundary injection caught the old version even though register/R and game RAM still matched.
- [local: Head Over Heels pulse phase] Added drawing changes can place a ULA pulse inside the
  original967B sound-bank DI window. Trace the actual interrupted PC, then recover the pending
  pulse between companion drawing spans; do not change the sound routine or dismiss a real40ms handler gap.
- [local: Head Over Heels shift cost] Polling every row adds cost when the row never disables
  interrupts. The shift kernel keeps hardware IRQs enabled and polls pending status every four rows;
  use native handler deadlines and pace to check this separately from pixel equivalence.

- [local: Head Over Heels loop entries] Entry-only ABI checks missed loops branching into
  displaced bytes. Keep small whole loops in immutable trampolines, or move the patch ahead of
  every back edge; check original and patched routines through return and run the native room.
- [local: Head Over Heels palette transparency] Index255 is painted white, not free transparency.
  Reserve exact duplicate71 and remap painted71 to63 only at final copy; keep source mask values
  untouched. Changing global transparency also requires resetting ULA bright-black entry24.
- [local: Head Over Heels nested clock] Accelerated original drawing nests colour hooks. Track
  the outer game clock separately so both IRQ bridges run AY at3.5MHz even while drawing at28MHz.

- [local: Head Over Heels pace guard] Keep the original four-IRQ wait. A shared1220-line
  minimum guard prevents acceleration of steady play without adding a second four-frame wait;
  subtract held ISR time from the target and discard busy-window debt before the next update.
- [local: Head Over Heels menu glyphs] The fixed one-byte/eight-row menu font uses source
  addresses that overlap companion scenery. Keep these UI rectangles transparent to the original
  ULA, as with the game-built B66D glyphs. Native menu inspection caught a mistake shared by the model.
- [local: Head Over Heels startup automation] A loading screen changes input timing. Anchor
  startup keys to the restored0051/SPFFDA entry, and assert actual player updates before accepting
  a long soak; screenshots of a live menu alone do not prove play.
- [local: Head Over Heels event traces] An execute breakpoint can fire twice around an interrupt
  before its instruction actually runs. Count effects at967C, after the original DI, with the
  argument already in D; do not interpret an entry duplicate as another effect request.

- [local: Head Over Heels interrupt paging] The original ISR can leave bank1 selected.
  A recorded interrupt check must start from the recording's current7FFD bank and compare
  the original handler's resulting mapping, not require bank0. Registers/R, game banks
  and AY writes matched at the formerly rejected event; the corrected5000-frame check passes.

- [local: Head Over Heels upstream] A stamp from a frozen branch does not carry over: main's shared boot code had changed since its base, and the stamp named another Next ROM, so it was verified and stamped again on main's tree with the ROM most games use.

## Friction

- reuse: [local: Head Over Heels recorder] Private128K recorder preserves all banks and AY state.
- retries: [local: Head Over Heels menus] Inspect title, menus and game-over as well as rooms.
- environment: [local: Head Over Heels cards] Real-loader writes use disposable card copies only.
- hand-rolled: [local: Head Over Heels proof] Source-only per-event colour oracle is game-specific;
  native timing and IRQ injection cover its deliberate timing abstraction.
- scratch: [local: Head Over Heels proof] Portable replay and LDDR units are part of the engine;
  capture/input/artwork-source helpers remain private and do not enter the contribution.

## Stage log

-2026-11-09: upstream on current main: registration (the source package's engines.py line), record order 247 (230 is taken), views; rebuilt both published MD5s and re-verified and re-stamped on main's tree, since the shared boot model and record code had changed since c086e2b.
-2026-11-08: published as .nxc 1.0 (nxc 4a18183) at the owner's request, not yet played by him.
-2026-11-08: fetched main c086e2b, verified the archive/reference, recorded original128K play.
-2026-11-08: replaced the rejected repeated-plane design with direct companion pixels;
  fixed loop back edges, nested clock restoration, IRQ stack switching and palette transparency.
-2026-11-08: connected all drawing paths, restored original pace, added shared pace guard,
  source-only replay/units and death/game-over coverage. Built1MB release candidates and NXC.
-2026-11-08: native loading/menu review found fixed glyphs using scenery colours; preserved
  those glyphs and anchored automated startup to the restored game entry. Final native checks and frozen source proof pass.
  Main refresh is deferred while those checks and this work are in flight; knowledge base c086e2b.

-2026-11-08: frozen source 34fd85a passes selftest --verify --stamp. Default and Enhanced
  NEX MD5s733570c090d77d8f8a8bc52cb7a6719b/4e8ba81e7131c86a9c785ae45f7e4137.
  Real .NEXCLASH default/Enhanced/all-trainer modes rebuild exactly and play on disposable
 26.11 card copies;20000-frame native soaks pass both modes. Source-only contribution prepared.
