# Switch a figure's replacement image atomically (no hide/show)

```json
{
  "schema": 3,
  "id": "patch.display-atomic-switch",
  "revision": 1,
  "kind": "patch",
  "title": "Switch a figure's replacement image atomically (no hide/show)",
  "question": "When does the new image become visible relative to the original's drawing, and can the viewer see a gap or a half-done state?",
  "tags": ["flicker", "display", "sprites", "timing"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["hook.updates_visible_image"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {
    "entry": {"after": ["patch.isr-deferral"]},
    "exit": {"after": []},
    "cross": ["the new image is complete in other pattern memory before any attribute points at it",
              "the old image stays shown until the attributes switch"]
  },
  "owns": {"sprite_ids": "param", "pattern_slots": "param"},
  "examples": ["incredible_shrinking_fireman-add-OPUS", "atic_atac", "commando"],
  "sources": []
}
```

## Use / do not use
Keep the old image visible, build the new one in other pattern memory, then rewrite the sprite
attributes in one go, whenever a hook changes a figure that is on screen. Not needed when images
change only while hidden (a cleared screen, a room change).

## Recognise
- A hook hides sprites at plot entry and shows them at exit: hidden for the whole call, often
  across the beam (Commando 5c1081b7: flicker).
- A slow original draw (Fireman's XOR plot: 24-27K T, a third of a frame, 97%+ of plots while the
  beam draws) leaves its half-done ULA image visible if the sprite moves only at exit.
- XOR erase + redraw by the same owner shows an empty gap between them unless the entry is kept.

## Probe and stop
1. `cost GAME.z80 --rzx R --at PLOTTER`: T per draw (how long an intermediate state lasts).
2. From the design: when does each hook write attributes, patterns, or hide?
Stop when every visible change has a point where old and new are both complete.

## Contract
- State: none of its own (sprite memory is outside the game's).
- Time: pattern uploads before the attribute write; the switch itself is short.
- Display: from plot entry to exit, the old image or the new one covers the figure; no frame shows
  neither, and no frame shows the original's half-drawn pixels uncovered (Fireman: an entry hook
  shows the new image on pending sprites, the exit switches the figure's own sprites to it).
- Display: software = entry-to-exit coverage (incredible_shrinking_fireman_add_opus.verify); hardware = checklist item "no flicker while figures move or animate"

## Resources owned
Spare pattern slots or pending sprites per figure (double-buffered), in the record's `owns`.
Reuses a figure's sprites across erase/redraw by the same owner (Atic Atac: entry marked PENDING,
still shown).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Sprites flicker (Commando) | hidden at entry, shown at exit | read the hooks | this card | - |
| A bulb / figure flashes the cell colour (Fireman round 1) | half-done ULA plot uncovered for a third of a frame | `cost --at PLOTTER` | show the new image at entry | moving the sprite at exit only |
| Ghost left after an XOR erase | parity per image instead of per tracked unit | detect.tracked-unit | track the right unit | - |

## Verification
- Entry-to-exit coverage where the engine has it (Fireman: old + new image covered throughout,
  5.1M pixels); otherwise only boundary checks exist (BRIEFING C2: shared Display check).
- Negative control: hide at entry -> coverage check must fail.
- Hardware: figures moving over every kind of scenery.

## Evidence
- LEARNINGS 2.1e (the flicker rule); games/commando.md (pattern slots, round robin);
  games/incredible_shrinking_fireman-add-OPUS.md "Hardware round 1"; games/atic_atac.md "Build design".
- `grep -n 'def cover_of\|def _entry_case' nexclash/incredible_shrinking_fireman_add_opus.py`
- asm labels `pend`, `hidep`, `show`: asm/atic_atac_hooks.asm; `e_ent`: asm/commando_hooks.asm.
