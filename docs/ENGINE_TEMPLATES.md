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

| finders_keepers.py | stateless alt-ROM hooks over an XOR plotter, the 2026-11-22 checklist below applied (speed kept on the stack, auto runs units + negatives + desync, hide-hook unit cases) |

## New engine checklist (2026-11-22: the six faults one review round found in six engines)
1. Speed: hooks keep the caller's NR 7. Alt-ROM hooks (no RAM) use `HLIB_SPEED_IN_SP` / `HLIB_SPEED_OUT_SP`
   (asm/lib/hlib_speed.asm); never write a constant to NR 7 on the way out. `hooklib.speed_audit` (selftest
   --tools) refuses one; the verifier enters unit cases at all four speeds, a negative control leaves 28 MHz.
2. auto(): runs `unit_tests` and the negative controls itself, fails a run with no coverage, and a replay that loses
   sync fails (`on_desync`). doccheck checks the calls (AUTO_LEGACY lists the older engines).
3. Hide-type hooks (room set-up, clear screen, window): unit cases from captured states with every sprite shown,
   `hooklib.hide_cases`, so their negative controls never depend on a recording reaching them.
4. A port re-derives every pin: MD5s of screens, snapshots and tables, addresses, sizes. doccheck refuses one MD5 in
   two engines (SHARED_MD5 for real sharing, with why).
5. NEXLOAD: a snapshot with its stack, code or live data in 0x5B00-0x5BFF needs `keep_printer_buffer` (48K and 128K)
   or the game's own set-up putting it back; boot with `nextboot.boot(..., nexload=True)` to see it.
6. Review (Codex or a person) the first engine commit, before the record and the patch exist: fixes are cheaper then.
Record: `python tools/mkrecord.py SPEC.json REFERENCE_DIR --stamp` writes it whole (its docstring has the spec).

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
