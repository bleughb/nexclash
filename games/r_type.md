# R-Type (128K) - intake

## Next session
Stage: 1 complete as a playable prototype; owner playtests in JNext and on hardware report level 1
plays, Kempston and pause work (2026-11-16). Branch add-r-type in both repos.
Route (owner goal 2026-11-15: hardware scroll + sprites, hard to tell from the original; slowdown
dropped; equivalence "extremely close"): the original game runs unchanged as the logic; scenery is
drawn on Layer 2 and hardware-scrolled; figures are hardware sprites; HUD/stars stay on the ULA.
Sources: specnext reference r_type/intake l2scroll.asm/.py (scroll, hooks, builds), l2sprites.asm,
l2sprites_body.asm (sprites), l2sprites_full.asm (whole game), r_type_colour.py (colour sheets,
recolour, outlines), r_type_figures.py (figure IDs). Sheets, registry, README: r_type/colours.
Builds: `py -3 l2scroll.py --full` (whole game from Rtype.z80) / `--sprites` (RZX frame 2000 test).
Mechanics, details in reference continuation/history-2026-11.md:
- Scroll: 8842 copier hook moves NR 0x16 one pixel per call (7A8E clear); 89C3 draws the staged
  column on Layer 2; 8734 (FEEB) converts the drawn level. Scenery black is opaque on Layer 2.
- Sprites: plotter entries 8CFD/8D65/8DD3/8E29 record plots; graphics converted once into 4bpp
  patterns, cached by address + ink with checksum; flips = mirror bits; 24 tiles converted per
  update; partly drawn figures published behind whole ones; 8886 skips the copier's copy of cells
  a sprite shows (8EA2/8EC2 hooks) and blanks them; overflow falls back to native cells.
- Sheets (owner 2026-11-16, deviates from docs/COLOURS.md for R-Type only): two per level,
  IDENTIFY (2x, IDs) and PAINTING (1:1, same arrangement, every figure; a graphic is bright and
  paintable the first time, faded and ignored after); no REFERENCE sheet. Related figures grouped
  (shared art, art stored back to back at similar size and colours, or alike shapes).
- Colours: per-level sheets in the game's colours; import via r_type_colour.py recolour (shared
  nexclash.recolour.run); colour pages banks 32..47 applied at conversion.
- Figure registry r_type_figures.json: stable IDs L<n>-<nnn>, families, name / layer / outline;
  outlines pre-rendered one pixel bigger (pages 88-95). Layers are stored, not yet used.
- Speed: 28MHz only from the level draw to the next Layer 2 off (title, scores, name entry and
  continue run at 3.5MHz: busy-loop timing); the native ISR (all beeper sound) always 3.5MHz.
- Full build: technical-spec screen held 5 s or a key; FE03 tape prompts patched out; level unpack
  return (8F4E) maps the hook page back (7FFD maps ROM over slot 1); Kempston enabled (7A8B cleared,
  NR 05 mode 001); high-score check (92E8) turns Layer 2 / sprites off.
Next: play through a level change (untested in play); outline companion weapons / pickups (IDs from
the identification sheets); use registry layers in publication; then stage 6 promotion (record,
engine, profile, retire the parked cell-recognition route, full-recording verification, release).
Setup and tests: specnext reference r_type/intake/tools/README.md (duplicate the owner's Windows
setup or use the /workspace layout; emulator order CSpect then JNext; CSpect's control server needs
its paid Builder tier). Before pushing prototype changes run smoke.py and compare.py, plus
gameover.py when titles, game over or speed change; each prints PASS / FAIL, exit 1 on failure.

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
Earlier feasibility work (pace ledgers, ISR footprint, DMA publication, native tilemap, cell
recognition with identity caches) is in reference continuation/history-2026-11.md and the intake
reviews. It established the facts above; its cell-recognition route is parked: it could not give
hardware scrolling and its per-update identity work cost about 93% of the CPU.

## Checks
- Full recordings replayed by both caller censuses: 90,102 frames each, no desync.
- Prototype vs same-speed ULA control, eight RZX snapshots (2000..75000), 300-600 updates, no input
  and scripted input: pacing equal (297-299 of 301 updates at 3 frames), pictures differ by stars
  and see-through overlaps only. Full build: start, title, attract timing (title->scores 621 vs
  original 597 frames), game over, name entry same as the original. Colour import: recolour with
  {} gives the build back byte for byte; painted and outlined sprites shown in JNext.

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
- [local: wrong root cause recorded] A reset after patching C027 was first put down to a "game load
  check" and noted as "never patch bank 0"; the real cause was the 7FFD remap below. Confirm a cause
  with a trace (PC and MMU at the reset) before writing it down.
- [local: 7FFD remaps slots 0-1] On the Next a 7FFD write maps ROM over slots 0-1, hiding a hook page
  in slot 1; the level unpack (8F40) did it and the next interrupt reset the machine. Return through
  game RAM that maps the hook page back before EI.
- [local: busy-loop screens need original speed] Title, attract and name entry time themselves with
  CPU loops; run 28MHz only during play.
- [local: draw order beats identity] Replacing the picture (scroll on Layer 2, sprites keyed by the
  plotter call) cost less than recognising the original's cells every update, and gave hardware scroll.

## Friction
- reuse: [none: existing survey, scan, preview and census tools provided the investigation paths]
- retries: [local: measurement boundaries] JNext can report an execute address again after IRQ; one-shot phase flags and nested-ledger negatives prevent double accounting. All101 clocks/380 bytes agree with uninstrumented controls. Earlier guard/stack and source-hole fixes retained in reference.
- environment: [local: remote continuation] SkoolKit10.1/Pillow13.0.0, official JNext1.2.0 and new owner SD restored read-only outside Git. Old peak/profile absent; new9cfed755 recipe is explicit, not an old-result reproduction. Main f92662e.
- hand-rolled: [none: disassembly used sna2skool; screen images used the existing preview renderer]
- scratch: [local: per-game feasibility evidence] Game-specific experiments kept beside the inputs
  in specnext/reference/r_type/intake; none added as an untested shared toolkit probe.

## Stage log
- 2026-11-16 Prototype: colour sheets + recolour, figure IDs, outlines, partly hidden figures,
  start-up / title / high-score fixes, level-unpack hook-page fix. Owner hardware playtest OK.
- 2026-11-15 New route: Layer 2 hardware scroll, then hardware sprites; later levels and scripted
  input checked; Kempston fixed. Cell-recognition route parked (28MHz main loop measured).
- 2026-11-10..11 Stage 0-1: intake, censuses, ISR footprint, DMA publication, live budgets.
  Full entries in reference continuation/history-2026-11.md.
