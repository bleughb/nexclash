# Engine templates: the nearest engine to copy (PLAYBOOK 5; STATUS.md lists every engine)

| Engine | Template for |
|---|---|
| build.py TidPatch | Codemasters TID engine (generic builder) |
| chuckie.py | the simplest: 48K, stateless alt-ROM hooks (no RAM page), interrupts on |
| jetpac.py | 16K game, run-time graphics buffers, no RZX (free runs with a key schedule) |
| loderunner.py | XOR plotter, hooks in RAM (the game reads the alt ROM), figures printed as tiles |
| dizzy1.py | pure XOR to the screen: 1-bit shadow screen + Layer 2, outlines, plots at 28 MHz |
| wally.py / wally2.py | back-buffer composer, interrupts off / every figure on a double-buffered Layer 2 |
| midres.py | interrupts on, all RAM used: hook page at slot 5, CALL-target redirect into a scratch buffer, pattern-slot cache, per-pixel colour map |
| smashtv.py | the game's own plotters into a scratch buffer at slot 7, no frame sync, see-through outline |
| commando.py | 128K BASIC loader, front end, depth from walk boxes, cached solid sprites |
| renegade.py | alt ROM images 0 + 1, loading-screen front end |
| rainbow.py | full redraw / tile composer, 128K (excluded from automatic checks) |

## Colour map
(Moved from PLAYBOOK 5-6, 2026-11-08.)
Colour map (every game, docs/COLOURS.md): the sprite builder applies `<record>_colours.json` per pixel -
key = the graphics byte the pixel comes from, a non-zero nibble replaces the default colour of an
opaque pixel - and, in an engine with outlines (paint_clear), makes a PAPER pixel opaque in that
colour (Dizzy 1: fill_mask; its verify model and negative controls must cover it) - and a check of
the graphics bytes stored with the entry (other graphics at that
address in a later level -> defaults). Store it where the build can read it at sprite-build time
(midres: Next pages 28.. at slot 4 during the commit, page tables in the hook page, MidresPatch
store_pages / asm `ovl`). A build with no colours file = today's defaults.
Colour map: the expected sprite layer uses the map too (midres.expected_layer / map_colour); unit
cases with a synthetic map per figure, a wrong check byte (must be ignored) and a negative control
(the map left out of the build, informative cases only); once the user's colours file exists, the
full RZX run uses it.
