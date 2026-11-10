# Movie (Imagine, 1986)

## Next session

Stage 2 colour round: Jon's native sprite edits imported on `game/movie-painting-edits`.
The earlier stamped package remains on `game/movie-release`; its proof does not cover this round.
Latest review paths: private runs/movie/work/current-art-review.json. November 9's second pass
adds 42 scenery edits to the prior figures and a painted HUD. Before packaging, run full verification/stamping
and all disposable-loader cases using the current review's asset folder.
Inputs and hashes: `docs/records/movie.json`. Supply external colours.bin, palette.bin, painting.json
and movie-loading.scr beside movie.z80; optional hud.bin paints the icon strip. Alternatively set NEXCLASH_MOVIE_ART to the painting folder.
No game assets enter this repo. Jon approved 1930s noir colours and overnight implementation.
Private evidence is in pilot runs/movie; use its private handoff when completed.

## Source and presentation

Source: `M.O.V.I.E. (1986)(Imagine)[a][a].z80`, 48K, MD5 `facf9b90032759b7012abd91602b4b45`.
The unqualified archive file (MD5 `d86588219c95b00e132863a527f35543`) produced a damaged HUD in
original execution and was rejected. The supported source pauses mid-draw at F56C, SP=0.
Finish exactly 3796 native T-states to F526 before patching: 33 scratch bytes change, no I/O or
game updates. Both modes restore registers, R and RAM there, including NEXLOAD's printer buffer.
Full hidden ROM: bank 47; mapped Sinclair lower/upper pages 27/24 preserve the native ROM view.

Default retains original monochrome, not advertised as a clash fix. Optional Enhanced is off
by default: charcoal/navy/brown clothes, cream shirts, warm skin, muted walls, wood, burgundy/brass.
Original clipping and depth order remain; no added white outlines. Jon's November 9 edits trim
black edge pixels and repaint some paper pixels; these intentional Enhanced changes are recorded.
The approved concept was not used as pixel data. Editable sheet: 193 native graphics. Imports
use flat native pixels, reject contradictory shared-part edits, and propagate shared pixels
across animation references without blending. Canvas grey erases an existing painted pixel;
static graphics allow explicit additions within their cell. Mutable door/text data retains
native opacity; unsupported edits fail. Added and erased pixel ownership is explicit metadata.

## Engine

Techniques: patch.pace-limiter, patch.restore-speed, patch.preserve-r, verify.update-locked-pace.

F29B is the SP-based plotter, with eight masked/direct/shifted/mirrored chunk hooks. F18A clears
scratch 9500..95FF; F700 commits dirty rectangles. A 2048-pixel colour scratch feeds Layer 2,
on rows 0..167. Optional HUD paint extends it to 191; the native animated selector stays on ULA.
EFCF copies the 256x24 painted strip once at native initialization, using bank 45/page 90.
Only original set bits may be painted: holes stay transparent for the OR-composited selector.
MMU3 is saved/restored along with shared entry state. Full-screen reset clears the strip too.
7279 updates speech-cache bytes as written. Mutable shared masks D3F4..D403, door bytes A401..A482
and inventory data from 9F77 use live decoding. FFA6 mirrors full-screen erases, including reset.

Private code/state: page 26; resident upper-ROM code stays below 3D00 (DivMMC trap avoidance).
Layer 2: banks 14..16; masked/opaque colour caches: 17..30 and 31..44. HUD bank 45 is optional,
complete hidden ROM 47: fits 1MB. Shared hlib_iff/speed/r/pace preserve caller IFF, speed and R.
Nested full plots have separate outer IFF/speed latches. The game is DI; tests cover both IFF
states and all four clocks. Original logic, E5D5 delay and sound routines are unchanged.

## DMA evaluation

Cached pixels use unrolled LDIX/LDDX; opaque strips have a fast path. Mutable decoding is unrolled.
Ordinary DMA copies contiguous rows of at least 32 bytes and fills the canvas. Short/wrapped rows
use CPU copies. Disable DMA is an off-by-default menu fallback. DDMA adds no useful primitive
for these transparent segmented copies; old/new core and hardware-IM2 fallback cases are tested.
Model DMA time is not a hardware measurement.

## Evidence

HUD review: 2,554 replay frames / 7,255 plots plus a one-frame native initialization fixture.
368 speed/IFF and 20 DMA/fallback cases pass, including the new hook; four existing mutations
and a misplaced HUD copy are caught. 196 native selector half-blits retain every base icon bit.
All five modes pass exact normal/NEXLOAD boot. Native figure/scenery/HUD sheets rebuild the
four art files byte-identically. Twelve pace windows: -1.568% to +1.753%; all 1,208 player x/y/R
samples match. The 48 speaker values/PCs match at 3.5 MHz. JNext screenshots inspected.
HUD startup cost in the injected model: 0.594 ms DMA / 4.741 ms CPU fallback; no per-frame copy.
Editable HUD: 256x96 PNG, art at (0,72), one PNG pixel per game pixel; top swatches are samples.

Second painting pass: 2,280 changed PNG pixels across 42 scenery cells, including one explicit
addition to the bar/stool graphic C4A3. The assembled game code is unchanged by this import
support; the importer, exporter and independent painted oracle now retain that addition.
The isolated C4A3 plot passes in both directions against the painted oracle. Current review
checks and build hashes are recorded beside the private review NEX; final stamping remains due.

Current review: 2,229 distinct edited pixels (126 erased), represented across 92 graphics.
4,754 overlapping replay frames / 11,193 plots pass exact native registers/R/RAM and painted
scratch/screen comparisons. The independent oracle reads original blitter registers and native
LDDR destinations; intentional repainting is not tested with a one-bit ink comparison.
688 speed/IFF and 16 DMA/fallback cases pass. Position, transparency, R, speed and forcing the
trimmed shared edges back to black are caught. Five build modes pass normal/NEXLOAD boot checks.
Previous-art shared-body regression: 1,000 frames / 2,586 plots, no mismatch.
Current JNext pace: 12 windows, -1.582% to +1.728%; all 1,208 player x/y/R samples match.
Busy scene is +0.338% to +0.534%. Speaker values match, all at 3.5 MHz; spans vary with raster phase.
In-game before/after pictures were inspected. Full replay stamp and real-loader rerun remain due.

Earlier release evidence (before this colour round):

Native proof: reference 55,354 frames / 131,198 plots; archive-source start 5,564 / 11,498;
reset cut 554 / 930. All registers including R, game RAM outside checked patch sites, scratch
pixels and published Layer 2 pixels agree. All eight chunk paths, text and reset are reached.
These recordings overlap; reference ends at 16%, not completion. Per-record tests total 472
speed/IFF cases and 20 DMA/fallback cases. Position, transparency, R and speed mutations are
caught on each recording. The transparency fixture includes a nonempty overlapping foreground.

Pace: JNext 1.1.104, E0A5 with HL=8200, three consecutive 100-update windows per scene,
302 player states compared per run. All x/y/R match. Positive is slower, negative faster.

| Scene | Trial 1 | Trial 2 | Trial 3 |
|---|---:|---:|---:|
| Quiet opening | +0.137% | +0.038% | +0.101% |
| Reference 5000 | -1.581% | -1.579% | -1.582% |
| Reference 15000 | +0.268% | +0.417% | +1.731% |
| Busy reference 30000 | +0.261% | +0.123% | +0.295% |

All are within 2%; this is not zero slowdown. Default has no drawing hooks. The sampled beeper
has identical 48 speaker values/PCs at 3.5 MHz; JNext spans differ by 14.57 microseconds (0.245%).
Nine isolated native comparisons are bit/timing-identical at equal contention phase; varying
raster phase changes duration. No AY music exists in this 48K release.

Exact normal/NEXLOAD boot and ROM audit start at the separately proven F526 boundary. Actual
.NEXCLASH tests use disposable 26.11 cards, ROM MD5 `e50ee485fb4a21d24dbf57b5e0868d8d`, and
compare rebuilt files byte for byte. No shared-card writes. Final package and detailed loader results are in the handoff.

## Trainers

Archive POK MD5 `7955ff07ce077ac391c4c7ab3bfc3c58`; all options off by default.
Infinite lives (FD89/FD8A), frozen enemies (E7F2) retain the archive sites. Enemy shooting uses
E991=0, avoiding a return from the broad E9D0 geometry helper. Skip final film check replaces
CALL 78F9 at 78C2 with XOR A/NOP/NOP; unsafe archive 78F9=14 is not shipped. Start with film
reel sets FC2E=11 and disables its startup overwrite FC0A..FC0C. Neither item option is labelled
instant completion. Each native routine is tested on/off; loader checks select each independently,
verify installed bytes after room entry, run play, and separately exercise all trainers together.

## Lessons

- [local: live HUD overlay] Native selector ORs immutable icon bits; paint only those bits and leave holes transparent. Prove this on selector replays and retain reset/init hooks.
- [tool nexclash/movie.py] A painted static hole is an explicit pixel addition, not native mask corruption; keep its ownership in metadata so export and the independent oracle agree.
- [tool nexclash/movie.py] Painted paper/erasures need exact colour composition from native chunk and copy parameters; binary ink equivalence would reject valid artwork.
- [local: shared walking masks] D3F4..D403 have fixed bitmap bytes but variable masks. Record intentional erasures separately from cached transparency belonging to another mask.
- [local: snapshot boundary] A mid-blit snapshot with SP as a graphics pointer requires a bounded native prelude.
- [local: reset coverage] Dirty rectangles miss the full-screen erase; the late replay reset exposed stale Layer 2 pixels.
- [local: mutable graphics] A shared opacity mask crosses D3FF; a page-boundary cutoff loses D401/D403 pixels.
- [local: nested state] Inner drawing overwrites its IFF latch, so the outer wrapper requires its own saved IFF.
- [local: coverage] A recording ending at 16% is not a completion even when every drawing entry type is reached.
- [tool nexclash/movie.py] Transparency negatives need nonempty overlap and the broken patch's own code/tables.
- [tool nexclash/movie.py] Audit ROM paths from the independently proven normalized PC, not the source's mid-blit PC.
- [local: trainers] Final-item cheats needed startup/condition translation and accurate labels, not blind POK copying.

## Technique use

- detect.buffer-layout-producer: helped: recovered scratch and screen commit.
- detect.drawing-parameters: helped: recovered clipped SP-based chunk parameters.
- detect.graphics-record-layout: helped: native consumer is an independent mask oracle.
- patch.pace-limiter: used: bounded full-plot/clear/commit windows and outside-work debt.
- patch.restore-speed: used: separate outer and nested incoming-speed latches.
- patch.preserve-r: used: compare R at each rejoin; broken epilogue is caught.
- verify.update-locked-pace: used: E0A5/8200 is the player update, not room initialization.

## Friction

- reuse: [none: existing intake tools suffice] Composition needs a game-specific native oracle.
- retries: [local: painting oracle] Speech-cache changes must feed the independent colour oracle; stale source colours gave false mismatches. Native-sheet tests reconstruct a private baseline after the user edits.
- environment: [local: firmware fixture] Verify copied ROM hash; an older private card was not the intended 26.11 system.
- hand-rolled: [local: colour renderer] Companion pixels preserve this game's native depth masks.
- scratch: [local: evidence scope] Movie-only loader/sound/trainer/pace scripts stay in private evidence; no game data enters the contribution.

## Hardware checklist

No hardware run. Check both modes, loading picture, speech, foreground occlusion, room changes,
reset, sound and DMA fallback on a 1MB Next. CSpect also remains untested. Raster behaviour during
a copy is not proven by return-boundary pixel checks.

## Stage log

2026-11-09 HUD round: painted noir icons, preserving native selector animation; added a native
editable strip, guarded initialization hook, independent HUD oracle, boot/ABI/pace checks.
This is an artwork review; the prior stamped package remains unchanged.

2026-11-09 second colour pass: merged current main 931458b, imported the 42 scenery changes
and preserved previous figure edits. One newly painted transparent pixel required host-side
import/export/oracle support; no assembled runtime change. Review remains separate from release.

2026-11-09 colour round: refreshed main from cc60245 to 8265011, resolved the generated status
view, preserved the prior release branch/package. Imported native sprite edits, taught shared
paper pixels to respect erasures, checked exact painted composition, ABI, negatives and pace.
Review build only; prior full stamp remains historical until the new release gate runs.

2026-11-09: source intake, independent oracle, colour renderer, mutable-text/reset fixes, full
semantic replay, negative controls, JNext pace/sound and private-loader trials. Source refresh
from e01cdc0 to cc60245 before final stamp changes records only. An early full auto completed
semantic proof then failed exporting the ROM-audit snapshot; the harness fix is checked separately
and the final selftest stamping run passed, superseding that incomplete command.
