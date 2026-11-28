# Elite (Braben / Bell, Firebird 1985; standard 48K releases) - engine: elite_std (stage 2: record done, hardware untested)

Techniques: `patch.inbetween-views`, `patch.whole-altrom-image`

## Next session
Stage: 2 (build)   State: M8 SD save / load 2026-11-24 (## SD save); title speed 2026-11-28
Inputs: C:\1NEXT\elite_work\tapes\t1.tap ([a]), ejcv.tap (= t8, Joystick), e128.tap (original); work folder C:\1NEXT\elite_work\std    Branch: add-elite
Checks: verify (full scenario set) a / jcv / e128 all cases PASS + title renders ok + negative controls caught; CSpect: title (frames) -> launch -> flight, all three
Pending user answers: none
Start with: `python -m nexclash.elite_std start TAPE start.z80` then `python nexclash.py auto start.z80 [--quick 1]`
Read: this file, games/elite.md (the hack engine: Build plan / Lessons), games/elite_hack.md, C:\1NEXT\elite_work\STD_NOTES.md
Open: ## Smooth title ship (M5, 2026-11-23; asm/elite_std_hooks.asm, elite_std.py VERSIONS[v]['ttl'], elite_std_verify title cases)
- Goal (owner): the title ship turns at the original's angular speed but is drawn every frame (50 fps), mono, same
  models, same look; flight unchanged. Both rotating-ship screens are covered: "Load New Commander (Y/N)?" (a, e128;
  layout A 0x7378-0x7386, B 0x71A2-0x71B0, no HALT in the loop) and "Press Space, Commander" (jcv's only title; a /
  e128 after N; A 0x73C3-0x73F2, B 0x71E5-0x7210, HALT once a pass). The model is fixed per screen: Y/N always the
  blueprint 0x6490 (event 0x79); Press Space cycles 8 models by a counter (A 0x7470, B 0x7286) per entry.
- Measured (simulator, 3.5 MHz): frames per pass jcv 8.68, a 10.90, e128 10.86; the draw is most of a pass (jcv
  316k of 560k T); the ship turns about 1/16 rad a pass. Choice: extrapolate with the game's own draw, not smaller
  rotation steps (the fixed-shift step A28D would change the pass-boundary state); every game pass stays the original's.
- Hooks (8 same-length CALLs per version, title loops only): h_top (clear's CALL: 28 MHz, phase), h_bg (rotate + draw:
  the cleared + text buffer kept in page 27), h_copy (HALT: the copy at a frame top), h_prea / h_pree / h_prej (after the
  copy): L = the pass's lines at 28 MHz, D = L * K / 312 frames at 3.5 MHz; the frames not the game's own get renders.
- Render (game code, own stack in page 26): buffer = background (DMA), slot 0x6159 extrapolated by w = j / D of the last
  pass's change (no extrapolation on a change of 0x2000+), the game's draw (A6DF / E008), HALT, the game's copy (7FBE /
  7398, 4K at 28 MHz in the top border); then the slot, the draw's work bytes (prm.rng) and the buffer put back.
- Memory: alt ROM entries from 0x3A3D; bank 13: page 26 = 0xF3 0xAF, variables, prm, code, saves, stack, pass log at
  0x1F00; page 27 = the background + the alt ROM's IM 2 table / h_isr copy at 0x1900 (+ the SD code, ## SD save).
- K from the CSpect pass log vs the original's frames per pass: 8.27 (a), 8.28 (jcv), 8.29 (e128); prm.kf 68 / 72 / 74.
- Verified: lockstep (title CALLs run as replaced, so the game's passes equal the original's); title_render_check: each
  render on a copy of the original put back leaves RAM as the pass left it (a 125, jcv 70, e128 120; all 8 Press Space
  models, rcheck2.py); CSpect: every displayed frame differs from the one before (m5\*_frames.png), Y / N / SPACE / 1.
- CPU speed (2026-11-28): each pass gives back the caller's speed (was 3.5 MHz); speed_check.
- Limits: game work at 28 MHz must stay under a frame per segment (measured at most about 0.8); a big model may need two
  frames (counted). Hardware: ## Open.

## Owner decisions
(2026-11-23) rebuild for the standard releases so the game looks and starts as the original; the
Russian 128K hack (engine `elite`, games/elite.md) becomes an NXC option (games/elite_hack.md). Colour / 50 fps
renders are enhancements, options, not the default. Lenslok skipped (the build starts after the check). Three versions
supported: "[a]", the Joystick / cursor tape and the original Firebird tape.
(2026-11-24) Commander save / load on the SD card, not tape (tape cannot work on the Next): one file per name, the
first 8 characters + .ELA / .ELB, an empty name loads the last saved; only the "Press Any Key" wait is skipped; SD only.

## Versions (nexclash/elite_std.py VERSIONS; profile signatures per version, at the start state)
| | a ("[a]" tape, t1) | jcv (ELITEJCV = "[Joystick]", t8 / ejcv) | e128 (ELITE128 = original Firebird tape) |
|---|---|---|---|
| Tape | BASIC + 37-byte code + 49,065 bytes at 0x4000 | BASIC + loader + 42,240 bytes (a frozen game) | BASIC USR 28672, SCREEN$ (6,914), 40,801 scrambled |
| Protection | Lenslok (code at 0xC799) | none | none (scrambled block) |
| Real start | 0xD07F after the check: init, IM 2, title "Load New Commander (Y/N)?" | the loader's IM 2 / I 0xFD / SP 0xFFFD / JP 0xD07F: a NOP slide to RET into the title loop, "Press Space, Commander" | 0x716B after the unpack (frame 0): init, title "Load New Commander (Y/N)?" |
| Code | layout A | layout A, same code; commander MILICEVIC (as the hack) | layout B: the same game assembled at other addresses (clear 0x745F, copy 0x7398, main-loop top 0x72FD, dispatcher 0xF2CA, ship lines 0xF204 / 0xF232 / 0xF253 / 0xF27F); own font glyphs; no ROM calls |
| IM 2 table 0xFD00-0xFE00 | not uniform (key data): fix at 0xD09E, 0xFF4C | same: fix at 0xFF4C + the start state's I | uniform (257 x 0xFE): no fix |
| Tail | 0xBE00 | 0x5000 | 0x5000 (all three: written before read, access scans) |
| M3 build MD5 | 355c82559dae3614c547eea45d56525f | 70892450b094794e0e828123fb3ca5f5 | 835a19547bec49d07430d899404c67e7 |
All three are 48K games (no 7FFD, no AY; ELITE128's banks 1, 3, 4, 6 stay empty). Pace in quiet flight: A 5.0 frames per
pass, B 4.0; interrupts every frame in both layouts. The hack is layout A with its changes: its toggles (M4) fit a / jcv,
e128 would need them relocated.

## Survey (M1, 2026-11-23; C:\1NEXT\elite_work\std\survey.py / access.py / ports.py, scripted keys)
Layout A [observed]:
| Item | Standard (measured) | Hack (games/elite.md) |
|---|---|---|
| Pace in flight | 1 pass per 5.0 frames (Lave, station only) | ~10 frames per pass (busier scenes) |
| Interrupts | every frame (1000 / 1000 in flight) | ~2/3 of frames (long DI) |
| ISR | IM 2 I = 0xFD, vector 0xFEFE, JR 0xFF25: own stack 0xFFBF, key scan 0xFD69, controls 0xFE01 | same body; the hack mutes it around ship draws |
| Ship draw | 0x9E44 CALL 0xA6DF on the normal stack, interrupts on | 0x9E44 JP 0xF8B4 wrapper: DI, SP 0x4020 |
| Clear / copy | 0x8080 DI + PUSH fill of 0xC000-0xCFFF / 0x7FBE LDI blocks, once per pass | LDDR / another copy |
| Buffer writers | planet 0x9119 / 0x911E, launch rings 0x917D / 0x9182 / 0x91BD / 0x9083, stars 0x7CA2, ships 0xB436 / 0xB466 / 0xB487 / 0xB4B3, sun fills 0x8B15 / 0x8B1A / 0x8B23 / 0x8BB6 / 0x8BBB, text 0xD549; docked pages use 0xC000+ as scratch (0xD0xx-0xEFxx writers) | WRITERS_A/B/FF/LDDR in nexclash/elite.py |
| ROM | executes only 0x22B0-0x22CA (PIXEL-ADD) | ROM font |
Keys (layout A and B, keyprobe.py): M / N roll, S / X pitch, SPACE faster, SYM slower, A laser, T target missile, F fire
missile, 1-4 views (1 launches when docked), H hyperspace, I galactic chart, O short-range chart (S / X move the target),
K market, L status, P data, ENTER inventory. On the title and the status page a key must be held ~20 frames.
Encounter dispatcher (layout A 0xB867, B 0xF2CA; A = event, high nibble a count): events 1 (four type 15), 2 (type 1),
5 / 8 (two of type 3 / 5), 6, 7, 9 (one ship) spawn via 0xB898 (type table 0x6180, 4 bytes each).

## Verify (M3, 2026-11-23; nexclash/elite_std_verify.py, its docstring = the method)
- States: free runs of the start state with key schedules (scenarios(): title, docked pages, launch, flight with roll /
  pitch / speed, charts, hyperspace (target moved on the short-range chart, H), the sun (rear view after arrival)), and
  combat injected with the game's own dispatcher at the main-loop top (events 1, 2, 5, 6, 7, 8, 9; firing / turning; a
  missile case with T / F; a 1,200-frame fight).
- Lockstep: original (Sinclair ROM, bus byte 0xFF) and build (alt ROM image of the patch, sites, I = 0x39, a different
  bus byte per interrupt: 0xFF, 0x00, 0x07, ...): PC equal after every instruction, registers (not I) + RAM + port
  writes at every pass and at the end; the build's extra JP at 0x3A3A is not timed and its R step is undone.
- Results (full set, 16 cases, 5,740 frames each version): a 634 passes / 5,056 interrupts, jcv 691 / 5,004, e128
  610 / 5,090: all equal. Negative controls caught: a table byte (bus 0x07 lands on 0xFEFF), a site left at 0xFD
  (vector from the game's non-uniform table), e128's own table byte (vector, not the RAM compare).
- Coverage [observed: coverage.py / kills.py, version a]: sun fills, planet, launch rings, stars, ship lines, 8 ship
  blueprints (station, title ship, types 1, 2, 3, 4, 5, 15), one kill (0xB703 SET 4 in combat_e9), a type-1 spawn in
  the missile case (combat_missile never hits: the four event-1 ships ECM it).
- Gap cases (2026-11-24, GAPS in elite_std_verify.py; recipes proven by free runs in C:\1NEXT\elite_work\std\gaps\A|B):
  flight state + equipment pokes (A 0xD082-0xD08D, B 0xA844-0xA84F) or events, then docking computer, escape pod, energy
  bomb, galactic hyperdrive (G+H), in-system jump, game over (A: planet poked onto us; B: event 2, shields 0), explosion,
  missile hit (B pokes 0xA871 / 0xA872 past the target's ECM test 0xF81B: not natural play). A case that does not execute
  its proof routine fails (negative caught). a 25 cases, jcv 24, e128 25 PASSED, builds unchanged. C with the docking
  computer gives no Game Over (flag + station near suffice).
- e128 writers (gaps\B\writers.json): main four as layout A, plus screen-direct circles, the explosion disc 0x8572 (PUSH
  spans), attribute fill 92A8, LDIR 8F50, E173; none hooked by the plain build, all needed by a layout B renderer.
- Equivalence note: on the Next the build's R runs one ahead per interrupt (the JP); the standard code reads R only in
  the Lenslok code (0xC297 / 0xC29A, layout A; none in layout B), so no consumer.

## Build (M2, 2026-11-23; versions M3)
nexclash/elite_std.py, nexclash/elite_std_verify.py, asm/elite_std_hooks.asm, docs/profiles/elite_std.json, one line in
nexclash/engines.py. auto: build, automap off, nextboot.check (with and without NEXLOAD), unit cases on the .nex (the IM 2
path for every bus byte, the rest of the alt ROM = Sinclair's) with the negative controls, then the lockstep verify
(--quick: six cases). CSpect 3.x (MCP), all three: title, N / SPACE -> status page, 1 -> launch -> Front View, flying;
I = 0x39 and PC caught at 0x3A3A once (jcv). Hardware: not tried.

## NXC (M4, 2026-11-23; C:\1NEXT\elite_work\std\nxc, scripts mkload.py, poke.py, hk.py, harness_screen.py)
- Tape targets: `nxc.py make Elite_<v>_loading.nex TAPE --start v/<v>.z80 --rom 2` (zx0: NXC_ZX0_DIR). All three rebuild
  byte for byte; e128 from its 0x716B start too (47,489 bytes from the tape, 462 carried). a: 45,296 / 477; jcv 42,963 / 4,170.
- Loading screen: Elite.scr is on no tape. [a]'s main block starts with nearly the same picture (offset 222; 73 hidden
  bytes differ), jcv has none, e128's SCREEN$ (offset 172) says "128K VERSION". So the patch carries it: the build .nex
  has Elite.scr as its header screen (byte 10 = 2, atom_ant.loading_nex) and INF1 `build_screen=nex` (C:\1NEXT
xc	ools
xc.py
  in the nxc repo; the vendored nexclash/nxc.py has no build_screen). Shown at ENTER after the keyed check; no hold.
  Z80 harness of the real loader (harness_screen.py): .nex = the build, display = Elite.scr but the Patching line, all three.
  CSpect closes on any NEX header screen (games/castle_master.md), so CSpect runs use the plain .nex.
- Toggle map (HACK_FUNCTIONS.md): the hack is a rewrite. Its gameplay code (NPC-vs-NPC engine 7A9E-7EDD and F92D-FAC9,
  missions/upgrade 5E78-5FD4, D67A-D787, FCEA-FD40) lives in space freed by its display rewrites (star field, fills,
  line clipper, ROM font, packed models) and shares its variables (D08E upgrade, D08F stage, D062 tally, B452 NPC records).
  Separable as same-length bytes: pirate pack size (B96F). Need the NPC record table: hostility (9D94/F9C9), who fires at
  you (A65D/FA84), NPC combat. Need packed models + their readers: 23 blueprints, type swap (EF01), per-ship damage
  (B5CA/B5D8 with blueprint +0x15). Need the upgrade flag: J turbo, galaxy select. Shop Y/N needs token table + 6ED4.
  Docking "stricter" is not: std already tests each high byte &7F; the hack only adds 7103.
- Toggle 1 "Bigger pirate packs" (a, jcv; kind 4): B96F AND 1 -> AND 3 (3-6 pirates, std 3-4). Reference: the start
  state with the same byte (poke.py); `auto` on it gives the byte-edited variant exactly and its lockstep verify (16 cases,
  combat_e1 = the pack spawner) PASSED against that toggled original. CSpect: pack injected at 0x74E4 -> 5 ships (a),
  4 (jcv), flying and firing. `--bare` with and without the toggle = the variants' MD5s.
- Toggle 2 "Russian hack gameplay" (a, jcv; kind 4; owner option c): C:\1NEXT\elite_work\std\mkhack.py swaps in every
  byte where the five hack snapshots agree and differ from the version's start state (about 13,600 bytes), keeping
  4000-5D6F, C000-CFFF (back buffer), D046, D04F-D0C8 (commander block / start code) and, for [a], BE00-BFFF (squares
  table its start code builds); bytes that vary between the hack snapshots stay standard. Engine versions `a_hack` /
  `jcv_hack` (profile signatures: 9E44 JP F8B4, 7FBE LD HL,C000). Fixes of our own:
  - D04E (save/load vector) = XOR A; RET: the hack's routine is TR-DOS (JP 3D2F at D938 = the ROM font on the Next).
  - 5800-581F = 0 and the start stack in the screen: the hack's main stack is at 0x411C (F8B4 sets SP=411A after each
    ship draw; F8E4 saves 40F0-411F to FFD0-FFFF around the ship loop, so a stack at FFxx is overwritten). jcv: RET
    address 74A2 moved from FFFD to 411A (SP=411A). [a]: start code ends LD SP,411C; push 74A2; JP D298 (the game's
    new-commander routine), as the hack has no title (its 7366-738D is a subroutine).
  - Ship slots take the stable bytes: slot 0's blueprint pointer (606B) must point into the hack's packed table, or the
    NPC record init (7A9E) restarts the main loop every pass.
  Came along (inseparable): the ROM font (hack code in the Elite font, 5D70-6047), star field / fills / line clipper /
  packed models (their space holds the NPC engine and blueprints), stack in the screen with the top attribute row
  black, Kempston removal (the ISR's joystick read space holds hack code at FC25-FC38; the jcv toggle has no joystick),
  no title screen (starts on the status page). Not taken: the TR-DOS save/load (neutralised: no commander save/load
  with the toggle on). The hack's own B96F is AND 3, so it overlaps toggle 1: `--excludes`.
  Verified: build-with-hooks vs the unhooked swapped game (same lockstep verifier, versions a_hack / jcv_hack),
  16 cases PASSED (a: 471 passes, 3,779 interrupts; jcv: 578 / 4,385), negatives caught; that checks the engine layer
  only, the swap is the hack's own code. Simulator: status, launch, flight, encounters 1-9; the NPC loop (7C60) runs
  every pass. CSpect [a]: status, launch, flight, pirates + event 2 injected, ships fly and attack. Not seen: an
  NPC-vs-NPC laser (7D25) or kill (7BF5), in our variant or in the hack's own snapshots over 2,500 frames after launch;
  docking (std: reached since 2026-11-24 by the gap case; the toggled build not tried).
- M5 rebuild (2026-11-23, the smooth title ship; C:\1NEXT\elite_work\std\m5\mk5.py, mknxc.sh; M4 files in nxc\old\m4,
  out\m4, tg\m4): NXCs a 32,000 bytes, jcv 34,581, e128 17,993; `--bare` MD5s = the builds byte for byte:
  a plain 3853cf919f95d28660f381e812597086, packs 8080110641c7a9025317a0ba825f9dfe, hack 4391d41dd0ae8d7bc7f8a24594c555f9;
  jcv plain 991a8347c8184a9cd0f89670f0f5e715, packs fc26ed3aa8b13e0ca7cd747d1b773fb9, hack 603f0eb893811b6b485ec1ddaa47ea67;
  e128 plain 17af428111ddfc5ac50a9e0d7a81cdd9. Plain .nex (no header screen): a fdf902724678c8bf6cd9ad00ca1fa687, jcv
  2b1cc73a21c038d25de35cee46b159bc, e128 4862999097474b509e4304749c08d66f. Pack builds = base + 0xB96F (1 byte);
  pack / hack builds verified again (17 / 16 / 16 cases); harness_screen.py: all three OK.
- Option (b), bundles as their own toggles: not feasible as asked. never.py (access scan over the scripted runs, jcv)
  leaves 11,099 bytes untouched in runs of 16+, but they are models of ships not met, docked/market/save code and
  so on, not free space; no dead space was found that the NPC engine (about 1.7K plus the B452 table) or the packed
  blueprints (about 3.6K plus about 15 readers) would fit. The hack gets its space by rewriting the display code.

## SD save (M8, 2026-11-24; asm "SD save / load", elite_std.py VERSIONS[v]['sd'], elite_std_verify.sd_check)
- Sites (survey C:\NEXT\elite_work\std\saveload): docked SYMBOL SHIFT = ACCESS MENU (1 load, 2 save, 3 exit). Load
  CALL 0x0562 at A D954 / B D32E, save CALL 0x04C6 at A D99C / B D376 -> CALLs of h_lda / h_ldb / h_sva / h_svb (alt ROM);
  the key wait before the save (A D996 / B D370) -> NOPs. Block IX = A D054 / B A816, DE = 0x66 / 0x68, name first;
  typed load name A DED0 / B AC25. The game's test after a load: empty typed name takes any, else
  equal up to the 0 (all 11 equal = mismatch -> it loads again); failure (NC): "Tape Loading Error", commander restored.
- Hook: DI, page 27 at slot 2 (0x5000: code; the ULA reads bank 5 itself), own stack, I = 0x5B over a 257 x 0x5D table
  with EI / RETI at 0x5D5D (DivMMC covers the alt ROM's table in esxDOS), NextReg 0x0A bit 4 (automap) on for the
  call only, esxDOS calls with IX = HL. Save: <first 8>.ELx then _LAST.ELx; load: <first 8> (empty: _LAST) into a
  buffer, the game's name test first (mismatch = NC, no loop), then the block. All state put back; carry = done.
- Verified: sd_check (engine unit tests): a Next memory model with a fake esxDOS checking each RST 8 (ROM in slots 0 / 1,
  automap on, stack / buffers / vector above 0x3FFF; it returns with EI, registers scrambled): saves, loads by name,
  empty, missing, clashing name, a refusing card; RAM changed only at the block; negatives caught. Lockstep: the 3 sites run as the replaced instructions ('sd hook'; no case reaches them);
  a 25 / jcv 24 / e128 25 PASSED. CSpect (-mmc=C:/CSpect/sdtest/), all three: save JOE / MILICEVICH (files 102 / 104
  bytes, MILICEVI.ELx, _LAST follows), load JOE, empty (= last), BOB (Tape Loading Error, commander kept), launch, fly.
- Notes: bytes after the name's 0 keep the old name's tail (as on tape). jcv's MILICEVIC (D054) shows as JAMESON after
  Press Space (backup D232; the original's path). The hack toggle has no SD hooks.

## Open
- Verify coverage: the gap cases (2026-11-24) cover docking, escape pod, energy bomb, galactic hyperdrive, in-system jump,
  game over, an explosion, a missile hit; still no natural (unpoked) missile hit or death in layout B.
- e128's own layout: writers surveyed (Verify); hack toggles would need relocation for it.
- Converter: 0xC000+ tails refused on 48K too; tails here from access scans (lesson 2).
- Hack gameplay toggle: NPC-vs-NPC fight not yet provoked; docking not reached; disk save/load off with it on; its
  builds fail gap_in_system_jump (proof 0x7EFF not reached: the hack's own jump code; every lockstep case equal).
- SD save: works on the owner's Next, all three versions (2026-11-24); cores before 3.01.10 untried.
- Option (b) bundles: no proven free space (## NXC); would need relocating the display rewrites too.
- Smooth title ship: not tried on hardware (DMA continuous mode, 28 MHz copy inside the top border are CSpect's); the
  draw-segment-under-a-frame assumption is measured for the 8 + 1 models only.

## Plan (M1-M8 done)
- M6 (2026-11-24): record docs/records/elite_std.json (order 277): the "[a]" start state, reworks jcv / e128 on their own
  (Lode Runner 128K pattern), the tapes as inputs (each start state rebuilds byte for byte from its tape); stamped.
- M7 (2026-11-24): the 8 gap cases (## Verify); NXCs to the nxc repo, branch elite-patch, patches/Elite (1985)(Firebird).
- M8 (2026-11-24): SD save / load (## SD save); NXCs remade, record MD5s updated.

## Stage log
2026-11-23  stage 2 M1 survey + M2 skeleton (standard release)  ~2.5 h  ~90 calls  0 user rounds
2026-11-23  stage 2 M3 three versions + lockstep verifier  ~2 h  ~80 calls  1 user round (decisions via the coordinator)
2026-11-23  stage 2 M4 NXCs, loading screen, toggles (pirate packs, hack gameplay), option (b) scan  ~4 h  ~170 calls  3 user rounds
2026-11-23  stage 2 M5 smooth title ship (hooks, renders, verifier title cases, NXC remake)  ~3 h  ~150 calls  0 user rounds
2026-11-24  stage 2 M6 record + M7 gap cases, e128 writers, NXCs to the nxc repo  ~2 h  ~120 calls  3 user rounds
2026-11-24  stage 2 M8 SD save / load, sd_check, CSpect, NXCs  ~2 h  ~90 calls  1 user round

## Lessons
- [local: Elite [a] tape] the "[a]" release carries Lenslok; the expected code sits in RAM (0xC799) once the prompt is up,
  so a deterministic start state comes from typing it in a free run, and the real start is the entry after the check.
- [deferred Open: reconsider when a second 48K engine starts from a game entry with SP=0xFFFF] the converter refuses
  0xC000+ tails even on 48K; an access scan (first access per address over a scripted run) found 0xBE00 written first.
- [local: Elite versions] ELITE128 is not a 128K game: the original Firebird release, a relinked layout of the same code
  with a uniform IM 2 table; the JCV tape is a frozen game whose loader jumps into a NOP slide (observed: traces).
- [deferred Open: reconsider when another free-run engine needs combat or rare events] injecting an event through the
  game's own dispatcher at the main-loop top gave reproducible combat states with no RZX (ships spawned by game code).
- [deferred Open: reconsider when another engine's only change is an IM 2 vector] a lockstep of original and build per
  instruction (the build's extra JP skipped, T and R aligned) is a cheap exact verifier: 5,740 frames in ~25 s.
- [local: Elite standard title] the title ship draw (A6DF / E008) reads only the slot (IX) and blueprint (IY), not the
  rotation's scratch, so a changed slot gives a changed picture; its work bytes are a few hundred, mostly self-modified
  line code (B43B.. / F209..) [demonstrated: title_render_check, 8 models each layout].
- [deferred Open: reconsider when another engine renders extra frames between a game's passes] extrapolating the last
  pass's change (not interpolating) shows the game's own frame at each pass boundary with no lag; at 1/16 rad a pass
  the error at w = 1 is about 0.4% of a vector, below a pixel [observed: CSpect frames].
- [deferred Open: reconsider when another hook needs a pass's 3.5 MHz length while running it at 28 MHz] time = raster
  lines at 28 MHz (NR 0x1E/0x1F against the line read just after a HALT) x K; K = 8.27-8.29 here (contention and the
  ISR at 3.5 MHz), from a pass log in the hook page against the original's frames per pass [measured].
- [local: Elite standard title] a page mapped at slot 1 over the alt ROM must carry the IM 2 table and the handler's
  JP at the same offsets, or an interrupt while it is mapped jumps into data [inferred: design; no failure seen].

## Technique use
- tools/probes/sprite_leftovers.py: no help: not needed (no sprites) (2026-11-23)

## Friction
- reuse: [local: Elite standard survey] survey.py / access.py / keyprobe.py / coverage.py are in C:\1NEXT\elite_work\std;
  to move to tools/probes once a second game reuses them. M5 reused the hack engine's dec_v / enc_v (asm/elite_render.inc,
  copied into asm/elite_std_hooks.asm: the two engines share no include).
- retries: [local: elite_std_verify] the lockstep first diverged at a HALT: skoolkit's HALT reads T, so the build's T
  must follow the original's; the title key needed ~20 frames held (5-frame presses were missed in e128). M5: the hook
  code first overran the alt ROM's free area (moved to a NEX page); an NXC set refused toggle builds whose bank list
  differed from the base (the hack builds now carry bank 13 too).
- environment: [local: selftest reference] selftest --game elite needs elite/elite.z80 in the reference folder (a copy of
  DockingElite.z80); staged in C:\1NEXT\elite_work\std\ref.
- hand-rolled: [local: start state] the start .z80 is made by the engine (start_state), not by a toolkit command.
- scratch: [local: work folder] run.py / scr.py / mkstart*.py / entry.py / inject.py / tryk.py in C:\1NEXT\elite_work\std;
  M5: zdis.py, titlecost.py, titlepace.py, drawwrites.py, slotprobe.py, rcheck.py, rcheck2.py, grid5.py, m5\mk5.py,
  m5\mknxc.sh there (CSpect's debugger SAVE wrote no file: screenshots + PIL diffs instead).
