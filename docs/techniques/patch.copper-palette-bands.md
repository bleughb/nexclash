# Copper palette bands: 16 colours per band of lines in Layer 2 640x256

```json
{
  "schema": 4,
  "id": "patch.copper-palette-bands",
  "revision": 1,
  "kind": "patch",
  "title": "Copper palette bands: 16 colours per band of lines in Layer 2 640x256",
  "question": "Can a 4-bit Layer 2 picture (640x256) show more than 16 colours by giving each band of lines its own palette, without seams?",
  "tags": ["copper", "palette", "layer2", "640x256", "showpiece", "title-screen", "colours"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["menu"],
  "order": {"cross": ["the Copper fills the hidden Layer 2 palette during the band above and switches with one write in the horizontal blank",
                      "the top band's palette is set below the picture, for the next frame's border lines"]},
  "owns": {"hook_state": ["COPPER_LIST"]},
  "examples": ["r_type"],
  "sources": ["specnext reference/r_type/intake/showpiece.py (convert, copper); glide.asm reveal_on; PR #99",
              "dev guide r3 Copper chapter; BRIEFING item 28 (Copper facts to confirm)"]
}
```

## Use / do not use
Use for a still picture (title, intro, a "wow" upgrade of an original screen) that needs full horizontal detail and more than 16 colours. Quantise each band of 8 lines to its own 16 colours (dithered within the band). The Copper loads band n+1 into the Layer 2 palette that is not shown (NR 0x43 bits 6-4 select the palette written, bit 2 the Layer 2 palette shown) while band n is drawn, then WAITs for the line above band n+1 at h 40 (past the visible width) and switches with one MOVE. If the picture is already 320x256 with up to 256 colours, use the 320x256x8 mode and one palette instead: no Copper. Not for a scrolling or changing picture (bands are per screen line).

**Assumptions.** The picture is still; the Copper is free while it shows; the WAIT offset is measured on the target (CSpect: n + 32).

**Validation gap.** CSpect only (R-Type start-up); NR 0x64 alignment and the 9-bit failure not checked on a board.

## Recognise
A paletted or AI-upscaled picture to show at the highest Next resolution.

## Probe and stop
Preview offline (indices through each band's palette). In CSpect find rows whose whole width shows the wrong palette: they give the WAIT offset.

## Contract
- State: none of the game's (start-up or menu only); Copper stopped and the palette restored before the game draws.
- Time: about 20 instructions per band (8-bit palette); 32 bands fit the 1024-instruction list. Hook stack: 6 bytes for its own calls and pushes; interrupt headroom: interrupts off: n/a.
- Display: software = return/boundary only; hardware = checklist item "picture bands seamless, colours right top to bottom"

## Resources owned
The Copper list (R-Type: 2 KB in the glide page; never map a page into slot 6 at start-up: the NEX stub's stack is there).

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| only the top rows correct, rest one palette | WAITs for border lines 280-311 never pass: the Copper restarts at vertical blank after them | trial line numbering | one palette for the border rows, set at the end of the previous frame | - |
| one wrong line per band | WAIT offset (CSpect: WAIT line n, h 40 shows from row n + 32 of 320x256 Layer 2) | full-width wrong rows | adjust by the measured lead; or set NR 0x64 (BRIEFING item 28) | guessing the direction |
| colours wrong after band 0 | 9-bit NR 0x44 pairs written by the Copper | compare with 8-bit | NR 0x41, one write a colour | - |
| crash after the reveal | a page mapped into slot 6 at start-up (stack) | PC and SP at the crash | keep the list in an already mapped page | - |

## Verification
Screenshot after the reveal; count full-width wrong-palette rows (must be 0); smoke passes start-up. Negative control: a lead of +1 gives two wrong rows per band.

## Evidence
Observed in CSpect only (R-Type start-up). Hardware timing of the switch and of NR 0x64 not yet checked.
