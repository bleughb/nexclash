# Bubbler (1987, Ultimate Play The Game)

## Next session

Stage: 3, verified software candidate; packaging and independent clean rebuild remain.
State: owner approved the current artwork as-is ("bubbler is good"); live editable PNGs are protected.
Branch: `game/bubbler-release`; refreshed main `6dbfaad` after ending all proof processes.
Inputs/evidence: enclosing run `files/`, `rzx/`, `work/`, `jn/` and `logs/`.
Start with: `../logs/final-record-verify.log` and `../work/final-generic-proof/`.
Open: independent source-bundle rebuild, then packaging handoff. Physical hardware remains untested.

## Inputs and decisions

Techniques: patch.iff-safe-read, patch.restore-speed, patch.pace-limiter, patch.preserve-r.

Target: `Bubbler (1987)(Ultimate Play The Game).z80`, MD5 `85d7841306333321838d372ea8797ff2`.
The supplied archive is a 48K loader snapshot at ROM IM1 entry, returning to BASIC PAUSE.
Its BASIC program eventually calls F000, which complements 37,300 bytes from 5E00 and jumps to 5E00.
The original TAP and matching archive POK are retained beside the snapshot outside the checkout.

Colour source: MatGubbins' `bubbler256.GFX/GFA/GFB/CFG`, snapshot and reference pictures.
The author and boot requirements are stated in the supplied `bubbler.txt` and `readme.txt`.
Credit: **Enhanced colours: MatGubbins (Spec256)**. The menu name will be **Enhanced**, off by default.
Jon approved the first pass and editable sheets as-is on 2026-11-07 ("bubbler is good"). Preserve the live PNGs.
Default preserves the original appearance. No new outline or repainting is authorized for default.

Original pace in steady scenes: within 2%; faster busy scenes are allowed where the original slows.
The build must not run slower than the original in the tested quiet or busy scenes. Report them separately.
The prior Filmation builds' cold-redraw debt tradeoff is not automatically acceptable for this task.

## Source match

Observed: after the original inversion, 34,735 bytes in 5E00..E5BA match the conversion snapshot exactly.
The twelve differing bytes are original runtime state: random seed, counters, attribute rectangle parameters
and self-modified operands. Each has an observed original writer; no unexplained program difference remains.
All 8,623 bytes in the separately checked graphic ranges match, including the main masked figures.
E5BB..F1BA is the original 24-byte by 128-line drawing buffer, not alternate program code.
Evidence: `../work/colour-source-match.json`, produced by `../work/compare_colour_source.py`.
No alternate archive release was needed.

## Rendering observations

- The original composes into E5BB..F1BA using masked plots and copies a visible strip to the ULA.
- B43C resolves an actor's image from type/animation tables, clips it and uses the masked plotter.
- C59A and C5F2 handle scenery geometry, clipping and the original in-place horizontal reversal.
  C741 is a second, occluding scenery path and must also be reproduced.
- E57F clears the back buffer; E517..E57A publishes the visible strip with a stack-based copier.
- A902 is a screen-scroll helper. The first short recording misses its caller at 6206; classify and cover
  that path before declaring complete caller coverage.
- The first recorded boot/menu/play trace replays without desynchronization. It is intake evidence, not
  a release proof or full-game coverage claim.

The colour preview runs the original plotters on palette bitplanes and checks a separate monochrome
back buffer. It produces PNG proposals only. It does not establish Next runtime speed or raster safety.
The clean 10,000-frame trace checks all 939 full and 499 partial copies, including 6,800 plots,
939 background saves, 935 restores, 55 column shifts and the original scrolling transforms.
The explorer recording with snapshot resets is excluded from proof; the continuous input trace replays cleanly.

## Current implementation and evidence

The startup preserves the original encoded payload and executes its unchanged F000 inversion.
The original JP operand at F010/F011 temporarily redirects through a nine-byte bootstrap bridge,
then is restored before entry 5E00. Normal and NEXLOAD models match all registers/R and every
48K byte at that exact boundary; no stack exclusion. The original screen is supplied from the
archive snapshot. The bridge reduces the local NXC site table to 407 bytes instead of requiring
37,300 changed decoded-source bytes. All seven actual dot-loader selections have passed on
private 26.11 cards: default, Enhanced, all trainers together and each trainer individually.

Default preserves the original picture and uses only CE10/CE19 around the sound-free renderer,
with shared pace K103 and incoming-clock restoration. Enhanced uses a private indexed 192x128
canvas, original ordered mask/OR/XOR geometry, saved rectangles, all scrolling transforms and
double-buffered Layer 2. Its 36 hooks retain every original game instruction and compare R.
Original code time is measured separately from added colour work. Renderer/copy/scenery K values
are 103/92/101; no pace debt carries between windows or updates. Beeper, HALT and deliberate
original delays remain at the incoming clock.

Prototype proofs pass: clean 10,000 frames plus labelled 21,901-frame five-stage trainer coverage,
full game RAM/R at hooks, independent original bitplane colour oracle and final publication.
All 1,328 direct ABI cases pass. Generic auto retains cumulative per-mode captured contexts for its negative controls: a
mid-game trace may begin after a restore and its first restore sample can be a no-op. Every
recording still has an independent full replay result. The generic verifier additionally checks the full published
49,152-byte Layer 2 image, not only the private canvas; quick 2,000-frame auto passes 704 Enhanced
ABI cases and six broken-build controls (R, MMU, speed, plot, restore and preparation).
Nine frozen native states match all 48K game RAM and both colour canvases, excluding only exact
emitted patch bytes. No dead-stack mask is used.

Native original-update pacing covers nine scenes and three raster phases: all 27 whole/steady
trials are within 2%, with steady differences -1.5885% to -0.074%. Cold 20-update bins are reported
separately, including small positive differences; do not claim every individual update is faster.
Four native beam audits cover 10,117 hook calls and 592 publications: every observed caller was
IFF0, every hook DI was redundant, no hook EI occurred, and every valid bank switch was outside
y8..119. The actual game disables interrupts; these are not newly introduced masked windows.

The 20,000-frame native archive soaks pass original/default/Enhanced: each reaches ten deaths
and two gameovers, then restarts. Sound writes and player updates never run at the accelerated
clock. Frame-scheduled input means these soaks are stability evidence, not pace comparisons.
See `../work/native-archive-soak.json`; menus/loading/gameplay pictures were inspected.

Owner sheets: `../out/BUBBLER_PAINTING_SPRITES.png` covers all 58 distinct animation/effect images.
`../out/BUBBLER_PAINTING_SCENERY.png` covers twelve scenery images reached in the first-level trace.
Both have unchanged-import checks, layouts and immutable copies under `../work/owner-baseline/`.
Never regenerate either live sheet. The moving sheet has 34 RGB entries; the shared importer now
reads the full declared palette rather than silently restricting import to its first 15 colours.
The added >15-colour round-trip/single-pixel checks, private Chuckie Egg canary and tools suite pass.
Missing reference games are explicitly skipped in the tools log; no other game's build is changed.

The extended next-level-trainer trace reaches all five stages in 21,901 cleanly replayed frames.
It is labelled trainer coverage; it does not replace the unmodified original recording. See
`../work/stage-coverage-extended/result.json` and `../rzx/next-level-complete-coverage.rzx`.

The death-refresh difference is now causally accounted for. Both builds enter original HALT E449
with R183. Original waits 9,020 HALT fetches and candidate 15,479; the extra 6,459 modulo 128 is
exactly the observed R offset 59. Later E491 HALTs take 17,066 fetches in both. No hook register
mismatch was concealed. Evidence: `../work/halt-cause.json` and `../jn/halt-cause/`.

The indexed renderer's primitives match 92 clipped/stippled/scenery cases. Copy/fill passes
88 cases per CPU/ordinary-DMA backend, saved rectangles and fractional scrolls pass both paths,
and all 36 publication cases compare complete inactive/active buffers. Ordinary DMA uses retained
rearm for row copies; backward overlap uses a private scratch page. No DDMA extension is emitted.
The CPU fallback's modelled full preparation is at most 523,613 T at 28 MHz (18.701 ms); ordinary
DMA CPU instruction cost is at most 91,459 T, excluding hardware stall. Those are model counts,
not physical transfer timing. Core 3.03 2D would suit opaque row copies, but cannot replace original
mask/XOR mixing. It is not selected without a native/hardware DDMA model; ordinary DMA remains
compatible on that core. Hardware IM2 conservatively selects CPU fallback. A native 120-update quiet fixture takes
24.94% longer on CPU-only fallback; it is not a menu option and is outside the ordinary-DMA pace
claim. Injecting capability 2 while retaining ordinary commands is cycle-identical to capability 1.

Generic integration now includes registry/auto, compiler/profile, complete separate v2 sheets,
reciprocal recolour and record 205. The existing live v1 sheets are never regenerated. Native v2
palette indexes above 15 use explicit integer arrays in JSON; legacy nibble strings are unchanged.
Duplicate RGB swatches preserve the existing semantic index on an unchanged import.

The shared ROM audit accepts an explicit, separately boot-proven runtime entry. Bubbler's clean
recording reaches 5E00 in frame 33; only the replaced BASIC prefix is excluded. Later original ROM
calls remain checked, and a missing entry is incomplete. Synthetic controls reject a post-entry
ROM mismatch and a missing entry. Recordings already starting in decoded game code check every
frame. This is not a blanket known-address waiver.

## Final software checks

The final generic record has checked and verified stamps dated 2026-11-07. Assembly/profile,
default/Enhanced rebuild and reciprocal recolour pass. Across the two recordings, the default
checks 6,247 hook returns; Enhanced checks 67,817 returns, 3,333,341,184 RAM bytes and 4,226 full
canvases. Every register/R and complete published image agrees with the independent oracle.
The cumulative direct matrix reaches 128 default and 1,824 Enhanced ABI cases; all six Enhanced
broken-build controls are rejected. The original 26.11 ROM paths pass after separately proven boot.
Each archive trainer is tested at its real instruction and branch. Both modes fit bank 47, retain
the original loading screen and full hidden ROM, and all cheats and Enhanced are off by default.
Retain the measured ordinary-DMA backend and functional CPU fallback; no DDMA hardware timing claim.
No hardware claim; no shared card writes or pushes.

## Lessons

- [local: Bubbler loader] Observed: the archive complements 37,300 bytes before game entry. Compare a decoded execution state with the conversion, not the encoded loader RAM.
- [local: Bubbler conversion provenance] Demonstrated: all twelve apparent program differences have original runtime writers; graphic ranges match exactly. Evidence is retained in the source-match report.
- [local: Bubbler rendering] Observed: masked actors and scenery compose into a 24-byte stride buffer, then a separate stack copier publishes it. Screen-writer ranking alone initially emphasizes the copier and menus.
- [local: scenery occlusion] Demonstrated: the C741 partial scenery path explains a three-pixel discrepancy that persists even when an isolated actor plot matches. Final-copy comparison catches missing intervening painters.
- [local: conversion geometry] Demonstrated: unpainted GFX bytes can contain a later shifted walkway. Use original mask/ink geometry for source indices 0/255; import actual paint only inside the original footprint.
- [tool nexclash/coloursheet.py] Demonstrated: the sheet importer truncated palettes at 15 entries. It now uses the declared palette length, with unchanged legacy behaviour and explicit high-index tests.
- [local: native start state] Observed: fixed video-frame snapshots can land in the game's pause loop. Capture the original player-update boundary for pace trials instead.

- [local: saved rectangle row count] Original save and restore branch to DJNZ before the first pixel copy. Header height N copies N−1 rows; treating it as N left stale or overdrawn pixels.
- [local: death HALT refresh] Native E449 fetch-count difference 6,459 modulo 128 explains the complete R offset 59. The repeated E491 phase then advances R identically; preserve this distinction from hook R correctness.
- [local: overlapping colour transfer] Ordinary forward DMA cannot implement an overlapping right shift directly. Copy backward chunks through a dedicated scratch page, or use the verified LDDR fallback.

- [tool nexclash/coloursheet.py] Palette indexes above 15 must serialize as explicit integer arrays; variable-width hex loses pixel boundaries. Preserve duplicate-RGB semantic indexes during unchanged imports. Both behaviours have golden checks.
- [tool nexclash/nextboot.py] A replaced BASIC loader prefix is not a runtime ROM path. An explicit entry boundary requires separate exact boot proof, records its first frame, rejects missing entry and still catches later ROM faults.
- [local: compact loader bridge] Preserve complemented archive bytes and rerun its original inverter; restore the exit operand and all registers/R before game entry. This keeps the patch site table within the real loader limit.
- [local: original ordered drawing] Persistent saved rectangles, in-place flips, malformed mask/ink bytes and partial death copies all matter; final front-buffer comparison catches errors that private-canvas-only checks miss.

## Friction

- reuse: [none: existing survey, scan, recorder and simulator helpers are being used]
- retries: [local: palette preview] Repeated full-buffer checks exposed the missing C741 path and scrolling transforms; retain the final passing log and scope separately from earlier diagnostic failures.
- environment: [local: isolated game checkout] The fetched baseline and private input hashes are recorded before development.
- hand-rolled: [local: conversion provenance] The game-specific comparison explains its inversion and writable operands.
- scratch: [local: review evidence] The source-match and palette-preview probes remain with this game's reproducible evidence.

## Technique use

- patch.iff-safe-read: used: required interrupt-state contract for new hooks.
- patch.restore-speed: used: required incoming-clock latch, including nested hook levels.
- patch.pace-limiter: used: steady original pace with separately measured busy-scene behaviour.
- patch.preserve-r: used: shared refresh save/restore and R comparison at every changed CALL.

## Stage log

- 2026-11-07: verified archive/conversion provenance, completed ordered colour preview, obtained first-pass approval and delivered protected editing sheets; default hooks pass initial semantic/ABI/native checks. Enhanced runtime and final release remain open.

- 2026-11-07: approved runtime now passes full prototype replay, 27 native pace trials, exact native RAM/canvas proofs and 20k archive soaks. Generic auto/recolour and compact loader bridge work; full generic proof and final packaging remain open.
- 2026-11-07: final generic record verified and stamped against frozen main 6dbfaad plus the recorded local changes. Seven 13,500-frame private-card loader selections passed; final metadata refresh changes only INF1 and explicitly reports the slower emergency CPU fallback. Source bundle and independent rebuild are the remaining delivery gate.
