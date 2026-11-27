# The Great Escape (Ocean, 1986)

## Next session

Stage 3 (prove + deliver) on current main: branch `add-great-escape` (worktree wt-great_escape), ported 2026-11-26
from the pilot branch `game/great-escape-release` (7e4f0f1, base cc60245). Record great_escape; reference folder
great_escape/ (snapshot, four recordings, input/, art/period-v2-jon = Jon's 2026-11-09 sprite edits: 391 pixels,
colours.bin only). Every output = automap_off(the engine's build with that art); with the period-v1 art the engine
rebuilds the pilot's recorded bytes exactly.
Codex review 2026-11-26 (10 findings) fixed: hooks counted only when entered, every event has an oracle case, a
missing-site control; DDMA only on core 3.03, no DMA port write in the CPU fallbacks; writes to Sinclair's ROM pages,
the colour/world/timing pages or the alt ROM view fail; negative controls each by their own failure (R control
changes only R, speed control drops the NR 7 restore); Layer 2 show/hide tested from both states with a control each;
autosaves stripped; a recording with no hook fails; boot check against the view at F068; the auto package carries
McQueen with "needs Enhanced" (OPR1 via nxcout `needs`) and no CPU-only option; --allow-60hz refused (312-line pace).
Open: the full verify + stamp on the fixed engine, release package + real loader checks, OverSpec play review by
Jon, PR. Recolour entry points (RECOLOUR/recolour) not yet: import_sheets() is this engine's painting route.
Set NEXCLASH_GREAT_ESCAPE_ART or place the four painting binaries beside great_escape.z80.

## Source and design

`Great Escape, The (1986)(Ocean).z80`, 48K, MD5 ff5eae3b61188cb5095a6177c3c34a06.
Its loader restores registers and relocates 39637 changed bytes, 5B77..FADF. Execute exactly
40833 instructions / 857190 T-states to F068 before applying hooks. Both normal and NEXLOAD
boot must reproduce all registers including R and all RAM at that boundary. The emitted NEX
retains archive banks and performs the same 5E00->5B00, 9FE0-byte relocation at startup; hook
and trainer sites are translated +0300 into its input range. Register restoration then joins
F068 exactly. This keeps the NXC site table small without embedding the relocated game. Original loading
screen SHA256 7eff616121a684dd0c0e9e7642181129aadb2dc9951c8a4c804c86dd8c55803d.

Default is the original monochrome presentation, with no drawing hooks and no clash-fix claim.
Enhanced is optional and off by default: varied RAF blue, brown, cream and olive prisoner
clothes; restrained guard uniforms; timber, slate roofs and dusty ground. Native silhouette,
mask, linework, foreground occlusion and draw order are retained. No white outline is added.
McQueen player is a separate off-by-default cosmetic outfit requiring Enhanced. It never
repaints a guard disguise. Six prisoner identities retain distinct outfits despite shared art.

This engine uses a Layer 2 companion to the native composed buffer, not independently ordered
hardware sprites. Filmation-style depth and occlusion come directly from the native masks.
All 38 actor descriptors and 16 item descriptors are exported. The three original keys share
one bitmap but select red, yellow and green palettes by item ID. Editable sprites, items, interior tiles and
four world sheets use enlarged flat pixels. Import rejects antialiasing, outside-silhouette
paint and conflicting shared-key edits; an unchanged export/import is byte-identical.

### Painting a thinner outline

Paint a mask-only figure or item pixel with the exact sheet grey `#30343a` to reveal the
colour already drawn behind it. Native ink must keep a paint colour. One edit propagates
to every use of the source pixel, including the three keys. Conflicting edits are rejected.
Export shows erased pixels in canvas grey, so they can be painted back in a later pass.

`colours.bin` reserves 255 for these erasures. Bright paint occupies 0..127, so the sign
flag after the existing outfit/key OR tests the marker in one branch. Layer 2 index 255
already maps to transparent magenta (RGB9 0x1C7, NextReg 0x14 = 0xE3). Writing that index
would expose native paper where the game's mask cleared the bitmap. The halo kernel skips
both the bright and dark canvas stores. Foreground clipping, native bitmap stores and final
publication follow the normal path. Only a colour map containing the marker selects the two
assembled overlays in page 26. All five recorded outputs with period-v2-jon art retain their hashes.

## Hooks and memory

Techniques: patch.pace-limiter, patch.restore-speed, patch.preserve-r, verify.update-locked-pace.

Sixteen hooks: A9D0/6B5A/BC62 tiles; six A9FC..AAA6 scroll prefixes; E2A2/E102/E29F
figures/items; EED3 native screen copy; 9DC2 final publication; AEB8 searchlight mask painter;
A50B dialog. A50B reveals original ULA confirmation/result text; a complete subsequent play
frame restores Enhanced. Original logic, input, morale, beam movement and beeper remain native.
Only pure drawing runs at 28MHz, with hlib_pace original-cost windows and outside-work debt.
Shared hlib_iff, HLIB_SPEED_IN_ABC, HLIB_SPEED_OUT and hlib_r preserve incoming IFF, speed and R.
The original game runs DI; both IFF states and all four incoming clocks are tested anyway.

Native canvas F290..FF50, 24 bytes per row; tile IDs F0F8..F28F. Actual viewport is 184x128 at
56,16. A7C7 contributes vertical fine offset, A7C8 selects a half-byte offset. Contextual tiles
use the native world block pointer, including BC62's alternating-register prefix. Six scrolls
move both bright and dark colour canvases. Live native foreground masks and clipping stores
control every pixel. The three key palette bases are selected independently of actor roles.

Lower original ROM page27, resident upper page24, private code/data page26. Layer 2 pages28..33;
bright/dark canvases34..41; compact pixel pools42..85; world/timing86..89; staging90..93.
Highest game bank46, complete hidden ROM bank47: all modes fit a 1MB Next. Code stays below
1400; helper block1A00..1BFF; cache tags1400..172F; shared library1800; pace/state1C00..1F6F.
Resident code remains below3D00 to avoid DivMMC trap addresses. No shared card is modified.
Packaging uses the current patch repository writer and OPR1: McQueen needs Enhanced,
and the outfit combines with all trainers. CPU-only diagnostics are not in the release menu. No shared loader or writer is modified.

## Performance and DMA

Clean contextual tiles are reused; moving figures invalidate exact affected cells. Clipped
column23 spill and F28F starts invalidate conservatively. Figure rows map their colour source
once and update bright/dark pixels together. Unchanged lighting and dirty spans reduce copies.
The native searchlight painter has an independently measured 4096-state timing table; its
movement, detection and penalties are outside the accelerated region.

Release: ordinary DMA on every core (policy 1). The core 3.03 blitter path (policy 2) froze the game in OverSpec
(core 3.03.03) right after the key choice (2026-11-26, Jon's review; CPU in the ROM tape loader); it was only ever
model-tested, never run on hardware, so it stays in the code unused. Ordinary DMA and short CPU copies; hardware IM2
and explicit diagnostic builds use CPU fallback. Long CPU copies tick the limiter
between chunks. JNext 1.1.104 reports core0x32, so its measurements exercise the older-core path.
Model core0x33 and hardware-IM2 cases are tests, not physical hardware evidence.
CPU-only diagnostics are materially slower and are excluded from the release menu;
the 2% target and tables below refer to the normal Enhanced DMA path.

Pace is measured at B5D4 with IY=8000, the player's own update. Each scene has three
100-update automatic-walk windows and three independent stationary trials. The latter hold
SPACE at different update boundaries and retain exactly one position in one room. Every
sample agrees in x/y/z/R. Positive is slower; negative is faster. Percent elapsed-time delta:

| Scene | Automatic windows | Stationary trials |
| --- | --- | --- |
| Quiet | +1.812, +0.595, +0.601 | -1.867, -1.553, -1.521 |
| Busy | +0.571, +0.093, +0.639 | +0.805, +0.754, +0.664 |
| Searchlight | +1.637, +1.335, +1.286 | +1.540, +1.310, +1.281 |

All 18 windows are within 2%; this is not a claim of zero slowdown. Native sound event counts,
values and call sites agree; no FE sound write occurs at an accelerated clock. The aligned
copy allowance is calibrated across stationary and moving cases; shifted copying includes
measured contention. Independent hook-overhead checks guard double charging in debt accounting.
Native A11D..A12E beeper checks at nine contention phases have identical register and 37-write
traces at equal starting phase. Live FE writes remain at 3.5MHz. This is a 48K beeper game.

For the round-two halo art, JNext 1.3.5 gave the following elapsed-time differences against
the original at the same player updates. All 18 windows were within 2%. Position and R matched
at every sampled update, as did beeper values and call sites. The three isolated figure/item
hook trials (E2A2, E102, E29F, model core 0x32) changed by +1.5, +4.5 and -10.25 base-clock
T-states respectively against the same round-two scenery with the previous black outlines.

| Scene | Automatic windows (%) | Stationary trials (%) |
| --- | --- | --- |
| Quiet | +1.862, +0.560, +0.596 | -1.955, -1.627, -1.587 |
| Busy | +0.596, +0.058, +0.653 | +0.789, +0.756, +0.659 |
| Searchlight | +1.880, +1.564, +1.579 | +1.799, +1.563, +1.526 |

## Proof and coverage

Independent native geometry matches both supplied recordings: 47658 frames, 369765 tile calls,
23507 figures, 10017 publications and 2251 scrolls. Persistent actual-hook trials cover the
same recordings, plus a 5000-frame native abort/no/restart recording and a 500-frame controlled
result fixture. The latter forces the native exit branch with the required item IDs; it is
not a natural completed playthrough. Final selftest passed and stamped 2026-11-09:
53158 frames, 457675 hook executions, all 16 hooks covered and no mismatches.
All 536 unit cases pass, including the four deliberately broken controls. All five
recorded output hashes rebuild exactly; all 13 build variants pass the complete ROM-path
audit over four recordings. No game ROM reads occur in these recorded paths; boot checks
separately verify the full hidden ROM and exact restored native state.

Verification compares all registers including R, game RAM, native bitmap coverage, bright and
dark colour canvases and final Layer 2 positions. Interior LDIR/LDDR entries must follow their
original BC countdown; arbitrary interior entries fail. Unit cases cover every hook, clock,
IFF, core gate, CPU/HW-IM2 fallback, phase/mirror/clip/height, canvas edges, all items, costumes
and disguise. Position, transparency, R and speed deliberately broken builds must be caught.
Full hidden-ROM/boot checks include all options. Raw-loader replays start ROM observation at
the separately proven F068; decoded result fixtures receive the full audit from frame zero.

Final public NXC: nine real .NEXCLASH loader trials on disposable NextZXOS 26.11 card copies,
including default, Enhanced, each trainer, all trainers, both outfits and the automatic
Enhanced dependency. Every reconstructed NEX is byte-identical, trainer bytes are correct,
play advances and sound stays at 3.5MHz. Fifteen host option/trainer combinations pass.
Live soak: original 30002 frames/3 restarts, Enhanced 15002/2, private CPU diagnostic
15002/2, without emulator errors. Whole-run counts are stability evidence, not pace tests.

## Trainers

Archive POK MD5 7f61c780cc1d94e0fc2407c4e34206a4. Three verified choices, all off:
Runtime: Infinite morale A0E3:90->B7; No other people C52B:C0->C9; Pass through doors B368:C0->00.
Package input addresses are A3E3, C82B and B668; the startup relocation carries these into place.
Archive morale NOP preserves incoming carry and can empty morale; OR A clears it correctly.
1130 native morale cases pass, including incoming carry. Native spawn/door trigger tests pass;
the rejected-door fixture uses a recorded door context with rejection Z cleared.
Historical duplicate A0DE and C421 entries hit instruction operands in this release and the
checked alternate archive snapshots; they are not shipped as separate working cheats.

## Lessons

- [local: erased halos] Preserve the colour at the destination while still applying the native mask to the
  one-bit canvas. The red-key unit starts with bright 7 and dark 135 under two erased pixels. Removing the
  skip must change exactly those destinations to 255 on both canvases, including mirrored and page-crossing draws.
- [local: original relocation] Exact native register restore and relocation avoid inheriting loader workspace corruption. Retain raw source banks in the NEX and relocate at startup so NXC SIT1 holds only small patches.
- [local: world context] The same bitmap bytes serve different materials; colour by native block and subcell identity.
- [local: clipped damage] F28F and column23 spills require wrapped canvas access and conservative cache invalidation.
- [local: camera offset] A7C7 is not merely a horizontal shift; full publication is necessary on its changed view.
- [local: key identity] One shared key bitmap needs three item-selected palettes to retain gameplay colour information.
- [tool nexclash/great_escape.py] Native block-repeat countdowns distinguish legal LDIR interiors from stray entry.
- [local: dialogs] Abort confirmation and result messages need the ULA revealed; resume colour only after a complete frame.
- [local: trainer carry] Replacing SUB with NOP leaves an incoming carry alive; test flags as well as the apparent value.
- [local: palette quantization] Pack rounded RGB9 components; truncating already-quantized RGB silently darkens the art.
- [local: pace scope] Starting in a quiet room does not make a long automatic walk a stationary quiet-scene test.
- [local: option capacity] The old writer limits the menu to two sets; use current OPR1 rules when combining more options. The release retains the outfit dependency but omits the slower CPU-only diagnostic option.
- [local: contention budget] Calibrate drawing allowances against both stationary and moving scenes; a full isolated-copy contention allowance can overcharge whole-update debt.
- [tool nexclash/great_escape.py] A captured-state hook case passes with the hook removed: native code from the site gives the original's exact result. Require the hook's entry to be seen (state_trial `hook not entered`) and keep a missing-site control.
- [tool nexclash/great_escape.py] A model that always grants the blitter cannot test its fallbacks: grant DDMA by the modelled core and refuse any DMA port write in the CPU fallbacks.
- [tool nexclash/great_escape.py] Comparing the 64K view misses writes to physical pages (a ROM page restored to its slot afterwards): guard the immutable pages at the write.
- [tool nexclash/great_escape.py] A negative control counts only by its own failure; a mutation must change one thing (the R control once also changed A and F).
- [local: DDMA unproven] A DMA path the recordings' machine never takes (JNext reported core 0x32) is only model
  evidence: the 3.03 blitter path froze the game in OverSpec. Ship the path an emulator or board has run; run each
  core gate's path once before a release.
- [tool nexclash/great_escape.py] The halo overlay install copied the whole code blob over bank 13 and put the
  assembler's DMA policy 2 back over the release's 1: Enhanced and McQueen froze again in OverSpec (2026-11-27,
  Jon), while the verifier passed because it grants the blitter whenever policy 2 asks. The install now writes only
  the overlay bytes and the build asserts the policy byte.

## Technique use

- detect.buffer-layout-producer: helped: recovered native canvas, tile map and final viewport.
- detect.drawing-parameters: helped: native phase, mirror, clipping and foreground masks.
- detect.graphics-record-layout: helped: all actor and item descriptors, including shared keys.
- patch.pace-limiter: used: native drawing windows, incremental debt and long-copy ticks.
- patch.restore-speed: used: incoming speed latch, restored on every native rejoin.
- patch.preserve-r: used: native M1 deltas and R compared at every hook.
- verify.update-locked-pace: used: B5D4/IY8000 rather than drawing frequency.

## Friction

- reuse: [none: existing intake tools suffice] Native masks require a game-specific pixel oracle.
- retries: [local: lifecycle] Opening play did not expose the covered confirmation text; explicit abort/restart did.
- environment: [local: JNext keys] CAPS SHIFT is membrane key 0,0 in JNext scripts, not the name CAPS.
- hand-rolled: [local: colour companion] Shared contextual tiles cannot be represented by one flat source-address palette.
- scratch: [local: evidence scope] Game-specific probes remain in private evidence; no game data enters the source zip.

## Hardware checklist

No hardware or CSpect run. On a 1MB Next check default/Enhanced, both player outfits, disguise,
all three keys, loading, day/night/searchlight, foreground occlusion, room changes, abort/restart,
result text and beeper. Exercise CPU fallback separately as a diagnostic. Return-boundary
pixel checks do not prove raster behaviour. Final user play review remains due.

## Stage log

2026-11-09: native canvas/figure oracle, contextual colour renderer, profile-guided drawing
optimization, clipping/cache repairs, item/outfit importer, dialog fix and targeted lifecycle tests.
Upstream cc60245 unchanged at the pre-release refresh. Final selftest and ROM audit passed;
verification stamped. Nine real-loader cases and sustained live restart trials passed.
Source and package are ready for final visual review and upstream integration; no push made.
- 2026-11-26: ported onto main (add-great-escape), Jon's edited art in, Codex review (10 findings) fixed; full stamp, package, loader checks and Jon's play review next.
- 2026-11-26: Jon’s 1,000 round-two outline edits imported as 966 distinct erased halo pixels. The four
  painting binaries round-tripped exactly. Matched JNext captures showed tan ground and olive speckles
  through the erased outlines. The quick play1 and controlled-result replays passed (2,500 frames,
  22,464 hooks), including ROM-path checks on 13 builds. All 551 captured-state unit and control cases
  passed across all 16 hooks. The full four-recording release stamp was outside this art check.
- 2026-11-27: Jon's play of the halo build froze with Enhanced and McQueen right after the key choice (OverSpec).
  Cause: the halo overlay install restored DMA policy 2 (blitter) in bank 13. Fixed (overlay bytes only, policy
  asserted); a one-byte policy-1 patch of the halo build played past the key choice in both.
