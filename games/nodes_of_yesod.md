# Nodes of Yesod v1.5 — final owner artwork pass

Owner release status (2026-11-05): **shipped, same as Pyjamarama**, as reported by the owner. The intermittent death-only sprite breakup remains an unresolved follow-up; it does not hold this release. Existing packages and artwork are unchanged.

Imported all 456 edited pixels across 12 mole/enemy-spaceman graphics from the owner's latest sheet. Every edit uses an exact palette colour and stays inside the existing silhouette. The red enemy visors, white suit/boot cleanup, yellow equipment and revised mole details are included exactly as painted. The separate HUD portrait is unchanged. Patch and colours: Jon Attree. NexClash: Dean Woodyatt. The local build and loader evidence below remains unchanged; hardware is unverified.

## Art and builds in this repo (2026-11-06)
- The Backdrops option's sky and cavern planes and the Enhanced HUD portrait are original art by Jon Attree / NextTang:
  assets/nodes_of_yesod/ (indexed planes, RGB333 palettes, the PNGs they were encoded from, the HUD tile map).
- `auto` builds all four .nxc variants: sprites (default), enhanced (the painted map + palette + HUD), backdrops and
  enhanced_backdrops. Each is byte for byte the published .nxc 1.5 --bare apart from the NEX loading-screen block
  (header flag bit 1 + the tape's 6,912-byte picture) that the packager adds.
- recolour() now also sets the HUD flag (on with a map), so the selftest recolour guard holds for the Enhanced build.
- The Enhanced map keeps only the painting: its check values are null (the image bytes come from the player's
  snapshot); a repainted sheet's import writes them back, so null them before committing.

## Death-animation follow-up (2026-11-05)

Owner reports intermittent player breakup into scattered/scrambled sprite pieces during death, worse than the comparison captures, clearing on respawn. **Unresolved; no fix or new release claimed.** The v1.5 NEX/NXC and owner artwork remain unchanged.

Captured eight native deaths: two ordinary seeded runs and six reached deaths from nine room-start test fixtures. Inspected 1,898 native frame snapshots, including 1,226 with the death flag set. Pattern/grid checks found no persistent corruption after a hook completed. A few snapshots catch an upload or tile-position change in progress; these are intermediate states, not proof of the owner's visible fault. The two ordinary runs also pass the read-only flicker checker. Sampled death strips show the collapse animation, not the severe breakup reported. Headless results do not establish what the owner saw in the GUI.

The unchanged original was run from a real RZX death checkpoint. `out/NODES_DEATH_ORIGINAL_COMPARISON.png` compares matching player graphic IDs in different scenes; it is an illustrative pose comparison, not a synchronized whole-scene differential proof. The owner explicitly said the fault is worse than this picture.

Evidence: `jn/death-frames01/`, `jn/death-frames02/`, `jn/death-rooms03/`, `work/death01/`, `work/death02/`. Reproduction/audit scripts: `work/death_scan.py`, `death_pattern_audit.py`, `death_rooms.py`, `death_rooms_audit.py`. `work/death_capture.py` starts the unchanged v1.5 review build with native input recording and automatic PNG/JNS captures for its first six deaths and 64 recovery frames. Alt+8 marks an observed fault. Close JNext normally to flush `owner-input.jds`; the latest session path is in `jn/latest-owner-review.json`. Next action: inspect an owner-marked occurrence, reproduce it, then change only the confirmed cause and rerun the applicable proof.

## Files

- `out/nodes_of_yesod_v1.5.nxc`: 51,497 bytes, SHA256 `52efb19bda8dd25cca48226dd01293ce08cd2c7dfc1c986cb58efeb329d6f523`.
- `out/nodes_of_yesod_v1.5-enhanced-backdrops.nex`: review build, MD5 `3bd11552098628d7f7c9fe7902b854ff`.
- Default `f3f35d4c6e810004022b2c22b55ce56d`; Enhanced `84e1f3c5cb73cc27f8bcefc08b66ae90`; Backdrops only `fbc02effd60ac153995e10f79ec6dc2d`. Corresponding NEX files and `nodes_of_yesod_v1.5-menu.nex` are under `out/`.
- `out/NODES_OWNER03_CHANGED_FRAMES.png`: enlarged previous/current view of all 12 changed frames. `out/NODES_OWNER03_ART_REVIEW.png`: full-sheet comparison.
- `out/nodes_editable_owner03/` and ZIP: current native-size painting sheets, originals and layout files. The user's edited `out/nodes_editable_owner02/NODES_PAINTING_SPRITES.png` remains untouched, SHA256 `9e85753e721236196b238e92fe1cb050de6aff4ce48d999ff2ee9ec6c4dc103b`.
- v1.4 and earlier packages remain intact. `HANDOFF-V1.4.md` records the unchanged engine, HUD and backdrop implementation and its full proof.

Enhanced and Backdrops remain independent and OFF by default. The menu has seven archive trainers OFF and clash fix ON; keys 8/9/0 control clash fix, Enhanced and Backdrops. ENTER plays. In game: 1 keyboard, Z/X move, Q jump, A mole.

## What changed and current checks

Only Enhanced sprite pattern banks changed. Recolouring v1.4 produces the rebuilt v1.5 byte for byte; restoring the previous map reproduces v1.4 exactly. Headers, executable bytes, palettes, graphic tables, HUD, loading screen and both backdrops are unchanged. Default and Backdrops-only NEX files are byte-identical to v1.4. Every sprite transparency mask is unchanged.

All **33,679 opaque sheet pixels** were independently compared with the actual NEX pattern banks. The freshly exported sheet matches the edited source pixels exactly and imports back with zero changes. No edits were rejected or approximated in this round: 455 original-ink pixels and one interior-fill pixel changed.

Current differential replay: **w1.rzx and r22.rzx, 6,194 frames**, no failure counters. These cover seven of the twelve changed graphic IDs. The remaining five poses (D3AF, D3F5, D43B, D45E, D481) were absent from the available recording coverage and are checked by the current all-graphic unit matrix: **136 graphics, 2,992 positions, seven interrupted uploads, the unknown-graphic case and all 16 object indices**. This explicitly separates recorded coverage from injected cases.

Current JNext quiet regression against v1.4: **301 player-update records match exactly**, including state, master cycles, hook time and IRQ counters. All **2,037 AY writes match including their cycles**. There is no measured timing or music change in this regression. The three-trial comparison to the unchanged original remains v1.4 baseline evidence; no new whole-game speed claim is made.

All four host and **actual dot-loader combinations rebuild byte for byte** with the original 6,912-byte loading screen. Seven imported trainers pass 28 combination checks. Native loader runs use private card-image copies, not a physical card. Current loader SHA256: `d7ea19ec1fd65a6a73b16fd896014a922794489a95b515f1eb24074196c8db61`; older loaders can omit the tenth menu option.

## Unchanged engine evidence and limits

The v1.4 engine proof is inherited, not claimed as newly rerun: 48 valid RZX files / 243,719 frames, 59 paired surface/cavern fixtures, exact HUD/bank-7 checks, 240 speed/R cases, 60 IRQ injections and 28 negative-control types. No executable, palette, HUD or backdrop change was made in this colour round.

Source snapshot MD5: `4dd5e967592f0eabd20f113cb64f740e`. Known original left-edge clipping and room-79 collision-loop limitations remain. The original first-eight-pixel clipping comparison exception remains explicit; malformed injected t1 stays excluded. Ending and hardware are untested. No fresh long soak is claimed; see v1.2/v1.4 handoffs for the earlier soak warning and its limits.

## Reproduction and scope

Stage the untouched owner02 kit in `work/owner-import03/input/`; `work/painting_sheets.py import` stages the exact map. The previous map and palette are in `work/owner-import03/before/`. Import the staged map intentionally to the live work/profile files, then use `owner03_build.py`, `owner03_sheet.py`, `owner03_verify.py`, `owner03_binary_art.py` and `native_owner03.py`. `owner03_package.py`, `owner03_real_loader.py`, `owner03_finalize.py` and `owner03_owner_launch.py` complete packaging and review. All scripts are in `work/`; evidence is in `work/owner-import03/` and `jn/owner-import03/`, `jn/owner03-real-loader/`. The pilot venv and `PYTHONDONTWRITEBYTECODE=1` are required. Use a fresh output directory for a future import; existing paintings are protected from overwrite.

All writes stay in this Nodes run and its private clone. Other games, shared engines/format, real cards and the main NextTang repository are untouched. No network, push or publication. Baseline clone `8403e891fcd9e96fc6814c511dae46bc11ad4575`, refactor `bd1528cf`; changes remain local and uncommitted.

Techniques: detect.gameplay-screen-readers

## Lessons

- [local: frame-edge snapshots can catch a correct hook halfway through an upload] Diagnose persistence and inspect rendered frames before calling a temporary pattern/grid mismatch visible corruption; death-specific owner reproduction remains open.

- [local: a colour-only revision can inherit engine proof when its binary scope is demonstrated] Forward/reverse recolouring and unchanged non-pattern banks establish the boundary; current sheet, all-graphic and targeted replay checks validate the new pixels.
- [local: some edited animation poses are absent from available recordings] Report the five unit-only poses explicitly instead of presenting all twelve as recorded coverage.

- [local: an Enhanced set that also switches a HUD needs recolour to switch it too] the guard found the one byte (hud_enabled) recolour left as built.

## Friction

- reuse: [local: existing exact-palette importer accepted this complete pass] No importer or engine change was needed.
- retries: [local: complete changed-pose coverage was unavailable in recordings] Selected the shortest recordings covering every available changed pose and retained all-graphic injected checks for the rest.
- environment: [local: native JNext quiet comparison is deterministic for this pair] Player and AY event cycles match exactly.
- hand-rolled: [local: direct NEX/sheet checks guard the import boundary] Reused the independent pixel-address checker and transparency-mask comparison.
- scratch: [local: reproduction scripts belong with this owner revision] Kept owner03 scripts, staged source and evidence inside the owned run.

## Technique use

- verify.frame-layer-capture: helped: captured the native frames between completed hook checks.
- patch.display-atomic-switch: helped: isolated in-progress uploads and position changes from persistent corruption; no engine change was justified by the captured cases.
- detect.drawing-parameters: helped: checked runtime death-piece width and height against their graphic headers.

- detect.gameplay-screen-readers: helped preserve the existing screen/random-read contract by restricting this revision to sprite patterns; the code and palette remain byte-identical.

## Stage log and next review

2026-11-05: imported final owner sprite pass, checked exact pixels and binary scope, ran targeted proof/unit/native regression and four-way loader rebuild, packaged v1.5 and exported owner03 sheets. Owner now lists Nodes as shipped alongside Pyjamarama. Death-only breakup is a follow-up; no fix is claimed. Hardware remains unverified.
