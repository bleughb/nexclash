# Treasure Island Dizzy (Dizzy 2, Codemasters) - TID engine, dedicated builder

## Next session
v1.1 is on main and published (nxc 440fe60, played by Jon in JNext 2026-11-08). Main's
own recipe rebuilds the published bytes: rework v11_default writes `_sprites_published.nex`
(277cfbff, Enhanced's banks reserved so one .nxc header serves both) and v11_enhanced
`_sprites_loading.nex` (31d8c232). Inputs stay local and out of this repository: the 128K
snapshot, DIZZY2.scr, the five recordings; Enhanced also colour-source.256 and
source-palette.pal, and rebuilds only with them. Do not repaint the approved set without
requested edits. Open: hardware test, natural completion.

Historical 48K base below; the v1.1 release targets the exact 128K archive.
Engine facts shared with Fantasy World / Magicland: games/tid_engine.md.
Builder: nexclash/dizzy_patch.py (dedicated: bubble virtual read; printer only).
Profile: docs/profiles/tid_treasure_island_dizzy.json; signatures.json (`tid_engine`).
Reference files (private repo, specnext/reference/treasure_island_dizzy/):
- dizzy2_game.z80 (in game, md5 7578947f) - selftest input treasure_island_dizzy.z80;
- dizzy2.z80 (title screen, md5 9443f0cc) - optional selftest input treasure_island_title.z80;
- recordings dizzy2rzx, dizzy2newrzx.

| Output | MD5 | Status |
|---|---|---|
| treasure_island_dizzy_sprites.nex (in game, printer) | 8b4d0847d68fce3215bd43a0e116e682 | verified; hardware untested |
| treasure_island_dizzy.nex (in game, plain) | 4dae1a3a15b2158642a5d5b82de92ef7 | |
| treasure_island_title_sprites.nex (title) | 85e054fe4bce8e4b3a8e336aac432f58 | verified |
| treasure_island_title.nex (title, plain) | 70890aba7d821fba8a41e63636eb58be | historical plain build; no current hardware test |

Verified: dizzy2 RZX + 29 underwater checkpoints - 6,338 plots, 6,326 erases, 25,299 ISR, 18 wipes,
7,436 bubble tests (340 Dizzy-dependent): all identical (docs/VERIFICATION.md).

## Facts (addresses; engine routines described in tid_engine.md)
- Plotter 39774, eraser 40087; plot site CALL at 61578; undo buffer 40149; frame table 40249.
- Room wipe 44931; no box routine; ISR hide call 61362; pixel test 62333.
- Game logic READS the player's pixels: underwater bubbles at 63000 -> the patch gives them a
  virtual read (screen as if Dizzy were still drawn).
- Printer buffer free.
- Title-screen ISR 63328 plays beeper music (timing-critical: never hooked); it writes 63340
  (self-modifying - keep out of patch sites).

## Open
Historical 48K items below; the 128K rework resolves the trainer issue separately.
- The auto-recorder gets no response to input on the in-game snapshot (start/controls not found):
  needs --start/--keys or a user RZX.
- `--poke` cheat option (immunity 29289,201) not built.

## Hardware checklist
1. Title music unchanged (not hooked); game starts.
2. Dizzy is sprites: animates, faces both ways, no clash, no leftovers when he moves or the room
   changes.
3. Underwater: bubbles behave as in the original (they test Dizzy's pixels).
4. Inventory / dialogue screens: Dizzy hidden or drawn as the original does.
5. Faults: Fuse "Record from snapshot" on dizzy2_game.z80, autosave off, send the RZX (+ where).

## Rework (opt-in) v128: the 128K release (engine `tid128`; Jon Attree, 2026-11-05)
Dean's builds (4dae1a3a / 8b4d0847) are untouched and stay his record's; `selftest --game treasure_island_dizzy`
rebuilds them and this rework = recorded.
- Why: the 128K file (TOSEC `Dizzy 2 - Treasure Island Dizzy (1989)(Code Masters)(128K).z80`, db6ccbeb) plays AY
  music from bank 6 (CALL 0x7202 pages it in). Every patch site is byte-identical to the 48K game's (bank 0 holds
  0xC000-0xFFFF in play; the title pages bank 6 there).
- `nexclash/tid128.py` (Dean's dizzy_patch read, not copied): 128K detector / apply; trampolines kept at
  0x5B00-0x5B50 (128K ROM 0's paging routines there: the game never touches them, the verifier fails any access),
  0x5B00-0x5BFF put back after NEXLOAD by a wrapper round Dean's set-up; whole alt ROM image (ROM 1 as the ROM path
  check models it + the register block at 0x386E); a 128K copy of nexclash/verify.py that also checks the bubble
  test 0xF618 and ends the ISR event where the hook hands over to 0x7202; Dean's two hook-page entries (plot, bubble)
  through a wrapper that latches the incoming speed (0x5B60 / 0x5B61), runs his hook at 28 MHz and restores it.
- Keys: ENTER starts at the title, Z / X walk, SPACE jumps.
- Results (2026-11-05): plain 0515a0ae, sprites b3321d93, boot OK; walk1-3 (12,035 / 12,000 / 12,011 frames) +
  water4 (1,103 frames, walk-in-water POKE, the sea bed) IDENTICAL: 6,927 plots pixel-perfect, 189 bubble tests,
  111 wipes, every hook; 3 negatives detected; clock matrix 5 sites x 4 clocks PASS, forced 3.5 MHz exit detected;
  ROM paths pass; tail never read before written. JNext: pace ORIGINAL (probe 0x61A8, 10 trials a scene: +0.00 %
  everywhere; 1 busy trial lost one interrupt in the game's own DI windows), flicker clean, soak 15 min clean.
  Cheats: Immunity kept; Walk in water (resets the game), Walk through walls (no effect seen), Cheat mode, Immunity
  (alt) (text here) dropped. Loading screen: the tape's (bank 13 stub).
- Enhanced: EASY. Treasure Island Dizzy.256 (Spec256-256-all38) matches all 2,262 bytes of Dizzy's 39 frames; 9
  palette indices on his ink (orange rim, pink face, yellow gloves, blue boots); a 4-bit set fits. Only Dizzy is a
  sprite: the scenery stays 2-colour. Mock-up: pilot runs/dean_treasure_island_dizzy/out/tid_enhanced_mockup.png.
- Seen: Dizzy shows light grey (Dean's palette entry), the original's cell bright white.
- Hardware: none.

## Lessons
- [local: printer ownership] ROM startup writes 0x5B89; do not expand a previously proved 0x5B00-0x5B61
  allocation to the full printer buffer. Keep the larger trampoline in the hidden ROM and prove access.
- [local: interrupt entry] A sound call inside an ISR can also be reached by ordinary code. Preserve
  its incoming IFF and protect shared hook state before the first write; compare both IFF states.
- [local: cheat semantics] Distinguish drowning, hazard death and reset by their calling PCs. The
  room selector intentionally hides the player until SPACE exits; that is not a broken sprite.
- [local: simulator checkpoint] CSimulator caches mapped bank pointers. After restoring a checkpoint
  outside execution, recreate it from the full snapshot; Memory.out7ffd alone leaves stale native mapping.
- [local: colour intake] The 39 player frames match the colour source, including 4,602 header/mask/ink
  bytes, while executable/state bytes elsewhere differ. Import colour data only; retain the 128K source.
- [local: external colour viewer] The experimental viewer loads Z80 as 48K and tracks colour shadows by address,
  not 128K bank. A validated 128K SNA reaches play but still loses colour detail across AY paging;
  reject it for approval images and render from the original game's recorded drawing calls instead.
- [deferred Open: reconsider when another dedicated TID-family 128K rework needs it: fold verify.py's 128K paths
  into the shared verifier] nexclash/verify.py is 48K-only (list memory, list(mm) snapshots); tid128 carries a copy.
- [local: a hook-speed latch belongs in RAM: SkoolKit's simulator drops writes below 0x4000, the latch in the
  slot-0 hook page read back 0 (the clock matrix caught it)]

- [local: colour proposal geometry] compare a monochrome reconstruction of the same
  drawing events with the original bitmap before trusting a colour mock-up. Include text scrolling
  and bubbles; adding original XOR results to a player-free shadow retained old player pixels.
  Probe: private work/room_preview.py; all three final captures reconstruct exactly.

## Technique use
- patch.restore-speed: used (the wrapper latch / restore, as hlib_speed, around Dean's hooks)
- verify.update-locked-pace: used (corrected probe 0xF072, the actual player update)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path and tail checks; the boot check follows loderunner_v2's
- retries: [local: the TID verifier on 128K memory (classify needs a list), the negatives' dict, the latch place]
- environment: [local: current runs use private JNEXT_CONFIG_DIR and TMPDIR, never override HOME; read-only or disposable cards]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator; pace trials from Cobra's script]
- scratch: [none: scripts stay in the pilot run folder runs/dean_treasure_island_dizzy/work]


## Enhanced design preview (128K, 2026-11-08)
Observed in original 128K RZX execution: object selector 0x7765, graphics offset table 0x7CF4,
graphics base 0x7EF4; object renderer 0x7A9A clips and mirrors, with writes at 0x7BF7, 0x7C5C,
0x7C72, 0x7C93 and 0x7CAF. Mode byte 0x7741 selects replacement, XOR or OR. The mirrored path uses
a bit-reverse table at 0x6000; shifts are by four pixels. Colour data must follow the source bit,
mirror and half-byte destination, not just the destination cell attribute. Observed source bytes
all match the archive release, including scenery, objects and player frames; executable bytes are not imported.

HUD text scroll at 0x75CB copies existing screen bytes; the colour representation must copy the same
pixels. Bubble writes 0xF5DA/0xF5FA XOR into the same representation. They must not copy original
screen bytes containing Dizzy into a player-free background. The player's mask is opaque even for
original black ink: some source-coloured eye pixels lie there. Paint all mask-opaque pixels.

The private three-room proposal uses walk3 frames 1203/6501 and water4 frame 803, captured just after
complete player plots. Its original-colour geometry reconstruction matches the original bitmap in
all three captures (zero differing pixels); both replays stayed in sync. This is evidence for the
preview mapping only, not a runtime build, whole-game coverage or hardware claim. Existing recordings
mostly revisit the first two beach/forest rooms and the seabed; later rooms still need coverage.

Design direction subsequently approved: retain the default player hardware sprites; colour scenery/HUD
through a separate colour surface while preserving the original game memory and bubble reads. Player
colours can be built into patterns. Whole-object calls should be considered before per-byte hooks to
avoid multiplying low-speed entry costs. Evaluate total bank usage and interrupt/pace cost before
choosing double buffering or transfer method.

DDMA review at design: graphics expansion, masks and XOR cannot be replaced by a byte transfer. The
existing player patterns upload once at startup. No measured runtime transfer bottleneck yet, so no
new DDMA requirement is justified at intake. Revisit after the measured hook budget; any accelerated
transfer needs a capability gate, supported fallback and independent effects proof.


## Inherited R audit (2026-11-08)
Private work/baseline_r_audit.py builds the unchanged main engine in memory and adds register 15 (R)
to its existing comparison for the first 250 water4 frames. All 34 checked events fail R: 2 wipes,
7 plots, 20 ISR hides, 5 erases. Logged examples differ only in R; all seven sprite pixel checks pass.
This confirms a modernisation requirement, not a completed fix. Bubble was not reached in this short
audit. New verification must include R on all five old event kinds and any added colour paths.

Archive cheat code audit: 25081 is the underwater check's conditional jump, 25184 gates the built-in
cheat handler, 62242 returns from a wall attribute test. These are meaningful code locations, but that
alone does not prove safe/useful behaviour. Re-test the prior rejected cheats with explicit conditions.
The alternate immunity address 29738 is inside the screen-row pointer table at 29729; it is not a
second valid immunity hook for this release. The historical note called it text; the disassembly
identifies the actual table. Do not package that raw write.


## Default modernization candidate (2026-11-08)
The opt-in tid128_v11 engine reuses Dean's patterns, plot and virtual bubble read. Larger entries live
at hidden-ROM 0x2200-0x22BD, with state at 0x5B00-0x5B3F. Hook code uses bank 10 page 21 at 0x0300;
39 frame budgets for both pixel alignments are measured from the supplied original code and placed
at 0x1000. No game bytes are embedded in source or the profile. Highest added bank remains 12.

The original player plot runs at 28 MHz with its original stack and a temporary return address;
hlib_pace repays its measured original time, and the incoming speed is restored. Erase, sound and
room continuations run at their incoming speed. Every shared-state write follows hlib_iff's DI;
the fixed-R form keeps entry instruction counts equal even when the first interrupt-state read is
interrupted. hlib_r preserves the refresh result at every hook. The sound-call site restores both
IFF states because it is also called from normal game execution. Original plot/erase exits remain DI.

Development evidence: complete water4 plus 2,000 walk3 frames give 522 pixel-exact plots, 517 erases,
2,082 sound-call checks, 21 wipes and 189 bubble reads, with registers including R, game memory and
screen equal. Boot, whole-ROM path and tail checks pass using enNextZX.rom (file MD5 prefix e50ee485).
Unit checks: 160 clock/IFF/R cases, ten interrupted-IFF-read cases, 234 frame/position cases. Seven
faults caught: swapped nibbles, rotated frame table, missing ISR/wipe hide, wrong R, fixed 3.5 MHz exit,
and lost bubble IFF. Absolute opaque pixel positions, colours and transparent edges are checked.

Historical preliminary JNext measurements used 61A8, which counts idle iterations.
Those results are superseded by the actual-player F072 pace/audio checks below;
they must not be quoted as release player-pace evidence.

Cheat recheck on original 128K execution: immunity survives 2,076 death-entry calls in the test route;
water disables 186 underwater death checks, but still allows the separate hazard death at 0xED6D.
C enables the built-in room selector (Z/X left/right, K/M rows, SPACE exit); it hides the player while
selecting, then redraws normally. A captured solid wall restores x=33 to x=32 without the wall poke;
with that poke alone it retains x=33. Bank 0 must be explicit for address 62242. The alternate immunity
at 29738 corrupts a screen-row pointer: omit that duplicate/incorrect entry. These are code/behaviour
checks; the final NXC-option and real-loader tests also passed, as recorded below.

New private room-route recording: 1,386 frames with original built-in selector and immunity declared,
15 observed room IDs (76-84, 111-115, 147). Its synced replay passes: 240 plots, 238 erases,
945 sound calls, 21 wipes and 91 bubble reads; ROM paths and startup tail pass. This is renderer coverage, not natural completion. Avoid
empty room selections: the original can fall into invalid room IDs. A discarded longer diagnostic
route still passed differential checks, but is not claimed as normal-game coverage.

## Stage log
- 2026-11-08: default modernization development pass, about 25 minutes of logged development checks; one pending colour-approval
  round. Read the changed engine and verifier in full to preserve the legacy contract. Shared library
  interfaces and native checking tools reused; no other game outputs changed or shared cards written.

### Enhanced implementation update

Jon approved the original/Enhanced three-room proposal (“yes go ahead”). Continue the
approved colour implementation; do not request the same approval again. Base refreshed to
main ce4b083; incoming changes affect Midnight Resistance only. New colour hooks and
source importer are additive to tid128_v11; default output must stay identical. Full-row
scenery work avoids a clock latch per byte; half-byte, box undo, text scroll and bubbles
retain their separate drawing semantics. Runtime tests, pace/audio and loader proof remain.

## Approved Enhanced implementation and final development checks

Original 128K source db6ccbeb2f9c601476efab3cfd28b131; only artwork is taken from the
colour conversion. All imported static graphics, bubble images and 39 player frames
match the target's original bytes. Jao Paulo is credited. Default neither reads the
colour source nor installs colour hooks. Its raw output remains 774fd38022c24acc140e7b1d067230d4.
Enhanced raw output is 8d556b9e76c00f580d71a42eb5dd82e1. Original loading screen is
91b2df45ff454c507e7563f66fa6a29b; bank 44 holds the source-only loading stub. Both fit 1MB.

Player patterns use 103 four-bit patterns and 15 opaque colours. Layer 2 banks 16-18
hold the scenery/HUD; colour source pages occupy banks 20-43, code bank 14. Eight
colour sites cover full rows, clipped half-bytes, room/text clears, scrolling, box
save/undo and underwater bubbles. Scenery pixels follow original replacement/XOR/OR,
source address and mirror direction. Clear/copy operations preserve the ULA writes.
The original game reads its original RAM and virtual player pixels, not colour pixels.

Rows and bubbles access expanded source colours directly, four/eight pixels at a time;
no per-pixel speed latch or upload. Whole room and bubble-list scopes run drawing at
28 MHz and restore the caller's clock. AY calls run at their original clock even during
room drawing. A real interrupt-mode latch follows both original IM1/IM2 sites: I can
remain FE after IM1, so I alone is not a mode test. Long drawing hooks forward IRQs
through the original handler, restore nested colour state and account for its R result.
Short entry/exit sections defer a pending IRQ explicitly. Full hidden ROM is retained.

Development proof: water4 (1103 frames) and room_route (1386) pass independent colour
canvas/register/R/memory comparison, including full room and bubble-list wrappers.
582 colour routine cases, 28 injected IRQ cases and nine deliberately broken colour
builds pass/catch; default adds 404 routine cases and seven broken builds. Bubble cases
cover all four frames, both horizontal alignments, and top/bottom/page boundaries.
UI text clear and undo not observed in those recordings are explicit unit cases.
No natural completion is claimed; the original room selector supplied later-room coverage.

Native pace measures the actual player update at F072, not main-loop address 61A8.
Three seeds in each of rooms 76, 111 and 147, 300 updates per trial, preserve all sampled
player state. Enhanced overall is 1.25-2.78 percent faster; quiet thirds -0.25 to +0.10
percent, busy thirds 3.56-6.84 percent faster; worst 20-update window +1.78 percent.
Default overall +0.00 to +1.96 percent. These are measured scenes, not an all-game bound.
The generic meter's hardware-IRQ gap warning excludes software-forwarded IRQs. Actual
EF9B handler timestamps and ordered AY writes are recorded separately: all AY writes
use original speed, with over 13,000 consecutive matching register/value writes per
trial after the initial phase offset. Small phase-dependent missed frames remain in
some quiet trials; they are within the measured pace tolerance, not zero-cost claims.

DDMA review: direct byte expansion, masks and XOR dominate; a transfer engine cannot
perform their semantics. Player patterns upload only once. Unrolled direct source
reads removed the measured underwater slowdown without a core-dependent DMA path.

## Additional lessons
- [local: pace probe] F072 is the player update; 61A8 counts idle main-loop iterations.
  Require state equality at every player update and several seeded quiet/busy trials.
- [local: IRQ accounting] A forwarded RST interrupt does not increment JNext's hardware
  acknowledgement count. Measure original handler entries and ordered sound writes as well.
- [local: mode latch] I=FE does not imply IM2. Hook the actual original IM instructions,
  restore the found mode, and inject interrupts in both modes in routine tests.
- [local: colour transfer] Underwater bubbles were dominated by staging eight pixels.
  Direct XOR reads with nibble rotation remove the staging cost and preserve pixel identity.
- [local: loading] Reserve a free bank after the Enhanced banks; bank 44 is within 1MB.
  Loader restores bank 5's displaced screen bytes before original startup, using source-only stub data.

### Stage 3 boundary
2026-11-08: main refreshed to 364cb7f (Dizzy loading-screen helper, Ikari timing and docs).
Dizzy's source-only loading-stub pattern reused with separate bank 44 and a TID profile.
Only TID engine/record files change; no shared runtime change. Full modules were read
because the new IRQ/colour verifier spans their state ownership and legacy fallback.


### Default underwater correction and revised freeze
The first default aggregate concealed a quiet-third +3.00% and two short windows of
+12.50/+15.01% in room-111 trials. The original-colour mode now also accelerates the
original F4F7 bubble-list drawing, restoring its caller's clock before sound. Its
separate R/speed latch is at 5B30-5B35; the hidden-ROM wrapper is 22BE-2339. Enhanced
keeps its own already-verified equivalent wrapper; the new default entry is not installed
in Enhanced. The raw default build is now fef2738464db14f21b8a87ecc7eb0708, Enhanced
3855907e242ff29e5d659958915dcf7d. Legacy published builds remain unchanged.

New default native results: all nine 300-update state sequences agree; overall -0.08
through +0.30%, quiet thirds -0.05 through +0.00%, worst 20-update window +1.98%.
The complete water recording passes all six hook kinds: 191 whole-list comparisons
plus 189 individual virtual reads. 436 routine cases and nine broken builds pass/catch.
The whole-list wrapper is compared with the already-proved default bubble reads on
both sides, while every inner read is also compared with the unpatched recording.
This preserves a meaningful all-register/R comparison without mixing the original
player-containing bitmap with the player-free virtual-read model midway through a list.
The ISR-only list entry does not read IFF, so its matrix preserves both IFF inputs but
has no fictional interrupted-LD-A-I injection. The other five entries retain that test.

Native display checks: room-76 300 frames have no flags. Room-111 has three generic
ULA/sprite alignment flags and no vanished figure or transient. All nine saved neighbour
states have exact player pattern/position pixels and no visible ULA pixel under the
player box: Layer 2 is opaque there. The generic ULA alignment heuristic is inapplicable
at those locations. The snapshots use physical SRAM offset 40000 for Spectrum bank 0;
use the mapped address, not offset zero, when checking game RAM or Layer 2.
Both final candidate modes completed 15 emulated minutes with no freeze/loop/crash;
the corrected default was rerun. Native beeper comparison has 313 exact
pulse widths across nine trials, every write at original speed. Real-loader rebuilding
was rerun on the final package bytes and was byte-exact in all three option modes.

Final record freeze: replaced the temporary pending-proof label with a stable description
of the verification method before stamping. No build, recipe command, runtime byte or
expected output changed; the interrupted pre-stamp run is not a completed proof.

### Legacy report correction
Both v1.1 modes passed all five recordings, units, negatives and ROM paths at 2b60d85.
The overall gate rejected `MISMATCH` inside legacy successful DETECTED lines. Those keys
now say `difference`; detection and counts are unchanged. A report check accepts that
wording and still rejects real failures. The complete gate then passed; no shared tool was changed.

- [local: reporting] Keep DETECTED and counts in negative-control reports; diagnostic keys
  must not collide with the parser's failure tokens. Real build differences must still fail.

### Into main, 2026-11-08
The .nxc needs one bank layout for both colour sets, so the published default is the
loading build plus Enhanced's banks (14, 16-18, 20-43), zero filled: published_default.
Hooks, game and engine bytes are unchanged: raw fef27384, loading aa2789e7 as before,
published 277cfbff, the bytes the real loader rebuilt. Stamped again on current main.

### Release closure, 2026-11-08
The frozen gate passed in 2,939 seconds: all recorded rebuild hashes, legacy checks,
both v1.1 full five-recording proofs, routine matrices, negatives and full-ROM paths.
The evidence record is stamped verified. No runtime or recipe changes followed it.
Final NXC MD5 ec813d26f46ffc0e56b92e405d2e2169 (77,122 bytes); real-loader tests rebuilt
all three selected outputs exactly and reached play. All options default off.
Both final modes remain within the measured 2% steady-pace bounds; Enhanced busy
thirds are 3.36–6.85% faster. The coverage and remaining display-warning limits above
still apply. Physical hardware and natural completion remain untested.
