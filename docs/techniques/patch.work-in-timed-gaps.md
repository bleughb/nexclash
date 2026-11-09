# Do hook work in the gaps between hard deadlines; drop what does not finish

```json
{
  "schema": 4,
  "id": "patch.work-in-timed-gaps",
  "revision": 1,
  "kind": "patch",
  "title": "Do hook work in the gaps between hard deadlines; drop what does not finish",
  "question": "Can added work run inside a timed window without moving its deadlines, and what happens when it does not fit?",
  "tags": ["coroutine", "scheduling", "deadline", "freshness", "timing"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["hook.adds_time"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "commit"],
  "order": {"entry": {"after": ["patch.timed-side-effect-replay"]},
            "cross": ["a slice starts only when the next deadline is far enough away and ends before it",
                      "unfinished work is dropped at the update boundary, never finished after the limiter"]},
  "owns": {"next_pages": "param", "hook_state": ["WK_SP"]},
  "examples": ["inferno"],
  "sources": ["specnext reference/inferno/build/copier_window.md sections 8-9; build/pipeline.md"]
}
```

## Use / do not use
When a window has idle time between deadlines (OUT times, a pad) and the hook has work that can be
split: run the work as a coroutine in slices, each started only with enough ticks to the next
deadline. Work not finished by the update boundary is dropped; the display keeps the last complete
frame and the next update starts again from fresh capture. Not for work whose result the game
reads, and not where a dropped update would be visible for long (agree it with the user).

**Assumptions.** The work can yield at fine points (Inferno: per map cell, per tile); its partial
state is private until a final "ready" byte.

**Validation gap.** Inferno: 1,855 model states; each added stage raised drops (12 % with scenery
only, 17-20 % with selection and uploads, runs up to 32-35 updates) before the write-out was
reclaimed; no hardware freshness readout yet.

## Recognise
Idle polling inside a timed window; deferred work that "finishes after the limiter" (that eats the
slack the window saved).

## Probe and stop
1. Slice margin: minimum ticks between a slice's end and the next deadline over all CTC phases.
2. Per update: phase reached, slice time granted, dropped or published.
3. Report publication rate, longest run of drops, maximum displayed-state age.
Stop when the margin is positive on every state and the drop runs are agreed.

## Contract
- State: game state untouched; partial results private until ready.
- Time: a yield saves SP and live registers without CALL (a loop that uses SP as a data pointer);
  the slice gate polls often enough to keep the margin. Hook stack: the coroutine's own stack;
  interrupt headroom: interrupts off: n/a.
- Display: software = return/boundary only; hardware = checklist item "busy scenes show no long freezes"

## Resources owned
The coroutine's page and stack; the ready flag; values in the record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Runs of 32 dropped | busy windows nearly full; per-chunk cost | per-update profile | shorten the hit path; reclaim other time | preallocation (cold frames were not the cause) |
| Margin collapses | a scan between polls | slice margin | test one slot per poll | - |
| Drops doubled | 64-slot scan per new pattern | profile | recency list | - |

## Verification
Per state: the window's deadlines unchanged with work on; dropped work leaves no published byte.
Negative control: a slice that ignores the gate must break the OUT tolerance.

## Evidence
- `grep -n '^cw_wait\|^wk_hook\|^wk_select' asm/inferno_hooks.asm`; nexclash/inferno.py
  cw_work_renderer.
- games/inferno.md "Lessons" (drop runs, coroutine, 8F95 budget), observed in the model.
