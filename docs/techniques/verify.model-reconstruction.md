# Rebuild the original screen from the model, every event

```json
{
  "schema": 4,
  "id": "verify.model-reconstruction",
  "revision": 1,
  "kind": "verify",
  "title": "Rebuild the original screen from the model, every event",
  "question": "Does the verifier's model of what the figures drew explain the original screen exactly?",
  "tags": ["verification", "model", "screen", "unknown-writers"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": ["nemesis_the_warlock"],
  "sources": []
}
```

## Use / do not use
A verifier that checks the patched screen against a model (background + figures) can pass when the
model and the hook share a wrong assumption: both forget a writer. Close the loop at every event:
rebuild the ORIGINAL screen from the model (background, then each figure's writes in order, then
any modelled effect) and require it to equal what the original actually drew. Use it with every
overlay / save-under / shadow design; it is cheap (the model is already computed).

**Assumptions.** The original's screen after the event is available in the replay; the model
lists every writer it claims to cover.

**Validation gap.** One game (Nemesis); the check finds unmodelled writers inside figure areas only
when they change a byte the model predicts.

## Recognise
Failures reading "original != background + figures": a byte the model cannot explain. The XOR of
original and model is a clue (Nemesis: 0x5A = an XOR-90 effect at 0x89F9; three bytes on the left
edge = a figure wrapping past column 31).

## Probe and stop
1. On the first failure print the event's figure list and the differing addresses (original vs model).
2. Find the writer: `scan --range BUF --writers` on the buffer, or the XOR value's instruction.
3. Model it (an event in the hook's log, or a rule like "wrapped bytes stay on the ULA"), rerun.
Stop when a 20000-frame run has no model failure (PLAYBOOK 6).

## Contract
- Output: per event, model == original screen, or the differing bytes.
- It checks the MODEL; the hook is checked separately against the model (patched ULA = expected
  background, sprites = expected layer).

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| model != original, XOR 0x5A | an XOR effect under a figure | the XOR writer | log it as an event | excluding the bytes from the check |
| model != original at the left edge | figure past column 31 wraps | figure column | leave wrapped bytes on the ULA | sprites there |
| model != original, save-under in ROM | permanent stamp | the plot caller's IY | treat as scenery | a sprite |

## Verification
Negative control: drop one modelled writer (an event kind) from the model; the check must fail on
a recording that reaches it.

## Evidence
- games/nemesis_the_warlock.md "Engine", "Results" (quick 20000 found two cases 2000 missed; observed).
- `grep -n 'def expected\|def copy_event' nexclash/nemesis.py` (the comp check).
