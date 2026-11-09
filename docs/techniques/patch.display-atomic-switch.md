# Switch a figure's replacement image atomically (no hide/show)

```json
{
  "schema": 4,
  "id": "patch.display-atomic-switch",
  "revision": 3,
  "kind": "patch",
  "title": "Switch a figure's replacement image atomically (no hide/show)",
  "question": "When does the new image become visible relative to the original's drawing, and can the viewer see a gap or a half-done state?",
  "tags": ["flicker", "display", "sprites", "timing", "hook-library"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["hook.updates_visible_image"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit", "commit"],
  "order": {
    "entry": {"after": ["patch.isr-deferral"]},
    "exit": {"after": []},
    "commit": {"after": ["optimise.pattern-cache"]},
    "cross": ["the new image is complete in other pattern memory before any attribute points at it",
              "the old image stays shown until the attributes switch",
              "the attributes switch in one burst, right after the ULA change they go with"]
  },
  "owns": {"sprite_ids": "param", "pattern_slots": "param", "hook_state": ["HLIB_V_DB"]},
  "examples": ["incredible_shrinking_fireman-add-OPUS", "atic_atac", "commando", "inferno"],
  "sources": ["pilot runs/nightshade nightshade_hooks.asm burst / vbase (the blink fix, 2026-11-04)",
              "asm/lib/hlib_commit.asm + nexclash/hooklib.py (the shared library)"]
}
```

## Use / do not use
Keep the old image visible, build the new one in other pattern memory, then rewrite the sprite
attributes in one go, whenever a hook changes a figure that is on screen. Not needed when images
change only while hidden (a cleared screen, a room change). NEW engines that redraw every figure per
frame use the library (ENGINE_CONTRACT "Hook library"): the frame's images into the back half
(`hlib_db_back`, through the content cache), the attributes into a table, then `hlib_commit` right
after the game's blit - one burst, unused sprites off, the halves flipped.

**Assumptions.** Half of the pattern memory holds a frame's images; the ULA change the sprites go with is
one routine the hook can follow (the blit).

**Validation gap.** Fireman's coverage, Nightshade's verifier; the library's commit on the simulator only.
Inferno: one Copper list (attributes, tilemap, layer enables) at line 224; hardware by eye.

## Recognise
- A hook hides sprites at plot entry and shows them at exit: hidden for the whole call, often
  across the beam (Commando 5c1081b7: flicker).
- A slow original draw (Fireman's XOR plot, a third of a frame) leaves its half-done ULA image
  visible if the sprite moves only at exit.
- XOR erase + redraw by the same owner shows an empty gap between them unless the entry is kept.
- Sprites and the picture a frame apart (Nightshade's blink): the switch before the blit.

## Probe and stop
1. `cost GAME.z80 --rzx R --at PLOTTER`: T per draw (how long an intermediate state lasts).
2. When does each hook write attributes, patterns, or hide? 3. `python -m nexclash.flicker`.
Stop when old and new are both complete at every visible change.

## Contract
- State: none of its own (sprite memory is outside the game's).
- Time: pattern uploads before the burst; the burst is 5 OUTs a sprite;
  `hlib_beam_wait` holds it below the play area when tearing shows. Hook stack: 2 bytes; interrupt
  headroom: as the hook.
- Display: from plot entry to exit, the old or new image covers the figure.
- Display: software = entry-to-exit coverage (incredible_shrinking_fireman_add_opus.verify); hardware = checklist item "no flicker while figures move or animate"

## Resources owned
Spare pattern slots or a back half per frame, in the record's `owns`; HLIB_V_DB (2 bytes).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Sprites flicker (Commando) | hidden at entry, shown at exit | read the hooks | this card | - |
| A figure flashes the cell colour (Fireman round 1) | half-done ULA plot uncovered | `cost --at PLOTTER` | new image at entry | moving at exit only |
| Ghost left after an XOR erase | parity per image, not per tracked unit | detect.tracked-unit | the right unit | - |
| Blink, sprites a frame off (Nightshade) | switch before the blit | flicker | hlib_commit after it | - |
| Out of step (Cyclone) | ULA change over a frame | flicker | 28 MHz; short of lines: wait for the interrupt | - |

## Verification
- Entry-to-exit coverage where the engine has it (Fireman); else boundary checks.
- `hooklib.NextModel`: 'upload into a shown pattern!' and `burst_ok` per hook call.
- Negative controls: hide at entry (coverage fails); one pattern buffer; attributes split by uploads
  (`hooklib.NEGATIVES`, selftest --tools).
- Hardware: figures moving over all scenery.

## Evidence
- LEARNINGS 2.1e; games/incredible_shrinking_fireman-add-OPUS.md "Hardware round 1".
- `grep -n 'def cover_of\|def _entry_case' nexclash/incredible_shrinking_fireman_add_opus.py`
- asm labels `pend`, `hidep`, `show`: asm/atic_atac_hooks.asm; `e_ent`: asm/commando_hooks.asm;
  `hlib_commit`, `hlib_db_back`: asm/lib/hlib_commit.asm.
