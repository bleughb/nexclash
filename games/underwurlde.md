# Underwurlde (Ultimate Play The Game, 1984; 48K) - engine `underwurlde` (pilot game: emulator only)

## Next session
Stage: 4 (owner review + hardware). Hardware: untested. The owner approved the Enhanced look (Spec256 colours, palette
refitted so Sabreman keeps his eyes) before this release round; the .nxc v1.1 review package awaits his play.
Inputs: specnext/reference/underwurlde/ (not uploaded: kept in the pilot run): underwurlde.z80 = the archive bootstrap
below, MD5 9f2db0ec, and the 33 recordings named in docs/records/underwurlde.json.
Integrated on main 102091f (2026-11-07) from the pilot clone at 938f8fe: the engine files are byte for byte the frozen
release sources, so both game builds are byte-identical to the frozen ones (sprites MD5 07dff803) and the proof below
carries. Preserve the approved Enhanced pattern pages and palette.

## Inputs and appearance
- Archive: `Underwurlde (1984)(Ultimate Play The Game).z80`, MD5 `9a031797ed0cc96a9ec286ed22a32317`, the 48K beeper
  release. The .nxc targets this file.
- The archive starts in a BASIC infinite-lives prompt. The build input is its untrained "N" answer, captured before
  USR 26610's LDIR (pilot `work/bootstrap.py`, MD5 `9f2db0ec44da647aa1d7469f1f25ed67`).
- The LDIR moves 0x6801 down to 0x6800, length 0x8800: hook and trainer addresses are translated before relocation.
- Default: the original run-time figure colours, clash removed. Enhanced: optional, off by default; seven pattern pages
  26..32 and palette `006db6b1d0bfc410602552f885ff` are byte-equal to the approved build. 339 paired cold draws of all
  113 figures: default and Enhanced CPU registers, RAM, sprite attributes and timing identical.
- Enhanced colour credit: the Spec256 team (the conversion's readme: "Recolouring by: Spec256"). Patch by Jon Attree.
- The Enhanced colour map is Spec256-derived and stays out of the repository: a private reference input
  (underwurlde/approved_colours.json, SHA-256 605924aa...), applied with `underwurlde.recolour`.
- Loading screen: the archive TZX's pure-data block 22, shown by the .nxc package (SCR1).

## Rendering model and patch
XOR plotter shared by figures and scenery. 113 figure IDs, a fixed 24 object-record slots, 126 hardware sprite slots.
Records 36602..36938 (16-byte, then 8-byte records); graphic table 37682. Figure colours from IX+5.
Static plants and mounds, stalactites, furniture and the lives/menu icons stay on the ULA; the rope stays its original
XOR line. Approved solid interiors and existing black edges kept; no repaint and no added white outline.

| Entry | Hook |
|---|---|
| 38647 | Erase the old and draw the new figure |
| 38442 / 38454 | Draw / erase |
| 39015 | Figure cell painter: figure attributes suppressed, scenery kept |
| 39175 / 38269 | Room change / clear: every sprite hidden |

36 row writes become same-length, same-M1, same-T `LD A,(HL)` reads; the original plot bookkeeping stays.
A' after rows, and A and the flags but carry after rope pixels, are dead: replayed separately with them overwritten.
Screen readers are tracked; picture checks compare the original ULA with the patched ULA XOR figure ink at update ends.
113 images at 9 positions = 1,017 draw cases; 24 record slots; 27 scenery cases; 108 row cases; move, erase, clear and
painter cases.

## Interrupts, speed and pace
Shared hlib_iff, hlib_speed, hlib_r and hlib_pace. Hooks latch and restore the incoming CPU speed.
The IRQ wrapper keeps the original IM 1 body, runs it at the game's clock, counts its R contribution and leaves its time
out of the pace debt. Uploads, row loops and limiter waits stay interruptible; short R windows run at 28 MHz.
176 ABI cases: all six hooks, four incoming clocks, IFF on and off. 2,114 injected IRQs, 27 of them NMOS LD A,I/R
PV-clearing cases; 48 standalone IRQ cases (all clocks, hooks active and not, R rollover and bit 7). Not exhaustive.
Longest atomic block including DI and the EI grace: 23.75 T at 3.5 MHz equivalent (6.79 us), over 44 captured and
cold-cache cases.
Shared change: hlib_iff's opt-in `HLIB_IFF_FIXED_R` makes both IFF read paths six M1s (five before DI on each path, so
R advances the same whether or not the first read reports PO); callers without the define assemble the old bytes.
`hooklib.selfcheck` covers it (16 captures, an omitted-padding negative); `iff_audit` no longer pairs reads across an
IFDEF/ELSE/ENDIF line.

Original row execution at 28 MHz plus hlib_pace K96 gives the original pace; K104 was 4.107% slow in the busy fixture.
Probe: the player's own update, 38183 with IX 36634, never the generic object loop. Three starting video phases per
scene, original, default and Enhanced from the same RAM:

| Scene | Three phases against the unchanged original |
|---|---|
| quiet | +0.204%, -0.662%, +0.204% |
| busy (four enemy records placed away from the player) | +0.006% each |
| sound (the original beeper routine every 10 updates) | -0.964%, +0.910%, -0.964% |

Player X/Y/room equal at every update; default and Enhanced timings identical. Natural-play traces diverge through
R-dependent encounters and are not pace evidence. Beeper writes in the original order, median edge-period difference 0%,
all at 3.5 MHz. A 48K beeper game: the broad AY-port counter also counts keyboard reads; no AY claim.

## DMA/DDMA assessment
Read docs/DDMA.md and docs/DDMA_IMPLEMENTATION.md. The per-slot image cache already skips unchanged patterns.
Whole-hook profile (pilot `work/hook-profile.json`): 44 captured and cold-cache calls. A cold figure change uploads 512
bytes, a repeated one 0; a whole move call takes about 2.77..3.18 ms including the original bookkeeping and pace waits.
DDMA 2D, transparency and physical addressing do not do the original XOR or bit shifting; the sprite upload is
memory-to-I/O. DMA could speed cache misses but needs shared DMA ownership, core gating and a measured crossover.
No DMA code: CPU OTIR at 28 MHz is the tested path and every controlled pace trial meets 2%.

## ROM, memory and loader
Whole hidden Sinclair ROM (patch.whole-altrom-image), not the 26.11 printer-buffer subset; its own IM 1 entry/exit
trampolines at 0038/004F are audited exceptions. Warm NextZXOS's delayed DivMMC RST 38 trap is disabled by clearing only
NR 0x0A bit 4 and unmapping E3. Direct and NEXLOAD entry checks pass in both colour sets, with R = 32 and speed 0.
NEX highest bank 16, 278,528-byte span, nine stored banks: fits 1MB. Tail 5B00, state 5B80..5BFF.
Real dot-command loader (pilot run and this release round, private card copies only): default, Enhanced, Enhanced with
all five trainers, and the menu .nex; the written .nex byte-exact with nxc.py, live trainer bytes checked, play reached.

## Trainers
| Trainer | Runtime target | Pre-LDIR NEX | Behaviour proof |
|---|---:|---:|---|
| Infinite lives | 59375 | 59376 | 1, 3, 6 lives not decremented |
| Infinite gems | 38042 | 38043 | 1, 3, 7 gems not decremented |
| No enemies | 45018 | 45019 | Enemy slots stay empty |
| Weapons stay put | 59590 (corrected) | 59591 | One layout over 256 FRAMES seeds |
| Start with 9 lives | 36980 | 36981 | The initialiser stores the chosen 1, 3, 9 |

The archive's runtime 59591 removes one RLA and still gives four layouts. 59590 changes the FRAMES-address high byte to
ROM 0x0078, which holds 34 in the Sinclair ROM: one layout for all 256 seeds. The archive's 128K-only fix is left out.

## Evidence and limits
33 recordings, 131,756 recorded frames (131,789 frame callbacks with each initial state), 249,111 figure plots, 125,499
picture checks, 96 rooms, 66 observed figure IDs: zero differences. Menus, play, rooms, rope, death, game over and
ending fixtures; room tours start from labelled teleport and cheat states: no natural completion.
14 of 14 broken controls detected: X/Y one pixel off, erase, upload, colour, attribute paint, AF/IX loss, room/clear
hiding, scenery, spare sprites, 8-byte slots, row write.
Six native soaks: 3 seeds x 12,000 frames a colour set; 32,814 player updates, three deaths and 151 room changes a set;
equal default/Enhanced counters; no fast beeper writes or emulator errors.
Known issue: past X 232 a figure is clipped where the original wraps its XOR row; not seen in recorded play.
Missing: hardware; natural full-game completion. No generic `--verify --stamp` claimed: the external release suite is
the proof (pilot run release-20261106, `work/final-proof/`).

## Hardware checklist
Default and Enhanced: ropes, bubbles, rooms with several enemies, death, game over, restart; the loading screen and each
trainer. Compare player pace and beeper effects with the unchanged 48K original. Look for tearing during pattern changes.
Record the board and core version.

## Lessons
- [local: Underwurlde release evidence] SkoolKit per-call int_active 32 can clear both LD A,I PV reads without an
  accepted interrupt; paired-hook simulators use 0 and real injected IRQs are tested separately.
- [tool nexclash/hooklib.py] Fixed-M1 IFF reads need equal fetch counts on both paths: shared opt-in macro and 16
  hooklib cases added, old callers' bytes unchanged.
- [local: Underwurlde release evidence] Pre-LDIR trainers need per-instruction translation; the weapon-layout effect
  was proved over 256 seeds instead of checking bytes alone.
- [local: Underwurlde release evidence] Natural encounter divergence is not pace evidence; controlled fixtures keep
  identical player states over several video phases.
- [local: Underwurlde release evidence] A whole hidden ROM does not remove a delayed DivMMC RST 38 trap; clear only its
  enabling bit and keep the other controls.
- [doc docs/LEARNING.md §1. Source refresh and verification freeze] Integration onto newer main (2026-11-07): the
  frozen engine files plus the reviewed registry and IFF patches rebuilt both NEX files byte for byte, so the proof
  carried; shown by rebuilding and comparing, not assumed.

## Friction
- reuse: [local: existing per-slot image cache and shared hook helpers kept; no new generic probe]
- retries: [local: the final suite leaves out the old K104 and synthetic int-window failures, kept as diagnosis]
- environment: [local: Python 3.14 forkserver needs a main guard; dead-register subprocesses use an explicit fork context]
- hand-rolled: [local: controlled busy and beeper fixtures live in the run evidence; the player-update probe is per game]
- scratch: [none: work scripts stay in the pilot run; no scratch files in the toolkit]

## Technique use
- detect.gameplay-screen-readers: helped: original screen reads classified before row suppression.
- patch.whole-altrom-image: helped: independent of the NextZXOS 26.11 printer-buffer ROM path.
- patch.restore-speed: helped: incoming clocks restored, all six hooks tested at all four values.
- patch.pace-limiter: helped: controlled player-update pace within 2% in every trial.
- optimise.pattern-cache: helped: repeated images upload 0 bytes; cold ones 512.

## Stage log
2026-11-07: release round: approved-art identity, interrupt/R repair, K96 pace calibration, trainers and private-loader
checks; frozen replay and six native soaks passed.
2026-11-07: integrated on main 102091f (branch nexttang/underwurlde-1.1): byte-identical rebuild of both builds, record
input paths made reference-relative, selftest --tools, --canary, --game underwurlde (rebuild) and doccheck PASS; .nxc
v1.1 review package with real-loader runs on NextZXOS v2.09 and 26.11 card copies.
