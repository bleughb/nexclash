# Incredible Shrinking Fireman — add-GPT6_ASTRA

## Next session
Stage: 4 (hardware/colour)    State: stage3 software acceptance PASSED
Inputs: specnext/reference/incredible_shrinking_fireman-add-GPT6_ASTRA/ (snapshot, RZX, builds)
Branch: claude/incredible-shrinking-fireman-add-GPT6_ASTRA
Start with: test the supplied sprite NEX in CSpect/Next using the checklist below.
Read: PLAYBOOK stage4; this file's Implementation and Open sections.
Open: hardware behaviour, unseen paths and optional user painting.

Status: phase B acceptance PASSED and stamped. Hardware untested.
Branch in both repos: `claude/incredible-shrinking-fireman-add-GPT6_ASTRA`.
Reference: `specnext/reference/incredible_shrinking_fireman-add-GPT6_ASTRA/`.
Module: `nexclash/incredible_shrinking_fireman_add_GPT6_ASTRA.py`.

## Provenance and approved design
Capture adapts the existing add-OPUS phase-A module; runtime/verifier adapt fireman.py. This is
not an independent from-scratch benchmark. GPT6_ASTRA is the requested label, not model identity
certification. Existing Fireman output is unchanged: dispatch selects this engine only for
snapshot filenames ending `-add-GPT6_ASTRA.z80`.

User approved all moving figures and collectables as sprites, in front of scenery, original
colours, transparent gaps, hidden during option/inventory screens; identical coincident enemies
retain XOR cancellation. Scenery, HUD, text and inventory UI remain ULA. Diamonds start white.
Original attribute writes remain because gameplay reads them; background colour behaviour is
therefore retained. Original colours can have low contrast on light scenery; painting is optional.

## Inputs and survey
- Snapshot MD5 `fc8e7535fc42afb60c12625b5fdfd064`: 48K, PC0xC524, SP0x618A, IM2, I=0x39.
- RZX MD5 `8154d148d90b0f3cc94229bc143bac68`:32,492 frames, no desync, includes completion screen.
- Capture:9 fireman and172 enemy graphic/ink variants;198 reference figures including static
  additions,192 minimum painting figures. Static additions are not recorded-play coverage.
- Whole-figure1:1 PNGs without labels, separate diamond sheets, source-ink colour keys and
  paintable paper pixels. Unpainted sheet read-back produces zero edits.

## Implementation
- Three moving slots use two overlapping16x16 patterns each (16x24); five diamond slots.
- Original bitmap XOR stores removed, attribute painter retained. Virtual reads reconstruct
  diamond overwritten bytes before XORing moving images. Clears hide sprites for menus/rooms.
- Hooks0x386E..0x3CA9;20-byte register block follows, below0x3D00. IM2 vector39FF/3A00 remainsFFFF.
  StateF400..F41F and tail5E40..5F3F were untouched throughout the full memory scan; only preserved
  vector bytes were touched in the hook ROM range.
- Sprite update saves entry IFF, disables interrupts, uses28MHz, restores MMU6/page0 and3.5MHz,
  then restores entry IFF. The recording exercises19 entries with interrupts enabled.
- Fixed16-colour palette and frame/ink cache. Display banks16..39 cover all256 wrapped frame
  addresses and16 source inks. Diamond pattern6 occupies the first128 bytes of bank11.
- Recolour changes only display banks and diamond pixels; header and every non-colour bank are
  hash-checked. Empty-map identity, synthetic repaint, revert and invalid-header rejection tested.
- Normal and NEXLOAD boot restore the printer buffer. Plain tail5E40..5E8F; sprite tail stays
  within the scanned reservation. Original bytes are checked at every patch site.

## Final verification (2026-10-26 local date)
`selftest.py --game incredible_shrinking_fireman-add-GPT6_ASTRA --verify --stamp`: PASSED.
- Full32,492-frame differential IDENTICAL:29,891 ISR hooks,27,883 plots,674,333 virtual reads,
  79 diamond draws and164 clears. All19 IFF-enabled entries pass.
- Compared7,736,176 moving-figure pixels and384,200 diamond pixels;702,459 hook instructions
  checked for interrupt safety. Attributes and non-draw memory compared.
- F/AF-prime scrambled at27,883 plot ends: all RAM identical at every frame end.
- 2,705 unit cases plus setup and five negative controls PASS: all256 frame addresses at edges,
  multislot/diamond cases, virtual reads, synthetic paint, cancellation and both entry IFF states.
  Negatives catch wrong colours, missing virtual reads, IY corruption, omitted paint and missing DI.
- No recorded right-edge clipping or large-jump exceptions counted. Worst patched ISR53,301
  simulated T states, mostly at28MHz; this is not a wall-clock/raster measurement.
- Rebuild MD5s, pinned assembly/profile, recolour round-trip, boot checks PASS. Chuckie Egg
  stage1 canary PASS after registry change. Generated record views are current.
- Final report: `verification_report-add-GPT6_ASTRA.txt`; model preview:
  `verified_preview-add-GPT6_ASTRA.png` (original left, sprite model right, not hardware captures).

Build MD5s:
- `incredible_shrinking_fireman_plain-add-GPT6_ASTRA.nex`: `f8f213e55e3da01349827f8ae7d93bee`
- `incredible_shrinking_fireman_sprites-add-GPT6_ASTRA.nex`: `1ea61f0bcaf2b5f27514807f8753f263`

## Reproduce / recolour
From nexclash, set `PYTHONDONTWRITEBYTECODE=1` and
`NEXCLASH_REFERENCE=../specnext-add-GPT6_ASTRA/reference` for these suffixed checkouts.

```sh
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA build INPUT-add-GPT6_ASTRA.z80 -o PRIVATE_DIR
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA sheet INPUT.rzx --z80 INPUT.z80 -o PRIVATE_DIR/incredible_shrinking_fireman-add-GPT6_ASTRA
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA recolour BUILD_sprites-add-GPT6_ASTRA.nex PAINTED.png --layout SHEET_layout-add-GPT6_ASTRA.json -o BUILD_painted-add-GPT6_ASTRA.nex
```
New filenames carry the suffix immediately before their extension; Python uses underscores.

## Open / hardware checklist
CSpect boot first, then Next: title/start, room transitions, collect/pickup/drop, inventory/options,
death/game-over/restart, figure overlaps, right-edge clipping, speed/flicker and beeper pitch.
Sprites clip at256px where the original plot can wrap; synthetic units cover edges, but unseen
rooms need additional recordings. Real interrupt scheduling/raster/DivMMC are not simulated.
No emulator or hardware result is claimed. Pre-merge affected-game checking remains the maintainer
workflow; no release or merge is part of this run.

## Lesson candidates
- Removed bitmap differences must be tracked at each actual store, including diamond overwrites;
  speculative plot-entry/end updates hid errors. Collectable virtual reads have350 unit cases.
- Full replay exposed19 IFF-enabled sprite updates: entry state is now explicitly saved/restored.
- Per-event overlay classes caused simpool's type cache to retain closures until an8GiB OOM kill.
  Stable overlay types fixed the leak; final replay stayed around360MB for the environment.
  Kept local under the current documentation workflow. Earlier interrupted/failed runs received no stamp.
- Tool-managed sessions were required on this host; a session reset lost an earlier partial run.
  Final acceptance retained stderr and completed. No new hardware/platform claim was inferred.

## Stage log
- 2026-10-26: stage3 continuation, roughly1hour/150tool calls,0new user rounds; recovered interrupted
  acceptance, fixed verifier memory growth and rare enabled-IFF entry, full acceptance PASS,
  published draft PRs and reconciled concurrent main changes. Earlier stage1/2 approved by continue.
