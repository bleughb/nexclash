# 1-bit shadow screen for XOR-drawn figures

```json
{
  "schema": 3,
  "id": "patch.xor-shadow",
  "revision": 1,
  "kind": "patch",
  "title": "1-bit shadow screen for XOR-drawn figures",
  "question": "Can XOR-drawn figures leave the ULA while the original screen stays exactly recoverable?",
  "tags": ["xor", "shadow", "screen", "layer2", "sprites"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["render.composition.xor", "mem.hook_page_slot_free"],
  "rejects": ["screen.gameplay_reads_figure_pixels"],
  "conflicts": ["patch.xor-overlay-keep-ula"],
  "phases": ["entry", "clear"],
  "order": {
    "entry": {"after": []},
    "clear": {"after": []},
    "cross": ["every converted XOR goes to the shadow; every non-XOR writer keeps ULA ^ shadow = original"]
  },
  "owns": {"mmu_slots": "param", "memory": "param", "sprite_ids": "param", "pattern_slots": "param"},
  "examples": ["dizzy1", "atic_atac"],
  "sources": []
}
```

## Use / do not use
Send converted XOR writes to a 1-bit shadow screen instead of the ULA, so ULA ^ shadow equals the
original screen at every moment, and show figures from the shadow (Layer 2) or per-image sprites.
Do not use when gameplay reads figure pixels (the ULA no longer holds them: use
patch.xor-overlay-keep-ula), or when the composition is not XOR.

## Recognise
- Pure XOR plotters, many figure kinds, partial draws, thin pieces (Dizzy 1; Atic Atac's rows).
- XOR is linear, so every caller, partial draw, overlap and double draw is exact without modelling.
- Other writers that change figure bits (clears, scenery drawers, text) must keep the invariant.

## Probe and stop
1. `render.composition.xor` per plotter (manual: writers + disassembly).
2. detect.gameplay-screen-readers: must be false in scope.
3. List non-XOR writers that change figure bits (`screen.other_writers_change_figure_bits`).
4. `isr GAME.z80 --rzx R`: a slot for the shadow page.
Stop when each non-XOR writer has a rule: new ULA = op(ULA ^ shadow, v) ^ shadow, or a fold.

## Contract
- State: ULA ^ shadow == the original screen after every write; every screen read sees the
  original's value; the game's own code runs (row hooks write the shadow with the same code).
- Time: hooks at figure level where row calls are many (detect.tracked-unit); 28 MHz inside.
  Hook stack: per engine; interrupt headroom stated when IFF is on (Atic Atac: ROM IM 1, keeps IY).
- Display: one shared XOR layer cancels touching figures (Dizzy 1 hardware round 1); per-image
  sprites keep each figure solid (Atic Atac). Play-area clear: shadow zeroed, sprites hidden.
- Display: software = return/boundary only; hardware = checklist item "touching figures stay solid; nothing left behind at room change"
- Self-modified op bytes in the drawers: move the site off them, read the op at run time.

## Resources owned
A shadow page (and attribute shadow if attributes are XORed), its MMU slot during hooks, sprites
and patterns per shown image.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Touching figures cancel / vanish | one shared XOR layer | hardware | per-image sprites or per-figure shadow | single Layer 2 for all figures |
| Scenery corrupted where a figure stood | a non-XOR writer applied to the ULA alone | classify that writer | fold its change through the shadow | - |
| Wrong op after a mode change | site on a self-modified op byte | static LD (nn),A scan | move the site, read op at run time | - |

## Verification
ULA ^ shadow vs the original screen at every hook; registers and memory; sprites vs the parity
model by tracked unit; negative controls: no fold for a non-XOR writer must fail.

## Evidence
- games/dizzy_ultimate_cartoon_adventure.md (method); games/atic_atac.md "Build design"; LEARNINGS 2.1d.
- `grep -n 'def run_pair\|def compare\|class Model' nexclash/dizzy1.py`;
  `grep -n 'def event\|class Expect' nexclash/atic_atac.py`; asm labels `h_rowa`, `h_o1`, `h_clear`:
  asm/atic_atac_hooks.asm.
