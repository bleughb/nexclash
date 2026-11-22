# R-Type (128K) - intake

## Next session
Stage 6 (owner 2026-11-22: "get R-Type set up as a nexclash game"), branch add-r-type: the engine is in,
UNVERIFIED (owner decision: ship unverified first; the simulator proof is its own stage).
`nexclash.py auto r_type.z80` (no recording) writes r_type_sprites.nex 1fdf9b83 and _loading 727b938f
(the .nxc's builds; r_type_loading.scr beside the snapshot, MD5-checked side input: game data, never
here) and r_type_game.nex 9d5bab81. The .nxc toggle "Advanced intro screen" = r_type_intro.nex /
_loading (the intro in free banks of the same build; nxc toggles need the same length).
- Owner 2026-11-22: no high-resolution picture (RC1's showpiece): Patch(showpiece=False), the
  default, jumps over spec_hold's reveal call.
- Intro flow (owner 2026-11-22): the low-resolution spec screen still for 5 s, then the ships turn;
  any key or fire: fade out, game. Stick: fade to the 3D side ship, turned by the stick; key or
  fire: fade back to the still screen, 1 s, fade out, game. Keys are not read during the page check.
- Stick ship every 8 of 256 angles (INGAME_GSTEP; 289 pictures, 90 pages); code bank 8, pages
  PICTURE_PAGES. The option jumps from the stub to the intro, NOPs `call spec_hold`; the intro
  restores the stub bytes and starts the game.
- nexclash/r_type.py: hooks from docs/profiles/r_type.json (asm/r_type_hooks.asm), 18 sites, PACE,
  RAMFIX, NOTAPE, banks (colour, scenery masks, behind flags r_type_behind.json, glide, ship).
  Level graphics: the game's own unpacker (8F31..8F4E) run in the simulator on the
  player's snapshot, checked by SHA-256 of all ten images; the catalogue (profiles: r_type_catalogue.json.gz) =
  level / address / ink + geometry only (the figure corpus rebuilt exactly from it + the snapshot).
- r_type_colour / _figures / _scenery / _masks / _showpiece: the specnext intake modules, paths only
  changed (snapshot via r_type.set_source or $NEXCLASH_R_TYPE_Z80); registry r_type_figures.json.gz
  and arrangement r_type_sheets.json in docs/profiles. Sheets and recolour use r_type_game.nex.
- Intro: r_type_intro.py + r_type_r9.py (owner's model r_type_r9_model.json.gz, rendered at build
  time) + asm/r_type_intro.asm; title / logo / text from the snapshot's own screen (= the
  original specification screen, checked pixel-exact).
Cheats: 4 TipShop trainers in the .nxc (auto writes r_type.pok). Open: hardware test of the .nxc
builds; proof stage: Layer 2 / sprite model, verify, unit tests.
Stage: 1 complete as a playable prototype (main: 2026-11-16). Since then specnext PRs #97 <- #98
<- #99 (stacked, open; owner-tested in CSpect only, 2026-11-17) own the display: Layer 2 640x256
half-pixel scroll, scenery in front with see-through edges, filled whole-figure sprites that glide,
4 frames per update, start-up showpiece (removed 2026-11-22). The
lines below describe main; the PRs and specnext reference/r_type/intake (and the owner's local
handover R_TYPE_HANDOVER.md) describe the rest. First: hardware test of #99 and banks 48-62 on a
1 MB Next. Techniques: `patch.hybrid-display-replacement`, `patch.layer2-half-pixel-scroll`,
`patch.scenery-edge-masks`, `patch.figure-glide`, `optimise.flash-palette-offset`,
`patch.copper-palette-bands`, `patch.art-from-own-unpacker`, `patch.optional-front-end-in-free-banks`,
`patch.loading-screen-from-tape` (record without techniques yet).
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
Animated spec-screen intro: built here since 2026-11-22 (r_type_intro.py); RC1's: "Spec-screen intro".
Setup and tests: specnext reference r_type/intake/tools/README.md (duplicate the owner's Windows
setup or use the /workspace layout; emulator order CSpect then JNext; CSpect's control server needs
its paid Builder tier). Before pushing prototype changes run smoke.py and compare.py, plus
gameover.py when titles, game over or speed change; each prints PASS / FAIL, exit 1 on failure.

## Spec-screen intro (2026-11-20)
RC1's standalone front end (R-Type_SpecNext_V1.2.NEX, owner hardware PASS; owner's r9-wireframe
sources, its own loader reading the game from its file): reference continuation/history-2026-11.md.
Since 2026-11-22 the intro is built here (Next session; card patch.optional-front-end-in-free-banks).
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

## Open
- .nxc loading screen: nexclash auto / nxcout to set INF1 build_screen=nex on a build with a loading
  screen, once jattree/nxc PR 9 is merged and nxc.py is re-vendored (card patch.loading-screen-from-tape).

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
- [doc docs/CHECKS.md §Setup] Observed in JNext1.2.0: execute-triggered JNS requests save at a frame boundary. Exact hook ABI/RAM tests use execute-time logs/dump_mem instead.
- [tool nexclash.isrinfo] Expose data-read/write address sets in the API, retaining text output;
  this distinguishes safe pixel scratch from ISR-mutated attributes and shadow-slot variables.
- [tool nexclash.survey] Observed: a CALL as a routine's first instruction was never tracked;
  R-Type 8979 -> 8842 exposed the false coverage gap. Removed the early return and added a golden check.
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
- [card patch.art-from-own-unpacker §Use / do not use] The figure corpus held graphics bits; the engine
  stores level / address / ink only and rereads attribute + bits from the game's own unpacker run on the
  player's snapshot (exact: SHA-256 of the ten images, corpus equal). Check unpacker output first.
- [card patch.art-from-own-unpacker §Use / do not use] Rtype.z80's own screen is the specification
  screen, pixel for pixel: the intro's title / logo / text need no side input.
- [card patch.art-from-own-unpacker §Verification] Demonstrated: the prototype's asm moved unchanged
  (asm2profile output byte-identical) and r_type.py's build = RC1's (a52841b4): port first, then change.
- [card patch.optional-front-end-in-free-banks §Use / do not use] .nxc trainers poke banks the NEX
  header lists; RC1's intro read the game's banks from its own file, so no .nxc and no trainers. In
  free banks of the same build (code bank 8, 90 pages) it is a toggle and the 4 trainers apply.
- [card patch.optional-front-end-in-free-banks §Failure lookup] nxc toggles need builds of the same
  length: the intro's banks are in both builds, the option only changes the stub's start.
- [card patch.loading-screen-from-tape §Use / do not use] Observed: Rtype.z80 holds no loading screen
  (0 of 107 64-byte pieces); the tape's SCREEN$ (offset 247) is an MD5-checked side input. add-dump
  of Rtype.tap refused (79,829 bytes not on it): level blocks load at C4AE, stored converted.
- [card patch.loading-screen-from-tape §Failure lookup] Owner's Next 2026-11-22: the new .nxc with the
  old /dot/NEXCLASH showed noise (`nex` read as offset 0); with both copied the screen and dots work.
- [deferred Open: reconsider when jattree/nxc PR 9 is merged] auto does not set build_screen=nex;
  the vendored nxc.py lacks the key until then (set by hand: nxc.py set ... build_screen nex).
- [local: owner removals by a jump] "No high-resolution picture": spec_hold's reveal call is jumped
  over (jr nz -> jr, found by its bytes), so the code stays and the change is one byte.

## Friction
- reuse: [none: existing survey, scan, preview and census tools provided the investigation paths]
- retries: [local: measurement boundaries] JNext can report an execute address again after IRQ; one-shot phase flags and nested-ledger negatives prevent double accounting. All101 clocks/380 bytes agree with uninstrumented controls. Earlier guard/stack and source-hole fixes retained in reference.
- environment: [local: remote continuation] SkoolKit10.1/Pillow13.0.0, official JNext1.2.0 and new owner SD restored read-only outside Git. Old peak/profile absent; new9cfed755 recipe is explicit, not an old-result reproduction. Main f92662e.
- hand-rolled: [none: disassembly used sna2skool; screen images used the existing preview renderer]
- scratch: [local: per-game feasibility evidence] Game-specific experiments kept beside the inputs
  in specnext/reference/r_type/intake; none added as an untested shared toolkit probe.

## Stage log
- 2026-11-22 Catalogue: 3 candidate cards (unpacker art, front end in free banks, tape loading
  screen); RC1 intro section + 13 parked-route lessons to reference continuation/history-2026-11.md.
  Owner's Next: .nxc loading screen at ENTER (jattree/nxc PR 9) works.
- 2026-11-22 Stage 6 engine (branch add-r-type): r_type.py + intro build reproduce RC1 byte for byte
  from the snapshot and two side inputs; record unverified; cheats open (intro loader).
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
