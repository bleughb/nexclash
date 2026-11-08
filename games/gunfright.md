# Gunfright (Ultimate Play The Game, 1985, 48K)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.1 published as .nxc 1.1 (2026-11-08, nxc repo 018c8f2), owner approved:
default = 1.0 byte for byte (runtime v14, hook page SHA-256 93ecf6af before the start-up restore); Enhanced (off by
default) = the ordered Layer 2 renderer v18 (page a18bedb0, code end 0x3848, highest bank 47, fits a 1MB Next).
Files: `nexclash/gunfright.py`; default `asm/gunfright_hooks.asm` -> `docs/profiles/gunfright.json`; Enhanced
`asm/gunfright_enhanced.asm` (the default runtime with five producer hooks, h_in/h_out/h_clear calling the renderer,
a Layer 2 setup and palette) including `asm/gunfright_l2.asm` (the renderer) -> `docs/profiles/gunfright_enhanced.json`;
`docs/profiles/gunfright_colours.json` (the owner's painting as palette digits per source pixel: town, street-bandit
role, scenery, the opponents' shared map plus each opponent's own differences, six geometry exceptions; no game data).
The Layer 2 asset pages 44..61 are compiled at build time from that file and the original graphics in the user's
snapshot (post-loader state). Build: `python -m nexclash.gunfright SNAPSHOT OUT.nex [--enhanced]`; with the original
tape beside the snapshot the original loading screen is added (NEX header byte 10 = 2, start delay 50).
Registered (2026-11-08): `is_gunfright` in nexclash/engines.py (loader signature at 5B96, 48K only); `auto` builds
`gunfright.nex` (default) and `gunfright_enhanced.nex`, boot-checks both (all RAM, registers with R, complete hidden ROM,
converter loader and NEXLOAD) and, with --rzx, runs the default replay proof and unit tests;
docs/records/gunfright.json makes `selftest --game gunfright` rebuild both (MD5) and verify the default on town.rzx and
duel-trigger.rzx. Enhanced's oracle, negatives, readback and pace proofs are the pilot run's (Evidence), not yet in the
repository.
Both builds equal the published .nxc 1.1 reconstructions (`nxc.py PATCH GAME --bare [--colours Enhanced]`) byte for
byte: default SHA-256 e9d01680 (MD5 f26d0a56), Enhanced a89a4beb (MD5 4ec70c82); both carry the original loading screen.
Pending: hardware checklist; wanted-poster portrait (mock-up only, 1.1 keeps the original poster); a natural
street-bandit fixture; an in-repository Enhanced verify.

## Inputs
Main archive Z80 MD5 0cd9e86a2c6c7afa22025f8d593af093; exact files/hashes in ../work/inputs.json.
48K snapshot is stopped in the BASIC loader at ROM PC 0038, SP FF50, IFF0. Loader USR entry 5B96.
The archive loading screen is present. SPACE releases PAUSE. Menu 3 starts the game; a sustained press is needed during the long menu beeper routine.
Original-only 3,500-frame intake recording includes menu, money-bag shooting prelude, street play and deaths; no game code or RAM was patched.

## Decisions
Owner scope: complete original-look release plus optional Enhanced after mockup approval. Default must preserve the original look; Enhanced stays off by default. Every moving figure is in scope. No added white outlines or pixels outside original figure edges. Paint by the drawn parts, with editable native-pixel sheets.
Pace target: match original steady scenes within 2%; busy slowdown may improve, but tested scenes must never become slower. Quiet/busy/cold paths measured separately, no masking cold delay with later limiter repayment. Preserve R and incoming speed; original beeper remains at original speed.
1MB target, complete hidden ROM, archive trainer behaviour tests, exact NXC reconstruction and private-card actual loader required. No hardware result claimed.

## Engine investigation
Techniques: discovery cards applied below; runtime recipe evidence remains in development.

Gunfright is Filmation II: BE0D/BF51 use the same masked stack plot family as Nightshade E45E, with a separate mirrored branch. The buffer is D6E4-E163, 24 bytes by 112 rows; D044 copies 22 visible bytes per row and D0B0 clears it. Scenery OR plotters C4AB/C622 are distinct producers. No whole-buffer scrolling shift was observed in the 2,001-frame write census; this is not a claim about unreached paths.

Graphics table 67F4 has 56 entries, 51 nonempty. Rows are bottom-up mask/ink byte pairs; opacity is mask OR ink, because original ink is not always a subset of mask. Multipart lists at BD5E contain signed dx/dy/graphic triples. The money-bag prelude uses the same masked drawing system (figure ID29hex); AE0E/table6864 animate the menu gun flash and bullet. Duel table 6AC6 has 41 unmasked 32x8 strips; B5AE has twenty five-strip bodies, combined with two three-strip leg poses and three collapse sequences. The wanted-poster portrait reuses four of those body strips. Scenery uses 43 strips and 39 unique full building compositions. Runtime Enhanced prelude/menu/HUD coverage remains open.

Player updates are A3C6 with IX=A27B. The original drawing/copy window A3E2-A3F4 consumes 82.98-86.67% of the update interval in three original 120-update scenes. All 363 player entries were IFF0. R reads C0C9/C0CE include a caller-return-address contribution, so hook trampolines must preserve both R and the original return word. No beeper writes or ROM execution occurred inside those measured windows; whole-game coverage remains pending.

The default runtime v14 renders the exact 176 by 112 playfield onto 77 4bpp hardware grid sprites. Town x72/y8 uses original bright white; duel x40/y8 uses original bright cyan. Original masked draw order and ULA output remain intact. Three hooks bracket A3E2-A3F4 and clear D6D4. Shared speed/R/IFF/pace helpers preserve incoming state. The private stack removes game-stack residue. Native conversion uses exact mono-tile caching and uploads only changed patterns. Shared ordinary DMA uploads contiguous 128-byte patterns, with capability/IM2 gating and an unrolled CPU fallback. DDMA cannot improve this contiguous port transfer or mono expansion; no DDMA extensions are sent. The latest emitted page SHA256 is 93ecf6af72e3cdcf4508b58037b18d7714d3365a3b6016b874a25990e9c59ca4.

Full default replay induction: 8,000 town frames (1,190 entries/exits, 23,457,280 pixels) plus 3,500 duel-trigger frames (466, 9,185,792 pixels); every register incl. R, live RAM and hardware pixels match; 296 + 288 ABI cases, five broken builds caught; DMA gate/fallback 1,728 cases. See ../work/default-full-v14, ../work/default-duel-v14, ../work/dma-fallback-final.json.

Native beam audits: zero unsafe publications (maxima 39.15/48.56/62.68 scanlines quiet, busy, duel); original I/O is FE/FD only. See ../work/dma-evaluation/native-costs.json.

Original-clock beeper proof: 5,650 pulses (2,402 jingle) with register/R/FE sequences and clock 0 equal; ULA contention phase bounds edge-time differences (aggregate below 0.011%; a contention-off diagnostic gives exact edges). A 12,000-frame restart soak is a robustness run, not a pace proof. See ../jn/sound-v14-live-complete, ../jn/default-soak-v14-restarts.

Input qualification: JNext clears keys held before NEX load, so keys start at frame 501 after load 500; the 18-trial matrix then has exact CPU/native R and actor bytes for 200 updates, every window within 2% and none slower (worst 1.181% faster); 17 freezes match full 48K and RGB. See ../work/PACE-REPORT.md.

The archive snapshot precedes a 6000-to-5E00 relocation. A direct post-relocation package exceeded the NXC site table. LoaderPatch therefore keeps original source bytes, places hook/trainer bytes at their relocation-source addresses, executes the same 32768-byte LDIR during DI boot, then restores the exact original post-loader register/R state and 11 outside-copy RAM bytes. Old and bridged boots are full 48K/register/R identical at 5E00, both direct and NEXLOAD, with no RAM exclusions. Gameplay hooks are unchanged. Current generic sprite NEX MD5 c9055bf7512835a43c5f15a13a18e6aa; default-only development NXC is 19,226 bytes. See ../work/loader-bridge/result.json. Final release remains open.

Engine dispatch and auto build the published default and Enhanced NEXs with all-RAM/register/R/full-hidden-ROM boot checks (before and after the NEXLOAD printer-buffer clobber). The loading screen is the tape SP block after its 12-byte copier (MD5 de2ebbf6d54e4c8d2842ab8a5063de78), never the 80-byte-different snapshot screen.

Enhanced (v17 design, v18 constants) is an ordered Layer 2 renderer. Five producer hooks (BE0D/BF51 masked figures, C4AB scenery OR, C622 ground store, B28A duel strips with the mapped bounty identity) record one command each after the original has computed its buffer address, data pointer, rows, shift and mirror; the original mono drawing still runs unchanged, so game RAM, registers and R stay the original's. h_out replays the queue into the hidden buffer of a double-buffered 256x192 Layer 2 (banks 16..21) from pre-coloured assets (banks 22..30: masked town and street-bandit roles, plain scenery/ground, 53 unique duel strips and a 20x41 identity table); masked = replace on cover, OR producers = OR of indices, ground = replace. The buffers flip only while the beam is outside rows 8..119; a frame that cannot flip in time stays pending (no tear, no wait). Hook costs are taken off the pace target: L2_WCOST 87 and L2_LCOST 26 sixteenths of a line (v18 changed only these two operands from the v17 build the owner played). The money-bag prelude passes through the same producers, so it is painted in Enhanced; the wanted poster, score and HUD keep the ULA.

Auto emits the verified eight trainers as a translated source-address POK (exact source hash and every expected byte checked); explicit --pok accepts only the checked archive or that translation. Evidence: ../work/generic-trainers/result.json.

## Evidence (pilot run runs/gunfright: work/enhanced-l2-v18, work/release-1.1, out/release-1.1)
- Default (v14, unchanged since 1.0): replay induction 8,000 town + 3,500 duel-trigger frames (every register with R,
  live RAM, sprite pixels), 5 negatives, 584 ABI cases, 1,728 DMA gate/fallback cases; 18 native pace trials within
  2% (none slower); 17 full-48K/RGB freezes; 5,650 beeper pulses; 12,000-frame restart soak.
- Enhanced: a Python reference model equals the original mono buffer and an independent painting of the original
  renderer in 159 cases; the emitted code in the paged Model equals it in all 159 complete updates (identity 40,
  opponent 16, complete 60, collapse 24, coverage 19: 3,134,208 pixels) with registers incl. R, 48K outside the site
  bytes, MMU and clock equal to the original; CPU-only (no DMA) path 49/49; 7 of 7 negatives caught (bandit role
  ignored, mirror shift, ground as OR, identity 0, wrap dropped, OR as copy, mask transparency); native readback 9/9.
- Enhanced pace (JNext, probe A3C6, 3 R seeds): steady quiet -0.30..-0.09%, moving -0.19..-0.12%, busy -0.20..-0.04%,
  death -0.16..+0.01%; duels -1.00..+0.18%; street after a duel +0.03..+0.12%; cold first 20 updates up to -2.27%
  (faster). Duel-to-street transitions within -0.50..+0.77%; beeper bursts same order and values, durations within
  1.5%; 20,000-frame soaks per mode clean.
- Package: default rebuilt on main 2c6778a equals published 1.0; real loader (.NEXCLASH) on disposable NextZXOS v2.09
  and 26.11 card copies: default, Enhanced, Enhanced with all eight cheats, 6/6 byte-exact; menu .nex 3/3.
Known issues: Enhanced's cold windows run up to 2.3% faster; the prelude's money bags are painted in Enhanced.
Missing: hardware; natural completion; joysticks; a natural (non-synthetic) street-bandit fixture.

## Hardware checklist
Default and Enhanced on a real Next (1MB and 2MB): boot with the loading screen, menu key 3, town walk/fire, a duel
won and lost, game over and restart; Enhanced: no tearing at the playfield edges, painted figures and opponents,
pace against the original by eye; each cheat once.

## Lessons
- [local: Gunfright menu timing] Observed: six-frame menu key pulses miss the long beeper routine; a 350-frame press of 3 reaches the prelude. The recorded key schedule retains this fact.
- [local: separate gameplay modes] Observed: the money-bag prelude and duel use different screen geometry from town. The prelude still uses the main masked figure table; AE0E is the menu gun animation, confirmed with original before/after plot captures.
- [local: paired mask semantics] Observed: some source ink bits lie outside the mask. Preserve mask OR ink as support; mask-only extraction loses original pixels.
- [local: cache initialization] Observed: zero mono cache bytes do not prove hardware patterns are initialized. Initialize every used opaque-black pattern during setup before accepting an unchanged black tile.
- [local: native colour opacity] The Enhanced setup substitution silently missed because its leading whitespace differed, leaving NR4B0 and making intended black0 transparent. Actual native palette/attributes/pattern compositing exposes122 original ink pixels in the broken moving snapshot; corrected NR4B1 covers all19712 viewport pixels. Check actual setup and full-layer opacity, not just final pattern indices; retain the old build as the negative. Evidence: ../work/root-white-frame-audit/native-opaque-grid.json.
- [local: editable pixel coverage] All51 nonempty town graphics have colours, but joined poses conceal130 opaque pixels from nine parts. Source-byte coverage is insufficient: audit each source pixel and expose occluded parts separately. Supplementary editable art and immutable baseline are ../out/colour-review/GUNFRIGHT_PAINTING_EXTRA_PARTS.png and ../work/owner-extra-parts-baseline-5f7f24d24b0d; import overlapping sheets by their individual edit deltas.
- [local: shared actor artwork] Original CB22 shares sheriff1 and walking-bandit10 bodies/legs; B407 adds2/4/6 to the head, giving bandit16–21 versus player14/15. A source-byte colour map therefore puts an edited sheriff badge on bandits too.24 original-code composition cases prove the reuse; label head-only edits separately and use actor-specific colour identity for future independent clothing. Evidence: ../work/root-character-identity/report.json.
- [local: owner shape cleanup] Compare edited PNGs to their actual frozen baselines. In this pass, two black additions and four erased pixels form a deliberate hat-edge edit; nearest-palette import alone mistakenly turns sheet-background erasures grey. Record these six explicit exceptions and verify compiled masks/pixels independently, preserving live original game masks.131 distinct main/extra edits pass actual NEX source-plane readback in ../work/root-owner-pixel-readback/report.json.

- [local: pace elapsed accounting] Long conversion paths must tick the shared pace accumulator before a frame can wrap. Polling every uploaded tile is unnecessary and lengthened publication; move readings outside the bounded transfer.
- [local: renderer pace calibration] Paired native original window measurements fit a slope of 104.05 and a fixed 679/16-line term. The candidate uses 104 and a conservative 448/16-line term to leave hook and quantisation margin, validated separately on cold and sustained windows.
- [local: private hook stack] A private stack inside the mapped hook page removes dead game-stack residue; full 48K native comparison then needs no stack exclusions.
- [local: native snapshot capture] A screenshot requested at the instruction-boundary freeze may contain the preceding partial video frame. Waiting two complete frozen video frames removed the isolated HUD-fragment mismatch; live game RAM was already identical.
- [local: archive trainer arithmetic] Infinite Money's archive RET truncates BCD carry propagation and rejects affordable purchases. NOP only the three money stores D36A/D36F/D375; preserve arithmetic and affordability flags. Six BCD boundary fixtures pass.
- [local: negative table coverage] Corrupting only the FF pixel LUT entry escaped the first four recorded frames because none used it. Corrupting every first-pair LUT entry makes the intended negative deterministic while retaining the broken build's own table.

- [local: mode-qualified pace] A fixture beginning in a duel or busy-looking death is not a sustained live scene. Split windows by actor type/mode and keep cold/death paths separate; do not rename mixed averages as duel pace.
- [local: DMA fallback] The shared capability and hardware-IM2 gate selects ordinary DMA only where supported; CPU-only and older/unknown-core paths pass the same ABI and negative controls. Native whole-publication measurements, not simulator T counts, establish its benefit.
- [local: beeper contention] Even with original clock and instruction/R parity, ULA contention phase changes edge durations. Bound the actual I/O plus stack accesses and retain a contention-disabled diagnostic; never claim normal waveforms byte-identical.
- [local: archive ammo corruption] NOP C9FF lets the HUD bullet index exceed six and overwrite live code. Preserve original decrement/increment/compare and cooldown, skip the count store CA00..02 and darkening branch CA06; all six starting counts preserve code and HUD.
- [local: separate duel artwork] The large opponent uses unmasked strips and independent body/leg lists, not the town mask table. Catalogue all twenty opponents and collapse poses explicitly before claiming figure coverage.
- [local: original scenery scratch] Original scenery can leave pixel-dependent AF-prime scratch and write one guard byte E164 beyond the normal buffer. An Enhanced compositor must reproduce both; do not conceal them with a broad RAM/register mask.
- [local: archive relocation packaging] A post-LDIR build against a pre-LDIR snapshot exceeds NXC site-table capacity. Keep archive source bytes, relocate during DI boot and restore the independently derived post-loader state; verify every RAM byte and register/R before reusing gameplay evidence.
- [local: native input survival] JNext NEX loading clears earlier key presses. Schedule keys after load and confirm original CPU/native update states; otherwise moving/fire labels can describe neutral-input runs.
- [local: trainer relocation] Generic import-pok does not relocate live addresses through an original loader. Emit a checked source-address POK from the engine and verify both patched-NEX and fix-off original-snapshot paths; do not import the archive blindly.

- [local: actor-specific source identity] A shared source address cannot give the sheriff a badge without the bandits. The selector uses IX actor type 10/22 and independent body/leg IDs 22..35, keeping geometry and MMU; named keys split town:/bandit:. 135 shared-R cases, 41 scenes and 3 negatives pass. See ../out/independent-characters/README.md.
- [local: named owner sheets] Label source roles outside paintable bounds; immutable baselines plus delta import keep duplicate parts without last-write-wins conflicts. ../work/named-artwork-qualification/report.json.
- [local: pre-window duel drawing] B28A strips and BDA3 arm parts draw before A3E2; an oracle starting at A3E2 can agree with a wrongly white duel. Capture only those original drawing commands and replay them into the private planes. The v5 complete-update oracle starts at A3B8:60 updates, full48K/register/R checks, native transitions and broken replay/R/capacity controls pass. See ../../work/duel-coverage-v5/README.md. This fixes coverage, not the remaining Enhanced slowdown.
- [local: mounted paint boundaries] A connected white region can span the rider, hand and pantomime horse. Source53's whole componentA was too broad a shirt mask; the owner caught its false anatomy. V6 changes15 hand pixels to skin and8 lower costume pixels to brown in both role maps. Preserve the38 owner edits and horse54/55; review assembled mirrored figures and actual native frames. See ../../work/art-import-v6/mounted-correction.json.
- [local: opponent-specific owner paint] Opponents reuse strip addresses, so one source map lost 48 conflicting owner colours. Keep twenty maps (stored as a shared map plus each opponent's differences) and capture the mapped bounty identity with each strip; the five owner-added pixels are bounded separately. ../../work/duel-owner-import-3fcefafdde67/report.json.
- [local: collapse coverage] A no-input defeat-to-town sequence does not draw the opponent's collapse strips. A separate original-state fixture exercises all nine strips32..40 over24 exact updates. The initial instruction bound was too short for the original score/sound path; raising only that bound completes the paired proof. Retain distinct scope labels; it is not a natural victory playthrough.

- [local: shadow-plane route abandoned] Four colour shadows of the original renderer stayed slower than the original (v15 quiet +2.4%, duel +52%) even after stopping at A3F1, one shared private state and bounded restores; ordered Layer 2 replay replaced them. A Faster toggle (28 MHz ULA copy below the playfield, copper frame clock) was built and dropped by the owner.
- [local: Layer 2 semantics] v7 planes = replace-on-cover (masked), OR of indices (OR producers), replace (C648/C692/C694), half-nibble OR (C641/C64F). Optimised pixel-work probe: 5.8 ms quiet, 19.4 ms busy. ../../work/enhanced-l2-v16/README.md.
- [local: ordered Layer 2 replay] Record commands at the producers' entries (after the original computes address, data, rows, shift, mirror) and replay them in order into a hidden Layer 2 buffer; the original drawing keeps running, so RAM/R parity is free and only the replay costs time. v17 brought every scene from +2.4..+52% to within 2%.
- [local: hook cost constants] Producer hooks inside the measured render window lengthen it and are scaled by the limiter's slope; take each hook's cost back from the pace target (L2_WCOST/L2_LCOST) and refit the constants from native measurements, not simulator counts.
- [local: synthetic role fixtures] No recorded state drew a street bandit through a masked producer; labelled synthetic fixtures (the player's record copied into the bandit slot before actor drawing) let the bandit-role negative be caught. Keep them labelled; they are not natural coverage.
- [local: published-build parity upstream] The engine compiles Enhanced assets from the post-loader state of the user's snapshot and the palette-digit painting; both builds equal the published .nxc reconstructions byte for byte, so the pilot's proofs carry to main.

## Technique use
- detect.buffer-layout-producer: used: identify the town screen copier and actual graphics producer.
- detect.drawing-parameters: used: observe live record pointers, dimensions, clipping and coordinates.
- detect.graphics-record-layout: used: derive graphics headers from original consumer code before sheet extraction.
- verify.paint-follows-drawing: used: original support and part boundaries drive the proposal; final accepted look proof remains pending.

## Friction
- reuse: [none: engine analysis is underway; no reusable implementation yet]
- retries: [local: menu timing] Short key presses did not leave the menu; retained a sustained press in the recording.
- environment: [none: local baseline and pilot environment available]
- hand-rolled: [local: intake screenshots] A small original-only frame sampler uses shared Machine and preview helpers for the game's initial modes.
- scratch: [local: intake probe] ../work/intake_frames.py is a game-specific key schedule and screen contact sheet; retain in private evidence, not the toolkit.

## Stage log
- 2026-11-07 intake started against refreshed main 102091f2; original loader and three display modes observed. No release candidate yet.
- 2026-11-07 original-renderer colour direction sent for approval; editable sheets frozen. Default prototype and first rejected native pace trial recorded; cached conversion under test.

- 2026-11-07 default v14: shared ordinary DMA plus gated fallback, full town/duel proofs, fifteen native exact-image/RAM trials, bounded original-clock sound and restart soak. Separate duel/scenery proposals await owner review; no Enhanced or release package claim.
- 2026-11-07 Enhanced v5..v7 artwork imports (bandit clothing, duel arms, mounted hand fix) and v8..v15 shadow-plane speed work (not pace-qualified); Faster toggle reviewed and dropped.
- 2026-11-07 final owner DUELS import (1,528 occurrences, five additions, 48 per-opponent conflicts kept): v7 passes identity/sequence/complete/collapse oracles, native readback (157,696 pixels) and the independent NEX audit (bank 47). Separate v6-art speed proposal saves ~30% hook time but is too slow. See ../../WORK.md.
- 2026-11-08 1.1 published (default = 1.0, Enhanced v18 ordered Layer 2). Upstream: Enhanced asm/profile/painting, registration in engines.py, auto builds both published NEXs (byte-identical to the .nxc 1.1 reconstructions), record and views.
