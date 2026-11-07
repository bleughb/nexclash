# Read the caller's IFF safely, restore it, and keep DI windows short

```json
{
  "schema": 4,
  "id": "patch.iff-safe-read",
  "revision": 1,
  "kind": "patch",
  "title": "Read the caller's IFF safely, restore it, and keep DI windows short",
  "question": "Can a hook leave interrupts off, or hold them off across the frame's interrupt, when the original would have taken it?",
  "tags": ["interrupt", "iff", "timing", "hook-library"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {"entry": {"after": []}, "exit": {"before": []},
            "cross": ["the second LD A,I runs only when the first read said off", "the DI follows both reads"]},
  "owns": {"registers_clobbered": ["A", "F"]},
  "examples": ["incredible_shrinking_fireman-add-OPUS", "renegade"],
  "sources": ["pilot runs/quazatron HANDOFF-SESSION6.md (JNext, 2026-11-06: 31 -> 5 missed interrupts in 1,400 frames)",
              "asm/lib/hlib_iff.asm + nexclash/hooklib.py (the shared library, 2026-11-07)"]
}
```

## Use / do not use
Every hook that disables interrupts and must give the caller's state back: `INCLUDE "lib/hlib_iff.asm"`,
`HLIB_IFF_DI` (then PUSH AF) at entry, POP AF + `HLIB_IFF_EI` at every exit. A hook that only runs where
interrupts are always off (inside the ISR, with no EI in the game's handler) does not need it; say so.
Line reads with interrupts on: `hlib_line_di` (hlib_pace.asm), called at 28 MHz.

**Assumptions.** An interrupt accepted at the end of LD A,I / LD A,R leaves P/V = 0 (NMOS Z80; JNext
does it, SkoolKit's simulator too; the Next's core untested - the double read is right either way). The
/INT lasts 32 T at 3.5 MHz on a Spectrum; at 28 MHz JNext loses interrupts in DI windows of a few hundred T (Quazatron).

**Validation gap.** Library unit tests on the simulator with the interrupt injected; JNext interrupt counts
on the games that changed. No board run.

## Recognise
`LD A,I` then DI, PUSH AF ... POP AF, JP PO / RET PO with no second read (`hooklib.iff_audit()`: 'once'), or
two reads back to back with the second trusted ('pair': an interrupt at the end of the second still reads
as off). A game whose interrupt count in JNext falls below the original's (soak / pace "interrupts per s").

## Probe and stop
`python -m nexclash.hooklib` (iff_audit over asm/), then the soak or pace tool's interrupts per second,
build against original. Stop when the audit lists no 'once' / 'pair' and the counts match.

## Contract
- State: HLIB_IFF_DI loses A (= I) and F (P/V = IFF); HLIB_IFF_EI keeps everything; stack: hook stack: the
  caller's PUSH AF only; interrupt headroom: the game's ISR depth, as without the hook.
- Time: 2 or 4 M1 + DI at entry, one JP at exit; every DI window kept as short as the work allows.
- Display: software = return/boundary only; hardware = checklist item "music and game clock at the original's tempo"

## Resources owned
None beyond the caller's stack word.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| fewer interrupts a second than the original; music drags | single LD A,I trusted after an interrupt | iff_audit | read twice (HLIB_IFF_DI) | read twice unconditionally |
| same, with no LD A,I | a DI window across the interrupt (a poll loop, a whole hook under DI) | JNext DI samples at the interrupt line (jnext.counters di_lines) | short DI per poll; defer the handler (patch.isr-deferral) | a longer EI pause only |

## Verification
`hooklib._t_iff`: entered with interrupts on / off, with and without an interrupt at the first read: the
caller's IFF back. Negative control: one read (`NEG_IFF1`) must leave interrupts off. `iff_audit` in
selftest --tools fails on any 'once' or 'pair' in asm/.

## Evidence
- `grep -n 'MACRO HLIB_IFF' asm/lib/hlib_iff.asm`; `grep -n 'def _t_iff\|def iff_audit' nexclash/hooklib.py`.
- Quazatron session 6 (pilot runs/quazatron/HANDOFF-SESSION6.md): observed in JNext.
