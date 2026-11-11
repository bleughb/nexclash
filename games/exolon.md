# Exolon (Hewson Consultants, 1987)

## Next session

Release candidate complete: runtime 96d0907 and guarded verifier a976349 on main dace0cc, exact NXC,
full replay stamp, native pace/sound/lifecycle checks and eight disposable-card actual-loader
runs. No push, shared-card write or hardware claim. See the run's packaging handoff.

Default retains original figure colours; Enhanced is optional and off. Five independently
verified 128K trainers and original loading screen. All options fit 1MB. Preserve the 81-frame
native editable sheet and its pixel borders. Patch by Jon Attree; Enhanced colours by
Jao Paulo (Spec256); NexClash / Dean Woodyatt (Bleugh.biz).

Next: packaging review and user/hardware play, especially later zones. Working CTC3 is
required for accepted sound timing; bounded absent/stalled-clock fallback has functional
checks only. Do not revive the rejected generic-boundary timing experiment or old ungated
pace tables. Those counted loader address 81A4. The valid counter/input gate is MMU4+caller 75CE.

## Inputs and observed facts

- Requested archive 128K Z80: MD5 87515df87645c4179a9ef90663774c7f, 52,628 bytes,
  eight RAM banks. PC80DB, SPFFE4, IM1/DI at entry, port 7FFD30 (paging locked).
- Original continuous 6,000-frame recording starts from that exact source. Menus, gameplay and
  AY writes are reached: 29,708 AY data writes, 9,450 ULA-port writes in the recording.
  Native sound/pace checks below retain the AY behaviour. A128K label alone was not used as music evidence.
- Colour source MD5 7c7348250d324c2a4211236414e1dbd4; reference SNA is 48K,
  MD5 17b01358a2c3c44f00aba34aac0809b7. Credit Enhanced colours: Jao Paulo (Spec256).
  Keep archive code; compare/map graphics before using colours. Menu says Enhanced, off by default.
- Archive POK MD5 a37a2102bf420c0dabdd7cd7323fd30c. Five compatible options are verified: lives, ammo, grenades, mines harmless and immunity.
  Contradictory enemy-control options remain excluded.
- Original TAP MD5 abded3d09e3625073bd1a42a394c017a. Its sixth block decompressed by its own 8001 routine yields loading SCR MD5 e57f1a46fed24dfb566ff09f95e64a38.
- R reads at 7C2B (beeper routine) and 9858. Preserve R at every hook, including idle paths.
- User credits: Patch by Jon Attree; NexClash / Dean Woodyatt (Bleugh.biz).

## Requirements

Original look/clash removed by default; supplied colours optional. Original pace quiet within 2%,
busy no slower, counted at player updates. Shared interrupt/speed/pace code. Full hidden ROM,
NextZXOS 26.11, highest game bank 47 or lower. Editable PNGs, isolated cheats, original loading
screen, NXC exact rebuild and private-card real-loader checks in all three modes. No pushes,
shared-card writes, game data in the repository/source package, or hardware claims.

## Development design and evidence

- Original keyboard mapping is O/P left/right, Q/A up/down, M fire (7AE9 keyboard decoder).
  The earlier keyboard recording sent Z/X; it tests stationary firing/enemies, not walking.
  Corrected exolon_moving.rzx has 6,000 continuous original frames and reaches zones 0 through 3.
- Large plot 76DA / exit 7897: 24 x 32, EF80 + A*96; 24 animated player frames, plus a fixture
  at frame 24, rendered in four owner groups (slots 4-19). Small plot 795C / exit 7AB0: 16 x 16, F8E0 + A*32.
  Old-picture buffer HL identifies the owner; B101 is an empty timing plot, B181 is the player.
- Foreground mask at 5B00 follows the original plot's pixel occlusion; sprite clip is 256 x 176.
  Small player death pictures share slot0 and hide the other three large-player parts.
- Tiny effect 92FB / exit 935D: 8-row XOR toggles, ED40 + A*64 + (E&3)*16. Seven nonempty
  source images plus blank 6. Eight resident effect patterns, active positions tracked separately.
- Painter exit 7CE7 captures original C and DE. Player painting happens BEFORE its plot; small
  painting can follow its plot. Pending colour/position and last figure tracking cover both orders.
- Resets B04B and B061 hide all sprites, clear owners/effects and reset the spare-pattern queue.
- Slot1 page 24 owns code/state; source assets pages 26-33; page 34 contains the exact 512-byte
  startup-tail backup. Boot copies it to 5B00 before resuming the archive PC. Main at 2800,
  renderer 3000, painter 3400, source directory 3700, owner/pattern tables 3800/3900, colours 3A00,
  effect state 3B00-3D4F. Hidden ROM includes the original empty plot copied to 3600 at build time. Projectile exits are at 2500; padding at 2000.
- The empty effect padding call at 9E92 targets that byte-identical 92FB-9361 copy. Relative
  branches and external CALL B088 are unchanged. No game data is stored in the engine source.
  The 9E85 padding function has identical registers/R, RAM and model time at all four clocks,
  with both IFF states. The original delay still runs; no sprite hook is entered for blank padding.
- Six spare patterns let all four large-figure parts upload before one attribute burst.
  Effect patterns 48-55 and projectile patterns 56-57 stay resident. Pattern uploads into visible patterns are checked by the model.
- First colour oracle: 28 large/small cases, source-colour pixels, mirrors, edge and mask clipping,
  registers and RAM pass. 160 reset/painter ABI cases pass (4 speeds, 2 IFF, 4 R boundaries).
  A separate 128-case projectile test checks all clocks, both IFF states, R edges, pixels and erasure.
- Both direct and NEXLOAD model entries reproduce original registers/R and visible game RAM.
  The latest page 34 backup change passes both. Eight exact-package native real-loader runs pass; see below.
- Enhanced prototype reaches play in JNext; four screenshots in jn/colour-first. No hardware test.

## Release evidence

- Twelve native trials: two checkpoints, seeds 2/5/11, default and Enhanced, 180 actual player
  updates each. All 181 tracked game states match. Quiet -1.631..+0.585%, busy -0.969..+0.403%,
  worst 20-update window +1.332%; positive is slower. Gate 81A4 on MMU4 and return 75CE.
- AY and FE values, counts and order agree in all twelve pairs; every sound write runs at
  original speed. Same-PC short AY intervals are exact. First-scene explosion pulse medians:
  Enhanced -5.072..-0.660us, default +6.429..+8us. Individual differences range roughly
  -94.4..+117.6us. Original-only phase controls have -101.714..+106.857us individual jitter,
  median zero, with unchanged state and FE order. Retain the small fixed median difference;
  do not claim pulse identity. Second-scene FE events have no qualifying short intervals.
- CTC3 is an owned free-running clock, prescaler 256/constant0, interrupts disabled, tick 32
  original T. State 3EB0..3EB2 is outside V_ATTR 3E90..3EA7. Default explosion plots use
  13/14 ticks; other plots 21. The hook credits elapsed time to shared pace debt. Non-original
  incoming speed bypasses the explicit wait. Absent/stalled clock exits are bounded and
  preserve operation, but those configurations have no timing acceptance.
- Per mode, 704 ABI cases cover 11 hook sites, four speeds, two IFF states and eight R values.
  420 independent source-pixel cases cover all stored frames, directions, edges and foreground
  masks. Reset, full effect pool and full owner table are checked. 256 whole-noise-loop phase
  cases compare registers/R/RAM/I/O; eight deliberately late deadlines are caught. Missing and
  stalled clocks are checked. Position, mask, R, MMU, speed, source-colour and pool-guard broken
  builds are each caught using their own modified tables.
- Five trainers: lives 9D1D, ammo 836E, grenades 9250 -> NOP; mines 9CAE, immunity 9CB8 -> RET.
  Eleven original-function cases test counters 1/7/99 and both death paths. All are off by
  default. Other contradictory archive options are excluded, not silently accepted.
- Boot reproduces original registers/R, visible RAM, unmapped 128K banks and both complete
  hidden-ROM pages, accounting for the loader register block. Direct and NEXLOAD entries pass.
  Highest game bank 17; reserved full-ROM banks 46/47. Original compressed-TAP loading screen.
- Exact NXC reconstruction passes default/Enhanced with no trainer, each of five, and all five
  (14 combinations). Eight actual .NEXCLASH loader runs cover default, Enhanced, Enhanced+all
  and Enhanced+each. Every resulting NEX is byte-identical, trainer bytes agree, native play
  advances, and no accelerated FE write is observed. Private card copies only.
- Editable native sheet: 81 frames at 480x336. Unchanged imports are byte-identical; one-pixel
  edits become solid RGB333 colours. Partial alpha, silhouette changes and paint outside cells
  are rejected. Two tiny literal projectiles retain their original white shape outside the sheet.
- Original lifecycle recording has 2,494 continuous frames: menu, all nine deaths, game over
  and return toward menu. Moving recording has 6,000 frames and reaches zones 0-3. Frozen verification passes all 8,494 frames per mode, with
  79,030 hook/R comparisons and 3,884,482,560 game-RAM bytes per mode.
  All five NEX outputs reproduce exactly; both recordings pass the ROM-path checks.
- CPU uploads perform the per-pixel foreground mask/XOR transformation. DMA/DDMA cannot do
  that transformation directly; staging adds work and ownership state. The current CPU path
  is measured end to end. No DDMA or hardware performance claim.

- Native lifecycle/soak: 24,000 scheduled frames in original/default/Enhanced; 8,364/8,947/8,172
  actual player updates, no hang or accelerated AY/FE writes. All reach natural game over and
  return to the menu; later scripted restarts exercise movement/fire. Inputs here are frame-keyed,
  so totals are not a pace comparison. Lives also wrap after later restarts in the unchanged
  original; the patch does not fix that original behaviour. Twenty patched snapshots have no
  effect-pool error, and menu captures have no stale multipart player (animated stars remain).

- The first full run passed all replay and unit cases, then failed the static ROM audit at
  B0C0 after game over. This is the unchanged B0B7 delay: HL=DE=0, LDIR, then restore BC/DE/HL.
  It copies each byte to itself, with no data consumer. Moving uses BC500; lifecycle adds two
  BC0 (65536-byte) delays. The long calls end in RAM, so final flags also use unchanged RAM.
  The exception for replaced ROM2000..3FFF is conditional: a separate original replay rejects
  ANY read unless PC=B0C0, HL=DE=address, DI, and the final byte lies in RAM. Whole-function
  comparisons test all observed count classes with A0/7/255, including exact R,flags, RAM and
  model time. Four negative read guards catch a consumer, unequal destination, final ROM byte
  and enabled interrupts. No game/runtime bytes are changed for this exception.

## Known issues and missing coverage

Known issues: individual update and noise-pulse timings vary with video contention; measured
scene pace is within 2%, but not identical. Working CTC3 is required for the accepted noise timing;
missing-clock fallback is functional only. Enhanced repaints figures, not all background artwork.

Missing: natural completion and exhaustive later-zone play; hardware and other-emulator tests;
certification of the contradictory unused archive cheats. The two literal tiny projectiles do
not have editable cells. The full frozen proof and native soak pass; the limits above remain.

## Hardware checklist

Use the exact handoff package on a separate card: default, Enhanced and each trainer; confirm
loading screen, original-speed movement, AY music and explosion sound, foreground occlusion,
deaths/game-over/reset, later zones, full memory fit and restored caller speed. Report the core,
NextZXOS, RAM and package hash. These are requested checks, not claims of hardware results.

## Technique use

- patch.timed-side-effect-replay: helped: identifies an original-time OUT model and CTC phase
  checks as prerequisites; used to require separate edge timestamps and the original-only phase control.
- patch.work-in-timed-gaps: helped: deferred work must meet the sound deadline, not merely
  catch up by the next player update; no dropped-frame design has been adopted.

- detect.buffer-layout-producer: used: identify composer versus screen copy before choosing hooks.
- detect.drawing-parameters: used: observe live figure dimensions/coordinates at the flagged plotters.
- detect.gameplay-screen-readers: used: classify collision reads before removing figure pixels.

## Lessons

- [local: Exolon pace probe] Address 81A4 also executes in the loader's MMU20 page with
  returnFFFF. It inflated the first busy window by counting pre-game activity. Gate the
  player counter AND input events on MMU4 and original caller 75CE; preserve failed tables.
- [local: Exolon oscillator control] Different entry video phases change the unchanged
  original noise pulses by roughly+/-107us. Compare timestamp distributions against that
  control as well as event identity; retain systematic median shifts separately.
- [local: Exolon CTC ownership] Channel 3 has no original game owner; configure its timer
  with interrupts disabled, test all 32 phases and absent/stalled clocks. State must stay
  outside the 24-byte attribute burst. Missing-clock fallback has no timing acceptance.
- [local: Exolon fixture tests] Large frame 24 belongs to fixture ownersB201/B281/B301/B381;
  pairing it with player ownerB181 is invalid. Enumerate real owner/frame relationships.

- [local: Exolon particle entry] Moving the speed latch before IFF/R capture removes 29.75us
  from a sampled full effect call (340.50 ->310.75us), but R correction must include the 15
  fetches moved before capture. All four incoming clocks and IFF/R boundaries are checked.
- [local: Exolon deadline evidence] A median pulse error near 2.6% still contains 14.7% outliers.
  Compare every adjacent oscillator write within the same update. Whole-game pace and AY
  event identity cannot establish noise pitch; both rejected experiments remain recorded.

- [local: Exolon source selection] Requested source contains eight banks with paging locked, yet
  executes AY sound output. Retain it; changing to the 48K colour source would discard release behaviour.
- [local: Exolon recording] The existing private 128K recorder from Treasure Island Dizzy retains
  AY state, all banks and native fetch counts; the shared 48K recorder cannot save this source directly.

- [local: Exolon bitplanes] Each .256 address has eight bitplanes followed by its original byte,
  not eight palette indices. Decode the planes; the first incorrect draft was replaced before editing.
- [local: Exolon keyboard] Read the actual key decoder before recording movement. The early Z/X
  schedule was stationary in this release; corrected O/P recordings now reach later zones.
- [local: Exolon paint order] Match before-plot colours by position; an owner-only lookup loses the
  player's colour because its painter's HL is the frame pointer, not the old-picture buffer.
- [local: Exolon timing] An aggregate pace number hides opposite errors in quiet and busy scenes.
  Keep the phase rows and update-keyed state proof, including failed trials.
- [local: Exolon empty effects] Profile the deliberate blank drawing separately from real effects;
  passing blank padding through the full sprite hook cost more than the original plot itself.

- [local: Exolon native trap] The first relocated padding copy at 3D80 passed the simple model but
  stopped native JNext after 17 updates. The 3Dxx DivMMC automatic-paging region is a suspected cause;
  moved to 3600; native trials now run 180 updates and match state at every update. The cause remains an inference.

- [local: Exolon pulse spacing] Particle rendering is inside the 95A3 noise oscillator. Identical
  FE values and original CPU speed do not prove sound pitch; compare edge timestamps as well.
- [local: Exolon pattern publication] Six spare patterns suffice for four-part figures; prepare
  all parts before one attribute burst. Unit and replay oracle checks catch displaced/changed parts.
- [local: Exolon checkpoint effects] Mid-game native fixtures must seed active XOR effects;
  otherwise their first erase is mistaken for a new draw. Normal menu starts reset the pool.
- [local: Exolon loading art] The TAP screen is compressed. Execute its original 8001 decoder
  from the sixth block; looking only for a6914-byte tape block misses it.

- [local: Exolon native snapshots] JNext mem/ram.bin includes a 0x40000 physical offset before
  ordinary Next RAM. Assert the hook-code signature before reading page 24 state; an all-zero
  free-pool count at every checkpoint identified the first check's wrong offset.
- [local: Exolon menu inspection] The original menu uses the same star plotters as play;
  zero visible sprites is not a valid reset assertion. Check stale multipart actors and the
  source-pixel replay while retaining original animated stars.

- [local: Exolon ROM audit] A static read mismatch is not automatically a consumed value.
  B0B7's original self-copy LDIR is a delay. Keep a per-read guard and full-function ABI/time
  proof before exempting 2000..3FFF; never broadly waive unknown ROM consumers or final flags.

## Friction

- reuse: [local: Exolon intake] Reused the private 128K recorder and shared survey.
- retries: [local: Exolon intake] A48K-only recorder failed before producing a recording; retained logs.
- environment: [local: Exolon intake] Own clone and outputs only, existing pilot Python environment.
- hand-rolled: [local: Exolon intake] Input schedule is specific to the original menu and Kempston mode.
- scratch: [local: Exolon intake] Private intake scripts retained with source/hash evidence until engine integration.

## Stage log

- 2026-11-08: fresh main clone/fetch, exact source/hash inspection, continuous 6,000-frame recording;
  initial original screenshots and AY port census. Survey and private prototype begun; no package.

- 2026-11-08: drawing/colour prototype, native appearance checks, corrected moving recording,
  reset and painter ABI tests, partial replay proof; timing and remaining coverage work continue.

- 2026-11-08: added large actor 24, tiny projectiles, atomic multipart publication and an independent pixel oracle; native sound test found an explosion pulse-spacing gate. Stage held for further design; sequential batch continues. No final verification stamp.

- 2026-11-10: refreshed main, profiled individual particle scopes, shortened effect entry with
  the shared speed latch. 128 ABI cases, both 450-frame oracles and 4 broken-build controls pass.
  Three new native Enhanced experiments retain pulse outliers; no release claim or push.

- 2026-11-10: corrected the player probe to exclude loader MMU20, completed twelve gated pace
  and sound pairs plus original-only controls, integrated the engine/record/loading/trainers,
  added independent edge/pool/clock fault checks and editable imports, and passed eight
  disposable-card actual-loader runs. Full frozen verification is next.

- 2026-11-10: first full run passed 8494 frames/mode and all unit cases, but the final static
  ROM audit flagged two long self-copy delays. Classified/proved the original B0B7 routine,
  added a guarded read exception and four negative controls; runtime and NEX bytes unchanged.
  A new frozen full proof is required; the failed log remains intact.

- 2026-11-10: full frozen verification passed/stamped; two recordings, all hooks/R/RAM and
  independent pixels, ABI/clock/pool/negative cases. Native 24000-frame lifecycle/soak and
  eight final-hash loader runs pass. Final package/source contribution and packaging handoff
  prepared; no hardware test or push.
