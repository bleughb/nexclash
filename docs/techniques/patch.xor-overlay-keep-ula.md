# Overlay: keep every ULA write, cover XOR figures with sprites

```json
{
  "schema": 4,
  "id": "patch.xor-overlay-keep-ula",
  "revision": 2,
  "kind": "patch",
  "title": "Overlay: keep every ULA write, cover XOR figures with sprites",
  "question": "Can figures become sprites without changing a single screen byte the game reads?",
  "tags": ["xor", "overlay", "sprites", "screen-reads"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["render.composition.xor", "design.figures_in_front"],
  "rejects": [],
  "conflicts": ["patch.xor-shadow"],
  "phases": ["entry", "exit", "clear"],
  "order": {
    "entry": {"after": ["patch.isr-deferral"]},
    "exit": {"after": []},
    "cross": ["sprites cover the figure's ink pixels from plot entry to exit (patch.display-atomic-switch)"]
  },
  "owns": {"mmu_slots": "param", "memory": "param", "sprite_ids": "param", "pattern_slots": "param"},
  "examples": ["incredible_shrinking_fireman-add-OPUS", "cauldron"],
  "sources": []
}
```

## Use / do not use
Leave the plotter writing the ULA exactly as the original, and put hardware sprites exactly on each
figure's ink pixels, in front. Use when figures go in front and gameplay may read XOR figure pixels
(nothing changes on the ULA, so no virtual read is needed). Do not use when figures must go behind
scenery (the ULA's XOR hole shows), or when the composition is not XOR.

**Assumptions.** Figure pixels change only by their own plots, or every other writer is hooked.

**Validation gap.** Fireman OPUS and Cauldron only; no masked or partial XOR images yet.

## Recognise
- XOR figures that logic reads or might read, and the user wants figures in front (Fireman).
- Every ULA pixel that differs from the clean scenery is a figure ink pixel under its own sprite,
  so the picture = scenery + sprites; where a figure crosses scenery ink, the sprite covers the hole.
- Attribute painting of figure cells is usually what causes the clash: it can be removed if no
  logic reads those attributes (Fireman: 0xBCDF LD (IX+0),A -> NOPs, value dead); if logic reads
  them, patch.attribute-shadow.
- No object table (compiled BASIC, Cauldron): key = (graphic, x, y, rows, width); a plot toggles it.

## Probe and stop
1. `render.composition.xor` per plotter.
2. `design.figures_in_front` from the stage-1 answer.
3. Attribute readers in scope before removing figure-cell painting.
4. `cost GAME.z80 --rzx R --at PLOTTER`: long plots need patch.display-atomic-switch.
Stop when the requirements are settled and every attribute write to be removed has no reader.

## Contract
- State: the ULA bitmap identical to the original at every moment; attributes differ only where
  painting was removed and nothing reads them.
- Time: hooks at plot entry and exit add time: check patch.isr-deferral's predicates.
- Display: sprite pixels = the figure's ink (+ an approved outline / mask); covered from entry to
  exit. Approved changes recorded per game (Fireman: 4-neighbour mask requested by Dean; black suggested, not objected to).
- Display: software = entry-to-exit coverage (incredible_shrinking_fireman_add_opus.verify); hardware = checklist item "figures solid over scenery; no cell-colour flashes"

## Resources owned
Sprites per figure (+ pending set for the switch), pattern store pages and the slot they map to
during hooks, alt ROM hook ranges.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Cell-colour flashes beside figures (Fireman round 1) | sprite moved only at exit; half-done plot visible | `cost --at` | patch.display-atomic-switch | - |
| Extra figures / garbage in one room (Fireman round 2) | added hook time let the ISR nest a plot | patch.isr-deferral probes | patch.isr-deferral | save/restore globals |
| Item or diamond at the wrong x | coordinate unit assumed (column vs pixel) | read the address helper | take the unit from the helper | - |
| Sprite left where the figure was wiped or moved (Cauldron) | clears, scrolls, text overwrite XOR figures without an erase | byte trace of the figure's rows between plots | hook every other writer: it ends the sprite | XOR parity alone |

## Verification
Registers and memory at every hook; plot screen change = old ^ new image of the model; sprite layer
incl. mask vs the model; old + new covered from entry to exit; attribute reads vs the removed
painter; negative controls.

## Evidence
- games/incredible_shrinking_fireman-add-OPUS.md "Build", "Hardware round 1-2"; PLAYBOOK 4 (overlay row);
  LEARNINGS 2.1a (coordinate unit from the address helper).
- `grep -n 'class Model\|def event\|def cover_of\|def verify' nexclash/incredible_shrinking_fireman_add_opus.py`;
  asm labels `e_ent`, `e_plot`, `e_item`: asm/incredible_shrinking_fireman-add-OPUS_hooks.asm.
