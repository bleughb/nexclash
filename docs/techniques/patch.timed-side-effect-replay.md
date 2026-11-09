# Run a sound-producing routine fast, replay its port writes at the original times

```json
{
  "schema": 4,
  "id": "patch.timed-side-effect-replay",
  "revision": 1,
  "kind": "patch",
  "title": "Run a sound-producing routine fast, replay its port writes at the original times",
  "question": "Can a routine that also plays the beeper be accelerated without changing the sound or the game's pace?",
  "tags": ["sound", "beeper", "pace", "ctc", "window", "timing"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["routine.emits_timed_output", "hook.faster_than_original"],
  "rejects": [],
  "conflicts": [],
  "phases": ["entry", "exit"],
  "order": {"entry": {"after": ["patch.restore-speed"]},
            "cross": ["each logged OUT fires at its original T measured from the original entry",
                      "the exit waits until the original routine's end time (patch.pace-limiter)",
                      "work placed in the waits never delays a due OUT"]},
  "owns": {"next_pages": "param", "speed": "28MHz-inside-hook", "hook_state": ["CW_X"]},
  "examples": ["inferno"],
  "sources": ["specnext reference/inferno/build/copier_window.md sections 2-8"]
}
```

## Use / do not use
When detect.pacing-structure finds that code you need time from also writes the beeper (Inferno's
copier: one OUT 254 per cell). A translated copy runs at 28 MHz, logs each change of the port value
with its original T (a closed-form model of the original's timing), outputs each change when the
CTC says its time has come, and waits for the original exit time. The freed time between OUTs can
carry other work (patch.work-in-timed-gaps). Prefer detect.routine-removal first: if the routine's
other effects are display-only, replace rather than translate it.

**Assumptions.** The original's OUT times follow a model checked on every update (Inferno: head
T = 79,477 + 101 x tiles >= 16); a CTC channel can be polled (no counting CTC: run the original);
the first OUT is not due before the fast copy reaches it, else interleave (lockstep).

**Validation gap.** Inferno, 1,855 states in the model within -24..+56 T, speed and sound by ear on
hardware. ULA contention not modelled.

## Recognise
`OUT (254),A` inside a copy loop reading a sound buffer; turbo builds with garbled or short sound.

## Probe and stop
1. Fit and check the OUT time model on full recordings (`cw_out_t`).
2. Translate; compare registers, RAM and the OUT log (value, T) against the original per state.
3. Calibrate constants over all CTC phases (5 phases left Inferno 7 T off).
Stop when every OUT and the exit land within the stated tolerance on every captured state.

## Contract
- State: the copy's RAM result equals the original's. Exact R or a lost-IRQ count only when a
  consumer needs it (Inferno later showed only `LD A,R` readers, which a replay can feed).
- Time: OUT within the tolerance; exit at the original time. Interrupts off: a frame IRQ falling in
  the window is accounted, not lost, only if the game's ISR has effects then. Hook stack: 4 bytes;
  interrupt headroom: interrupts off: n/a.
- Display: software = return/boundary only; hardware = checklist item "same speed and beeper sound as the plain build"

## Resources owned
A page for the translated copy and its log; one CTC channel (polled); CW_X.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| First OUTs late | copy slower than the first deadline | timeline | lockstep in the copy | defer all |
| Constant offset | speed-switch cost differs on the machine | cw_cal | measure once at boot | simulator figure |
| Crash on hardware only | hooks under the stub register block | post-boot hook check | move hooks | - |

## Verification
Per state: registers, RAM, OUT values and T against the original. Negative controls: change
detection removed, a tile counter removed, a constant off by one.

## Evidence
- `grep -n '^cw_head\|^cw_wait\|^cw_irq\|^cw_cal' asm/inferno_hooks.asm`; nexclash/inferno.py
  cw_out_t / copier_window_checks.
- copier_window.md (observed in the simulator; hardware by ear).
