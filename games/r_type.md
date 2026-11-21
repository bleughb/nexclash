# R-Type (128K) - intake

## Next session
Stage 6 started 2026-11-22 (owner: "get R-Type set up as a nexclash game"), branch add-r-type.
Release candidate RC1 = specnext r-type-cache 00d6801 game + spec-screen intro (owner flow
2026-11-22: tape loading screen >= 4 s, ships turn at once, stick -> hand-turned ship once, fades).
Owner decisions: intro rendered at build time from the owner's R-9 model (nothing copied from the
game stored); first version ships UNVERIFIED (.nxc says so), the simulator proof is its own stage.
Plan, in order (each step committed; RC1 is the byte-exact target until the proof stage):
1. nexclash/r_type.py + asm/r_type_hooks.asm (l2scroll, l2sprites_body, glide, ship folded in):
   `is_r_type`, profile, `auto` building plain + sprite NEX from Rtype.z80; side inputs found by
   MD5 beside the snapshot, like cisco_heat LOAD_SCREEN: tape loading screen (scr block), the
   owner's showpiece picture, decoded levels and figure corpus made from the snapshot / RZX at
   build time (not stored). Target: rtype_rc1_game.nex MD5.
2. Colours: registry, arrangement and colour map as docs/profiles/r_type_*.json (owner decisions +
   graphic addresses only); sheets drawn into the session folder, never committed here.
3. Intro: model json + renderer + specanim.asm as a build step; title / text / logo pixels taken
   from the snapshot's own spec screen; output = RC1 intro NEX MD5.
4. .nxc: variants (with / without intro), cheats from the TipShop .pok (all addresses checked
   2026-11-22: infinite lives, immunity, invincibility, attachments work; no-scenery has no effect).
5. Record (unverified, emulator evidence: smoke, compare, sweeps, intro verify_load), STATUS,
   engines.py line, doccheck. Push / PR only when the owner asks.
Stage: 1 complete as a playable prototype (main: 2026-11-16). Since then specnext PRs #97 <- #98
<- #99 (stacked, open; owner-tested in CSpect only, 2026-11-17) own the display: Layer 2 640x256
half-pixel scroll, scenery in front with see-through edges, filled whole-figure sprites that glide,
4 frames per update, start-up showpiece (owner's 320x256 neon picture, pixelate transition). The
lines below describe main; the PRs and specnext reference/r_type/intake (and the owner's local
handover R_TYPE_HANDOVER.md) describe the rest. First: hardware test of #99 and banks 48-62 on a
1 MB Next. Techniques: `patch.hybrid-display-replacement`, `patch.layer2-half-pixel-scroll`,
`patch.scenery-edge-masks`, `patch.figure-glide`, `optimise.flash-palette-offset`,
`patch.copper-palette-bands` (no record yet: stage 6).
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
Animated spec-screen intro (2026-11-20, owner hardware PASS on a 2 MB Next): see "Spec-screen intro" below;
after rebuilding the game, rerun its make step with the new game NEX.
Setup and tests: specnext reference r_type/intake/tools/README.md (duplicate the owner's Windows
setup or use the /workspace layout; emulator order CSpect then JNext; CSpect's control server needs
its paid Builder tier). Before pushing prototype changes run smoke.py and compare.py, plus
gameover.py when titles, game over or speed change; each prints PASS / FAIL, exit 1 on failure.

## Spec-screen intro (2026-11-20)
A separate front end, not part of the l2scroll build: the technical-specification screen redrawn with a
new 3D R-9 model (top, front, side views), then the game. Owner-tested on a real 2 MB Next as
R-Type_SpecNext_V1.2.NEX: screen, animations, joystick view and the load into the game all work.
- Sources (outside specnext, owner's r9-wireframe folder): `r9-wireframe/r4/next_spec/specanim.asm`
  (program; `-DALLDIR -DGAME` for this build), `make_spec_next.py` (ship pictures, text list, Layer 2
  title/logo; run from r4 with PYTHONPATH=.), `make_rtype_spec.py [GAME.nex]` (assembles and appends the
  game; default C:\1NEXT\rtype_builds\rtype_ship.nex, only read). Output `next_spec/RTYPESPC.NEX`
  (2.5 MB); any file name works. Details and history: r4/HANDOVER.md.
- Flow (2026-11-22): the tape loading screen (NEX SCR screen, "no palette" flag set) from the start
  of loading, at least 4 s (page checksums; blue border = a page failed), fade; the ships turn at once
  (top pitch, side yaw, front roll), text scrolling. Stick moved (not fire), once only: fade to the
  side ship alone, turned every way (33x33 views + flips); fire or key fades back. Any key, fire or
  (after that) the stick: load the game.
- Ships are stored pictures (the model needs a per-pixel depth test; live drawing is not feasible),
  packed 1-bit, built in page 220 and copied to the ULA screen in the bottom border. Title, logo and
  text on Layer 2 in front. Pages used: 18-23 Layer 2, 24-219 pictures, 220 work, 222 loader.
- Game load: the NEX keeps its file open (`savenex cfg 0,nexhandle,...`); the game's banks follow
  the intro in the same file. The loader runs from A000 (bank 2) in the standard 128K layout (see
  Lessons), reads 8K at a time into 8000 and copies each piece to its page; the game's banks 0-7 wait
  in pages 180-195 until the file is closed. Code planted at 4000 in the game's (blanked) screen puts
  bank 2 in place, pages the entry bank and jumps to the game's PC/SP. Next register 8E is restored.
  Border while loading: yellow open, cyan/green read, white place; red = open failed; red/yellow
  flashing = read failed.
- Changes to the copy of the game: the `call spec_hold` in the hook page (bank 12, found by the bytes
  ED 92 05 C1 F1 CD) is NOPped, so the game starts at its logo animation (no original spec screen or
  showpiece); the original spec picture in bank 5 is blanked. make_rtype_spec.py asserts these are
  found once and that the game uses no page from 180 up; a changed hook page needs the pattern updated.
- Checks (CSpect): ship pictures pixel-exact against the model's renderer at stops in every state;
  all 100 game pages byte-exact at the jump to the game (r4/scratch_v19/verify_load.py); title and
  level 1 play.

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
- patch.hybrid-display-replacement: helped: the original runs the logic; Layer 2 + sprites own the display.
- optimise.pattern-cache: corrected: keyed by ink, flash colours filled it; see optimise.flash-palette-offset.
- patch.pace-limiter: no help: the owner dropped slowdown; a fixed frames-per-update count (PACE 4) instead.
- optimise.pattern-cache: no help: protected union exceeds128; immutability/invalidation warning reused, staged single-bank protocol retained.
- patch.display-atomic-switch: helped: checks require complete old/new pictures; single-bank publication remains a measured alternative outside the play area.
- patch.preserve-r: used: actual copier M1 span repairs return R; isolated assembled bridge passes, IRQ consumers remain a separate proof.
- detect.pacing-structure: used: preliminary census locates the three-interrupt wait and beeper writers.
- detect.routine-removal: helped: identifies the required dependency experiment; existing probe is 48K only.
- detect.buffer-layout-producer: helped: separated final copier, nonlinear source cells and non-pixel holes.

## Lessons
- [card patch.layer2-half-pixel-scroll §Use / do not use] Scenery stepping 1 px per 4 frames judders on smooth
  sprites; Layer 2 640x256 scrolls only whole pixels, so two screens (one half a pixel on) halve it.
- [card patch.scenery-edge-masks §Failure lookup] Per-cell runtime floods were too slow; masks from a whole-level
  sky flood, keyed by cell content, with 1-2 px gaps as walls, cost one lookup per staged cell.
- [card patch.figure-glide §Contract] Port 303B selects both sprite and pattern-upload index: an ISR moving
  sprites garbled uploads; count skipped steps and make them up. Even update lengths are needed.
- [card optimise.flash-palette-offset §Measurements] Four flash colours x three graphics filled the cache; its
  restarts drew figures natively in 8x8. One conversion + palette offset per graphic fixed it.
- [card patch.copper-palette-bands §Failure lookup] CSpect: WAIT line n shows from row n + 32 of 320x256 Layer 2;
  the restart comes after the top border; 9-bit NR 0x44 pairs from the Copper failed.
- [local: start-up stack in slot 6] At the NEX setup call SP is near DFEE: mapping a page into
  slot 6 there (to copy data) crashed; keep data in an already mapped page or use slots 3/7.
- [tool tools/asm2profile.py] A SAVEBIN in an INCLUDEd file is not collected (names come from the
  top file): the build used an empty page. asm2profile now warns about uncollected .bin outputs.
- [local: tests break at 0000] The R-Type tests set a breakpoint at 0000 to catch a reset; a glide
  page entry at 0000 looked like a reset. Entry points start at 0100.
- [local: never edit build inputs mid-test] compare rebuilds each level from the current files; a
  half-edited layout gave a false slowdown on levels 2-8, cleared by a worktree bisect.
- [local: the original's pace] The recording averages 4.35 frames per update (28% 3, 34% 4, 22% 5);
  the title alternates 2 and 3. At 28MHz every update took 3 (45% fast): PACE 4, title 4.
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
- [local: CSpect fakes RST 08] The intro loader worked in CSpect and crashed on hardware three times.
  NextZXOS esxDOS calls need (NextZXOS_and_esxDOS_APIs.pdf): 48K BASIC ROM (1FFD=04, 7FFD=10, copied
  to BANK678 5B67 / BANKM 5B5C), MMU2-7 = 10,11,4,5,0,1, no DFFD paging, stack and buffers below
  BFE0, IY=5C3A, banks 5 and 7 untouched while the disk is in use (bank 7 is the disk system's).
  CSpect accepts calls that break all of these; a disk change is only proven on hardware.
- [local: read the rest of a NEX] Opening the NEX by name broke when the owner renamed it (red
  border). `savenex cfg <border>,<address>` keeps the file open and writes its handle there.
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
- 2026-11-20 Spec-screen intro in front of the game (R-Type_SpecNext_V1.2.NEX): 3D R-9 views,
  scrolling list, turning ships, joystick view, game loaded from the same file. Owner hardware PASS.
- 2026-11-17 Own the display (specnext PRs #97-#99): half-pixel scroll, scenery masks in front,
  filled figures, glide, pace 4, title fixes, power-up fixes, start-up showpiece. CSpect only.
- 2026-11-16 Prototype: colour sheets + recolour, figure IDs, outlines, partly hidden figures,
  start-up / title / high-score fixes, level-unpack hook-page fix. Owner hardware playtest OK.
- 2026-11-15 New route: Layer 2 hardware scroll, then hardware sprites; later levels and scripted
  input checked; Kempston fixed. Cell-recognition route parked (28MHz main loop measured).
- 2026-11-10..11 Stage 0-1: intake, censuses, ISR footprint, DMA publication, live budgets.
  Full entries in reference continuation/history-2026-11.md.
