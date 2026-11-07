# Herbert's Dummy Run — Mikro-Gen 48K

Private v1.3 implementation for the exact snapshot MD5
`b5570016396fc2ec823da33a2a095ba3`. Base refactor commit
`a8412b58f662a3301c68ef1414f777258dfcf57b`. No hardware execution. Owner played v1.0;
v1.1 was owner-played; the v1.2 artwork preview was approved. v1.3 imports the owner's solid-colour edits; owner play of v1.3 remains pending. Current evidence is in the adjacent run's REPORT.md and
ENHANCED.md; v1.0 remains in REPORT-v1.0.md and PROOF.md.

## In this repo (2026-11-06)
Techniques: detect.gameplay-screen-readers
- Built with tools/build_herbert.py (not yet an engine in engines.py: its verifier, negatives and clock matrix are
  the pilot's scripts, not ported; the engine contract's verify / unit_tests / CMP are the next step).
  `tools/build_herbert.py GAME.z80 -o OUT.nex --work DIR [--enhanced] [--screen PICTURE.scr]` gives, with the tape
  picture, byte for byte the published .nxc 1.3 --bare default (537f88c7) and Enhanced (dbb38ec4).
- No game pixels are stored. The paint routines' bytes and every image are read from the player's snapshot; the
  owner's figure paintings (herbert_parts.json) and the scenery paint (herbert_scenery.json) hold one colour digit
  per ink pixel of the game's image, in pixel / bit order, and the build lays them over the image it reads.

## Family finding

The first 45 normalized instructions of Herbert's OR plotter at 8CA3 match
Wally's A83D at 41 positions. Its masked 16x16 plotter at 93BA similarly matches
Three Weeks BA5F at 41/45. Shared stack-fed pixel operations and clean/back-buffer
composition support the same interception method, not interchangeable engines.
Wally uses Layer 2; this build uses hardware sprites. Three Weeks' separate
foreground-object list is absent here: the complete recorded original back buffer
is reconstructed from the frozen clean room plus the intercepted plots in order.
Any unaccounted foreground writer would fail that comparison. Later masked plots
cover earlier figures with their complete masks. Default scenery stays in the ULA;
v1.2 Enhanced adds a validated colour overlay below the sprites.

## Rendering and state

Playfield y48–191; clean buffer 6D00–7EFF, back buffer 5B00–6CFF. Reset 96BC
freezes the clean image; edits after reset belong to the following game update.
Five entries cover OR 16x16, masked 16x16, Herbert 16x32 and two alternate 16x32
paths. B32 is intercepted at 9330 after the original self-modifying base load.
The direct-screen XOR path 8D02 is panel-only in the code/census, at y0/8/24.

Original drawing and game logic still run. Plot entries copy live images, so later
in-place mirrors cannot change an earlier figure. Attribute operations use a
shadow. The original screen copy executes at 28 MHz into a hidden pixel page;
its original R delta is restored at 97DA. The displayed screen contains the
frozen clean room and sprites in plot order. Mask bits provide opaque black
details; OR images flood-fill enclosed holes black. There is no outside rim.
Colours are per-image reference inks from both recordings, with Herbert yellow;
the original scenery and panel colours remain. v1.1 adds an optional Enhanced set,
off by default, with pose-specific painting and complete live-image validation.

Two 64-pattern halves alternate. New images are uploaded into the inactive half;
attributes and clean screen publish in the border, before the playfield beam.
Port 303B explicitly selects sprite zero before the bulk 57 attribute transfer.
All 128 sprites are hidden on clear/setup. Cache entries share images by source
address through an allocation table and compare every raw byte and the mask type: in-place mirrors cause a miss rather than stale art. The table assigns 137 source
chunks to 33 slots with no collisions among the complete observed image set of
any one room. Unknown addresses have safe hashed slots. This avoids moving a
performance problem from the sports room to the barrel room when changing a hash.

Each hook restores its incoming CPU speed and R. No added DI/EI instructions:
the original observed execution already has interrupts disabled. The original
beeper runs at 3.5 MHz; there is no AY music. The limiter repays plot logging
outside the copy window, using a base line budget less the logged-figure count.
The clean copy uses unrolled LDI rows, giving the atomic publish a wider safe
border window. Game delays, movement and sound routines are not patched.

## Reproduction

Use the pilot virtualenv, PYTHONDONTWRITEBYTECODE=1, and TMPDIR inside this run.
The standalone builder verifies the source MD5 and every patch-site byte:

```
python -B tools/build_herbert.py SNAPSHOT -o OUTPUT.nex --work WORKDIR --screen SCREEN.scr
```

Add `--enhanced` for the painted variant. Both builds carry identical code and
tables; bank13 offset56 selects the painting at startup. The NXC menu exposes it
as option9, off by default. Changes to source graphics invalidate the cached
painting; unknown images use the ordinary renderer. Painting data is generated
from the owner's snapshot, not distributed as game graphics in this repository.

SCREEN.scr is the first 6912 bytes of TAP data block 3, loaded at 4000 by the
tape's BASIC-variable machine-code loader. Tape MD5:
`d5c0df83bbcb7c4eefbade3add8a7bfc`. The builder checks the boot tail and simulated
NEXLOAD overwrite before adding the screen, then verifies bank identity using
the screen-aware NXC parser. The complete hidden Sinclair ROM image is included.

The private run's work/ directory retains the exact-fetch recorder, independent
proof harness, negative controls, clock/R matrix, native checks and packaging
script. These are game-specific evidence tools, not changes to shared checkers.
This standalone builder is not registered in the generic auto command.

## v1.0 baseline coverage

Final candidate14: 30133 replay frames, zero differences; 65838 external hook
events, all 14 sites covered (the internal copy test is included in each copy),
12075264 sprite-pixel comparisons. Nine negatives detected; 208 clock/R cases and
the full log-table/overflow test pass. Forty pace trials: quiet -0.03%, busy
-0.02%, sound -0.12%, cube stress +1.86%. All 30 room checks range -1.57% to
+1.97%, with identical player-state samples. Two 220-frame flicker runs and a
15-minute soak pass. The final menu starts play in headless JNext; bare and menu
host reconstructions are byte-exact. Source rebuild and documentation checks pass.
NXC SHA-256: `eefcbad170fc3a086e60d714f03b5762f1f1cdd171593c59f0ca93153524d5f2`.

Natural recording: 15133 frames, menus and all three control choices, natural
deaths, game-over text and return to menu. Room recording: 15000 frames across
30 injected room-index starts, using original setup plus archive lives/immunity
trainers in the test starts only. Includes void/transition indices; not a full
walkthrough or evidence that every puzzle has been solved. Replay compares all
architectural registers including R and non-display game memory at each hook;
independent pixel checks include position and masked interiors. Native snapshots
also check actual sprite attributes against the staged table and stale slots.

## v1.1 Enhanced

The owner explicitly requested the painting after the initial HARD rating:
pink baby skin, white nappy, white cupcake icing/eggs and bold toy-shop colours.
87 source images receive new colours; 32 retain the game's colours. All original
black details and transparency are preserved. The 231 whole poses/facings have
zero look-sheet flags and were inspected at 4x. Static scenery keeps its colours.
This is a sprite paint set, not a full scenery repaint.

The 267 raw chunk variants and their mirrored paintings occupy pages56–65;
pages48–55 index source addresses. Complete raw bytes and mask type must match
before a painted pattern can be used. The cache additionally checks the source
address, since identical bytes at a different address need not have the same paint.

Final candidate03, both modes: 30133 frames each, zero divergences; 14 sites and
65838 external hook calls each. 13/13 negatives caught; 416 clock/R cases pass;
1072 pattern cases pass, including altered graphics and an unknown address with
the same image/cache slot. Raster phase sweep: 39 valid phases pass and 18 forced
unsafe publication phases are caught. Default pixels match v1.0 in all 30 samples.
Enhanced pace means: quiet -0.04%, busy -0.04%, sound -0.11%, cubes +1.72%; ten
trials each. Original-colour mode: -0.03%, -0.02%, -0.11%, +1.86%. Both within 2%.
Two 220-frame flicker checks and 15-minute soak pass. All 100 sound events match
player updates. Final menu selects both sets and reaches play in headless JNext.
The last art-only change makes the named RED WHALE red: only 102 pattern bytes,
no timing/control-flow change, and both full replays were repeated afterward.

Package: herberts_dummy_run_v1.1.nxc, SHA256
`583f33cd23e2ba8cd1d743ed837217eaaa536be163026de820e8c95c26e0dbb6`.
Menu, default bare and Enhanced bare rebuild byte-exact; seven cheats pass in
both sets. Enlarged evidence: out/herbert_enhanced_fix.png in the adjacent run.

## v1.2 whole-artwork pass

The owner requested a second pass over moving figures AND backgrounds, following
pixel borders instead of attribute blocks. 112/119 source figures are painted;
59 explicit part masks fix hair, nappy, icing drips, dummy, bomb, plane, top,
vacuum and previously missed Herbert poses. All 231 poses/facings retain their
exact original transparency and black detail. The 100 background templates were
reviewed as whole objects; 73 are painted. The default set retains its colours.

Enhanced scenery uses Layer 2 below the sprites and above the ULA, clipped to
rows 48-191. Zero is transparent. The 2496 painted glyph occurrences are keyed by
object identity, relative position AND source address, then checked against every
live graphics byte. A 16KB hash table has at most four entries in its observed
chains. Unknown or changed glyphs clear their overlay cell and use the ULA.
This prevents reused chair/sofa/plant tiles from borrowing another part's paint.

Object and both 8x8 glyph writer hooks queue colour updates. The queue flushes
before the clean-screen/sprite border publication, with a second border wait
before publishing. Room/reset/menu paths clear or hide the overlay. The original
clean and direct playfield glyph writers run at 28MHz in Enhanced only; paired
tail hooks restore incoming speed before game code resumes. HUD direct drawing
keeps its incoming speed. Every external boundary restores R. No DI/EI added.
There are 19 patch sites: 16 external entries plus three internal paired tails
(copy 97D7, clean glyph 9CB7, direct glyph 9C5E).

Scenery lookup uses pages 36-37, records 66-85, queue 86-87 and Layer2 pages 88-93;
the complete hidden ROM remains in pages 94-95. Existing sprite paint and image
cache pages remain separate. Build-time tables derive from the user's exact
snapshot. The private run's work/artpass directory holds the census, paintings,
independent scenery model, hash-collision negatives and final06 evidence.

Final06: both sets 30133 frames each, zero differences, 114651 external
calls per set. All 19 sites covered;18/18 negatives, 512 clock/R, 1072 pattern and
7490 scenery cases pass. All 30 room pace samples within 2%; ten-trial means:
quiet -0.12%, busy +1.21%, sound -0.14%, cubes +1.76%.
Two 220-frame flicker checks and 15-minute soak pass. Default pictures match v1.1
in 30 rooms. Menu and both bare CLI rebuilds are byte-exact; 14 trainer/set cases
pass. Packaged v1.2 SHA256 `867d5289d097c9235c51e858b48eb6822b857d7017b58f8f743880117a388df3`.
The enlarged comparison is out/herbert_artwork_fix.png in the adjacent run.
Owner preview approved; v1.2 gameplay awaits owner testing.

## v1.3 owner paint import

The owner edited the native-pixel PNG and requested solid white/yellow without
brush blending. Four ball frames and eight Herbert poses contain 342 ink changes:
273 green-to-yellow, 60 pink-to-white and 9 white-to-pink. Original black detail,
transparent pixels and silhouette are retained. Mirrored facings follow the same
paint. All other paintings and scenery remain unchanged. The 231-pose look sheet
has zero flags. Six native room starts and enlarged before/after pictures were
inspected. Fresh editable sheets preserve this v1.3 baseline and import unchanged.

Only 408 packed colour-data bytes differ from v1.2, in banks 29/31. Engine code and
all non-paint bytes are identical. Both sets again pass 30133 replay frames and
114651 external calls with zero differences; every count and instruction total
matches v1.2. All 19 sites, 18 negative controls, 512 clock/R cases, 1072 pattern cases
and 7490 scenery cases pass. The negative trace adapter now excludes all three
internal tails; per-process assembly outputs prevent concurrent harness races.
Pace, sound, flicker and soak evidence is explicitly carried from v1.2, supported
by the data-only delta and identical replay counts; no fresh timing claim is made.

Three CLI reconstructions are byte-exact, 14 trainer/set cases pass and all three
native menu cases reach play. Enhanced remains off by default. Package
herberts_dummy_run_v1.3.nxc SHA256 `56272ba2920cc7844ec2842034ed243912ef299c4d5574fc131139503bdacdc6`.
Owner has not yet played v1.3. Detailed evidence: adjacent work/owner13 and
ENHANCED.md; v1.2 evidence is retained in ENHANCED-v1.2.md.

## Lessons

- [local: v1.2 complete-object paint census] Repeated glyph bytes need object identity AND placement to distinguish materials within and between objects. Forged hash-collision negatives prove the full identity checks independently of the hash.
- [local: v1.2 sun-room timing, measured room by room] A rare per-update water strip invokes 22 direct glyph hooks. Measure every room; speed the original display-only writer with a paired restore rather than reducing the global pace limiter.
- [local: v1.2 Layer 2 publication] Flush queued scenery before the final border wait. Putting a large flush inside the existing sprite publication window can push attribute writes into active display.

- [local: implemented in this engine and independently checked in native snapshots] Attribute NextRegs and port 57 use separate sprite selectors. A simulator that aliases them can falsely approve stale copies. Explicit port selection and a broken-selector negative now cover this.
- [local: Herbert's mutable graphics and repeated cube frames] Cache by image address across figures, then compare complete source bytes. Per-slot caches can pass pixels while rebuilding the same animation many times.
- [local: v1.1 painting and the unknown-address negative] A painted cache must check source identity as well as raw bytes: another object with identical graphics can have different paint. Unknown or altered graphics fall back to the ordinary pattern.
- [local: v1.1 raster phase sweep] A faster renderer can make a formerly caught unsafe-publication negative pass at one phase. Sweep the raster phase: the good build must pass every phase, and the broken build must fail where publication reaches active display.
- [local: this game's clean buffer changes during an update] Freeze scenery at reset, not at commit; copying the live clean buffer presents some edits one update early.
- [local: self-modifying B32 base operand in this game] Intercept after the base load; placing the jump over its operand corrupts the hook when the room changes.
- [local: the native keyboard queue crosses a video boundary] Queue replay keys before the long copy window and count pace at player update 9095. Queuing at the reader itself can give one build an extra jump update.

- [local: a painting can be stored without the picture it paints] colours per ink pixel in order, laid over the image read from the snapshot, gave the same build.

## Technique use

- patch.display-atomic-switch: helped — inactive pattern half, border publication and native flicker checks.
- optimise.pattern-cache: helped — full-byte validation, shared image entries, deliberately stale-cache negative.
- patch.attribute-shadow: helped — original attribute state retained while scenery colours remain clean.
- patch.runtime-colour-map: helped — pose paintings validated against every live source byte, exact mirrored masks and a source-aware cache.

## Friction

- reuse: [local: family methods reused without copying an incompatible whole engine] Wally and Three Weeks supplied the plot/buffer model; Atic supplied cache and every-clock testing patterns.
- retries: [local: earlier candidates and failing measurements retained] Native pictures caught the selector-model mistake; the all-room pace survey caught sparse-room speedup and crowded-room slowdown.
- environment: [local: this task must remain inside its own run folder] All emulator HOME/temp/output paths are private, and the supplied card image is opened read-only.
- hand-rolled: [local: game-specific adapters are retained beside their raw logs] Exact-fetch recording and native classic-screen extraction avoid the unsuitable assumptions found in the generic helpers; shared tools were not edited.
- scratch: [local: reproducible evidence is retained with this game] work/ scripts and logs remain in the run; source ROM, snapshots, recordings and extracted art are not committed.

## Open

Owner play: check the nappy/arms during walking and jumping, toy soldiers, icing,
eggs, overlapping figures, stairs and the sports/cube rooms. Hardware remains untested. Generic command registration
is separate integration work; the supplied standalone build and NXC paths are
the reproducible deliverable here.

## Stage log

- 2026-11-05: v1.3 owner-painted solid colours, complete replay regression, native preview, byte-exact package and fresh editable sheets.

- 2026-11-05: whole-artwork v1.2 pass, object-aware scenery, paired glyph speed restoration, full proof and byte-exact package; details in the run's ENHANCED.md.

- 2026-11-05: family survey, engine, recordings, native graphics review and pace optimisation; final results in the run's REPORT.md.
- 2026-11-05: requested Enhanced set, all poses/mirrors reviewed, original-colour regression and full proofs, byte-exact v1.1 package; detailed results in the run's ENHANCED.md.

## Next session

Start from the packaged v1.3 and the owner's play feedback. Use the new v1.3
editable sheets for further paint edits; preserve the owner's original v1.2 PNG. Preserve this run's
inputs and evidence; no permission to publish or write a card is implied.
