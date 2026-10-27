# Engine contract (what every dedicated engine provides; read this before any engine's code)

Start a new engine from this page; open a real engine only for the one function you need
(`grep -n '^def \|^class ' nexclash/<engine>.py`, then Read that range). Template with everything
in its simplest form: nexclash/chuckie.py. `tools/doccheck.py` checks the REQUIRED names below
against every module in nexclash/engines.py, so this page cannot drift from the code.

## Files (one game = one engine; CLAUDE.md "Keep changes additive")
nexclash/<engine>.py, asm/<engine>_hooks.asm, docs/profiles/<record>.json (hook hex + symbols, from
`python tools/asm2profile.py <engine>`), games/<game>.md, docs/records/<record>.json, one line in
nexclash/engines.py: `('<engine>', 'is_<engine>', None)`.

## Module names
REQUIRED (doccheck):

| Name | Contract |
|---|---|
| `is_<engine>(snap)` | True only for this game: machine + the profile's `signature` bytes at their address (skoolkit Snapshot) |
| `load_profile()` | the profile json (path from `_profile_path()`) |
| `auto(a, z80, name, out, say)` | the whole run: plain + sprite build with boot checks, autosaves stripped, verify each `a.rzx` (`a.quick` = frames), unit tests + negative control, `say()` report lines `Plain`, `Sprites`, `Verify`, `Unit`, `Result : PASSED / FAILED`; returns True on PASS |
| `verify(patch, rzx_path, stop=None, collect=0, progress=None)` | differential test (PLAYBOOK 6) -> `(Counter, examples[, states])`; failure keys end in `!`; `collect=N` keeps N machine states per site kind for the unit tests. Free-run engines (no RZX: jetpac, loderunner) take `(patch, z80, rzx=None, frames, keys, ...)` |
| `unit_tests(patch, states, neg...)` | cases the RZX does not reach + the negative control (CLAUDE.md rule) -> Counter, failures end in `!` |
| `CMP` | register indexes compared (all but R, T, MEMPTR) |

OPTIONAL (when the engine has the feature):

| Name | Contract |
|---|---|
| `RECOLOUR = {...}` + `recolour(nex_bytes, cmap)` | both or neither (doccheck); docs/COLOURS.md RECOLOUR |
| `COLOURS`, `load_colours()`, `sheets(...)` / `capture(...)` | colour map path (via `recolour.build_colours_path`), sheet capture (docs/COLOURS.md) |
| `colour_identity(peek)` (+ `nex_peek(nex)` for 128K) | what a map / sheet means for this build; stored in sheet layouts, compared by recolour (docs/COLOURS.md "Identity") |
| `negative_patch(patch)` / `negative_patches(...)` | the broken builds the negative controls run |
| `boot_check(nex, z80, patch)` | 128K builds: the engine's own boot check (nextboot.check is 48K only) |
| `DECISIONS` | stored build facts for `auto --decisions` (docs/records `rebuild.decisions`) |
| `INTERIORS`, `TAIL_ADDR`, `ROM_ORG`, `ALT_PAGE` | patched-instruction interiors (no jumps into them), tail and hook addresses |

## The patch object (what z80tonex.convert and nextboot.check read)
`name`; `sites` = [(addr, original bytes, new bytes)] - `apply(snap)` refuses a snapshot whose
bytes differ; `stub_extra` + `setup_call` (setup code the stub runs), `hook_page_data`,
`extra_banks` {bank: bytes}, `uses_printer_buffer`, `tail_addr` (below 0xC000); alt-ROM hooks:
`altrom = (lo, hi)` + `page` (the 8K image); ROM bytes below 0x2000 (a JP into the hooks at a
ROM routine, Cauldron): `altrom_low = (RAM page, 8K image of 0x0000-0x1FFF)` - with `altrom =
(0x2000, 0x4000)` the whole image is the build's, not the Next's NextZXOS ROM3 (BRIEFING C2 #5;
z80tonex.altrom_fill copies it, nextboot.check compares it); older strategies `slot1`,
`keep_printer_buffer`, `max_tail`.

## Verify loop (the part every engine repeats; copy it from chuckie.verify)
Replay the RZX with the opcode table wrapped: at a hook site copy the state, run original and
patched code to their return (simulators from `simpool.machine`), compare CMP registers, memory,
sprite pixels; `fail()` keeps 5 examples per key; also count writes to patch sites and jumps into
INTERIORS (a site whose first instruction is 1 byte: the original itself runs the next bytes - count
them against the site's own count, SEQUELS; Fireman, Cauldron). Hook asm may use Z80N: the verifier installs it with `z80n.install(sim, nextreg)`.
A hook that runs the routine itself (CALL body / the routine's RET comes back to the hook, e.g. when
the next routine starts right after the RET, so no exit JP fits: Cauldron 0x6357) meets the original
at the CALLER's return: the replay must skip sites nested inside it until that point (Cauldron
`span`), or they are applied twice.

## Record (docs/records/<record>.json)
Fields: nexclash/records.py docstring; copy the nearest record. `python -m nexclash.records deps
<record>` lists what its evidence depends on.
