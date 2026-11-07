# Restore the caller's CPU speed at hook exit, never a fixed 3.5 MHz

```json
{
  "schema": 4,
  "id": "patch.restore-speed",
  "revision": 1,
  "kind": "patch",
  "title": "Restore the caller's CPU speed at hook exit, never a fixed 3.5 MHz",
  "question": "Does every hook exit leave the CPU at the speed the game was running at when the hook was entered?",
  "tags": ["speed", "nextreg-7", "turbo", "hook-library", "timing"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {"entry": {"after": ["patch.preserve-r"]}, "exit": {"before": ["patch.preserve-r"]},
            "cross": ["the latch is read before the NEXTREG $07,3", "nested hooks use their own latch byte"]},
  "owns": {"speed": "28MHz-inside-hook, caller's NR 7 restored", "hook_state": ["latch"]},
  "examples": ["knight_tyme", "spellbound_magic_knight"],
  "sources": ["docs/REFACTOR.md item 4", "pilot runs/atic_atac work/PERFORMANCE.md (2026-11-04: save_speed, every_site.json 192 cases)",
              "asm/lib/hlib_speed.asm + nexclash/hooklib.py (the shared library, 2026-11-04)"]
}
```

## Use / do not use
Every NEW engine's hooks: `INCLUDE "lib/hlib_speed.asm"`, `HLIB_SPEED_IN latch` at entry, `HLIB_SPEED_OUT
latch` at every exit (ENGINE_CONTRACT "Hook library"). The old convention `NEXTREG $07,0` at exit is harmless
while every caller runs at 3.5 MHz, but breaks any speed option, a "slowdown removed" mode, the F8 key (NR 6
bit 7 is left on, C2 #26) and a hook called from another hook. Existing engines keep it until a rework. A hook
with no RAM (alt ROM only: Jet Pac v1.1) keeps the read value on the stack instead of a latch.

**Assumptions.** NR 7 reads back bits 1:0 = the programmed speed (core 3.02 zxnext.vhd 5902; JNext 1.1.104
composes the same); the game and its ROM ISR never use ports 0x243B / 0x253B (a Spectrum game cannot).

**Validation gap.** Library unit tests on the simulator (NR 7 modelled as the core composes it); the
Atic Atac v1.1 candidate in JNext (all four clocks, 24 sites). No board run of the library.

## Recognise
A hook ending `nextreg 0x07,0`, or entering `nextreg 0x07,3` with nothing read first (`grep -n 'nextreg
0x07' asm/*.asm`). A game slower or faster after a hook only when a speed option is on.

## Probe and stop
`hooklib.every_site(sites, run)`: each hook entered at clocks 0-3 from a collected state must exit at the
same clock with the same results. Stop when every site passes.

## Contract
- State: the macros keep every register and flag (`_ABC` / `_A` forms lose what they say); stack: hook
  stack: 4 bytes (IN) / 2 bytes (OUT) below SP, 0 for the `_ABC` / `_A` forms; interrupt headroom: the
  game's ISR depth, as without the hook.
- Time: 97 T at the incoming clock before the NEXTREG; port 0x243B is left selecting register 7.
- Display: software = return/boundary only; hardware = checklist item "speed options and F8 change the game, the hooks never undo them"

## Resources owned
One latch byte per hook level, in hook RAM.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| a speed option resets after the first draw | fixed 3.5 MHz exit | every_site, clock 1-3 | the latch | - |
| outer hook finishes at 3.5 MHz | nested hook shares the latch | read the hooks | a latch per level | DI around |

## Verification
Every-site matrix (four clocks per site) in the engine's unit tests. Negative control: a forced 3.5 MHz
exit (`hooklib.NEGATIVES`) must fail the matrix at clocks 1-3; selftest --tools runs it. An existing engine's
verifier must answer the latch's IN (0x253B) from its NextREG model, not from recorded port input (Knight
Tyme, Spellbound: `_NS.nr_read`).

## Evidence
- `grep -n 'MACRO HLIB_SPEED' asm/lib/hlib_speed.asm`; `grep -n 'def every_site\|def _t_matrix' nexclash/hooklib.py`.
- Atic Atac v1.1's `save_speed` (pilot runs/atic_atac/nexclash/asm/atic_atac_hooks.asm), observed in JNext.
