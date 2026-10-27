# Attribute shadow: clash-free scenery while the game still reads figure colours

```json
{
  "schema": 4,
  "id": "patch.attribute-shadow",
  "revision": 1,
  "kind": "patch",
  "title": "Attribute shadow: clash-free scenery while the game still reads figure colours",
  "question": "Can the ULA keep the scenery's colours when game logic reads the cells the plotter paints?",
  "tags": ["attributes", "clash", "screen-reads", "overlay"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["render.paints_figure_attributes", "screen.gameplay_reads_figure_attributes", "design.no_figure_clash", "mem.hook_page_slot_free"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {
    "entry": {"after": ["patch.xor-overlay-keep-ula"]},
    "exit": {"after": []},
    "cross": ["the shadow equals the original's attribute file at every hook boundary",
              "no attribute access outside the hooked routines"]
  },
  "owns": {"mmu_slots": "param", "memory": "param", "hook_state": ["shadow attribute file", "save pairs"]},
  "examples": ["cauldron"],
  "sources": []
}
```

## Use / do not use
Keep the original's attribute file in a Next page (the shadow), let the plotter paint only the
shadow, and redirect every other attribute reader and writer, so the ULA shows the scenery's
colours while logic sees exactly the original's. Use when figures are sprites (overlay) and logic
reads painted cells (otherwise simply drop the painting, patch.xor-overlay-keep-ula). Do not use
when the attribute accesses cannot all be found and hooked (a generic copy loop over the whole
screen that also reads attributes), or when no MMU slot is free while interrupts are on.

**Assumptions.** Every attribute access in scope comes from a finite set of routines; each writer's
value is computable on the shadow (pure fills, copies, shifts, ROM PO-ATTR); the ISR never touches
attributes or the shadow's slot.

**Validation gap.** One game (Cauldron, 48K, compiled BASIC, IM 1): quick 9,000 frames + unit
cases + hardware round 2; the full-recording stamp and a second game are missing.

## Recognise
- Clash halos round figures; `scan --writers` on 0x5800-0x5AFF lists the plotter among the writers
  and non-plotter readers (Cauldron: PEEK / ATTR runtime 0x61D8, room-cell read 0xB361).
- Save / restore of an attribute band (Cauldron 0xC9DB / 0xC9E7): the buffer holds painted values.

## Probe and stop
1. `scan GAME.z80 --rzx R --range 0x5800-0x5AFF --writers`: every writer and reader PC.
2. Disassemble each; class as pure writer, copy, shift, read-modify-write, reader.
3. `tools/probes/rzx_census.py R --pc <sites>`: counts and the first frame of each (quick-run length).
Stop when every PC is classed; unreached routines that touch attributes are listed as unknowns.

## Contract
- State: game memory identical to the original's except the ULA attribute file; every game read of
  an attribute returns the shadow's value; registers and flags of every hooked routine as the
  original's (run the shadow pass last).
- Time: one more page mapping per hook; reader hooks are hot (Cauldron PEEK 104K calls).
- Display: the ULA never shows figure painting; a restore gives back the ULA colours of its save.
- Display: software = return/boundary only; hardware = checklist item "scenery keeps its colours under figures"

## Resources owned
The shadow page and its slot (Cauldron: page 27 at slot 4, 0x8000 + attr offset), save pairs.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Clash comes back after a band restore | buffer restored to the ULA holds painted values | restore event diff | ULA from the save's ULA pairs | painting the ULA at restore |
| Register differs after a reader hook | shadow address left in a register | differential at the hook | restore the register (Cauldron PEEK H) | - |
| Gameplay drifts | an unhooked reader saw a ULA value | verify: read of a differing cell outside hooks | hook it | whitelisting dead reads |

## Verification
Shadow = the original's attributes after every event; the ULA attribute file = an independent
model; outside hooks any attribute write, or a read of a differing cell, fails; unit cases with
every ULA cell different; negative controls (plotter paints the ULA, reader reads the ULA, a writer
skips the shadow).

## Evidence
- games/cauldron.md "Build design round 2", "Results" (observed, quick 9,000 frames).
- `grep -n 'def attrs\|def verify\|def compare' nexclash/cauldron.py`; asm labels `e_peek`, `e_poa`,
  `body2`, `save27`, `rest27`: asm/cauldron_hooks.asm.
