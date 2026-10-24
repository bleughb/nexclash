# Incredible Shrinking Fireman — add-GPT6_ASTRA

Status: phase A prepared; awaiting visual-design confirmation. No sprite conversion, engine
registration, verification stamp or hardware claim for this run.
Branch in both repos: `claude/incredible-shrinking-fireman-add-GPT6_ASTRA`.
Reference directory: `specnext-add-GPT6_ASTRA/reference/incredible_shrinking_fireman-add-GPT6_ASTRA/`.
Module: `nexclash/incredible_shrinking_fireman_add_GPT6_ASTRA.py`.

## Provenance and scope
The capture module is adapted from the existing add-OPUS phase-A module, not an independent
from-scratch benchmark. Existing `games/incredible_shrinking_fireman.md` and the OPUS notes were
read as required by CLAUDE.md. Their research is prior evidence, not newly measured in this run.
The GPT6_ASTRA suffix is the requested run label; it does not certify model identity.
No files belonging to another Fireman implementation were modified.

## Inputs and new checks (2026-10-25)
- Snapshot: 48K, PC 0xC524, SP 0x618A, IM2, I=0x39, interrupts enabled. BASIC loader remains in RAM;
  execution is in game code. `inspect` misreports the IM2 ROM vector because it uses blank ROM;
  the existing notes explain the real vector and trampoline. Do not relocate them blindly.
- RZX: full 32,492-frame replay through `rzx.trace`, no desynchronisation.
- Moving figure capture: 9 fireman variants and 172 enemy graphic/ink variants. 198 reference
  figures including static bank additions; minimum whole-figure painting sheet has 192.
  Static additions are NOT evidence that the recording exercised those figures.
- Colour keys include source ink, so painting an enemy in one colour does not overwrite every
  room-colour variant. Whole figures are retained, at 1:1 resolution, no sheet text.
- Separate collectable sheet: room-table items call 0xECFF, using the same seven-byte diamond at
  0xED14. DEC B draws rows bottom to top; the sheet reverses their source-byte order accordingly.
  Names/inventory icons are a separate UI path, not converted by this proposal.
- Preview: original ULA at frames 500/1500/2500/3500, replay stopped after 3501. This is a reference
  preview, NOT a simulated sprite build or evidence of sprite output correctness.
- Plain baseline: converter `keep_printer_buffer=True`, tail 0x5E40..0x5E8F (80 bytes), 50Hz.
  Simulated boot PASS with and without NEXLOAD printer-buffer overwrite; registers, RAM outside
  the explicit tail, ROM and paging checked. Ordinary CLI conversion without buffer restoration
  failed the NEXLOAD case (255 overwritten printer-buffer bytes), so that output was replaced.
  Tail lifetime safety relies on the prior full-recording scan noted in the OPUS research and
  still needs this run's access verification before a final conversion.
- Unpainted main and collectable sheets read back as zero colour edits. Frame wrap and black /
  bright palette mapping checked. `git diff --check` clean. Shared code unchanged: no canary due.

## Existing user choices and remaining visual question
Carry forward the existing game's recorded choices: ALL moving figures and collectables become
sprites; in front of scenery; existing game colours as starting defaults. Proposed remaining
behaviour: retain see-through gaps in the original graphics; hide sprites during full-screen
option/inventory windows; preserve disappearance when identical XOR enemy images cancel.
Keep scenery, HUD, text and inventory UI on the ULA. Diamonds proposed white, paintable separately.
Confirm these details against the preview and sheets; painting is optional at this stage and
belongs to the user, not an AI-generated pixel-art draft.

## Reproduce
Run from the nexclash checkout (set PYTHONDONTWRITEBYTECODE=1 to avoid cache files).

```sh
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA sheet INPUT.rzx --z80 INPUT.z80 -o PRIVATE_DIR/incredible_shrinking_fireman-add-GPT6_ASTRA
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA plain INPUT.z80 -o PRIVATE_DIR/incredible_shrinking_fireman_plain-add-GPT6_ASTRA.nex
python -m nexclash.incredible_shrinking_fireman_add_GPT6_ASTRA colours PAINTED.png --layout ORIGINAL_layout-add-GPT6_ASTRA.json
```
Generated files put the suffix immediately before their extension (including layouts).
For future records/selftests set NEXCLASH_REFERENCE to the suffixed specnext checkout's reference
folder; do not assume the conventional ../specnext directory exists.

## Open / phase B
- Confirm visual choices; identify which static/unseen figures need additional recordings.
- Scan hook/tail/state memory and all screen readers/writers; prove virtual-read behaviour,
  attribute dependencies, window cleanup and XOR overlap handling.
- Implement isolated hooks/profile, sprite builder, per-pixel colours, recolour and differential
  verification; preserve IM2 vector and interrupt safety. Measure hook cost.
- Only then create the production evidence record, register the engine, regenerate record views,
  and perform the single final full verification/stamp. No incomplete record masquerading as PASS.
- Hardware checklist: CSpect boot first; start/play, room changes, collect/pick up/drop, inventory,
  options, death/game over/restart, figure overlap, speed and flicker. No hardware run yet.
- Initial CLI push lacked GitHub credentials; subsequent publishing uses the connected GitHub API.

## Capture questions
1. No new general platform fact: printer-buffer restoration is already documented in z80tonex.
2. No shared documentation correction necessary.
3. No actual emulator/hardware failure; NEXLOAD simulation caught the known startup requirement.
4. Detached setsid/nohup jobs did not survive this host; used tool-managed foreground sessions.
5. Unproven work is listed above. All additions and limitations recorded here.
