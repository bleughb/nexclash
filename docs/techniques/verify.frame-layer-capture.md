# Capture every video frame's sprite layer and ULA to find in-between pictures

```json
{
  "schema": 4,
  "id": "verify.frame-layer-capture",
  "revision": 1,
  "kind": "verify",
  "title": "Capture every video frame's sprite layer and ULA to find in-between pictures",
  "question": "Does any video frame show the new sprites over the old screen, a figure missing, or a cell colour for one frame only?",
  "tags": ["verification", "flicker", "display", "sprites", "jnext"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": [],
  "order": {},
  "owns": {},
  "examples": [],
  "sources": ["pilot runs/nightshade work/blinkrun.sh, blinkstats.py, games/nightshade.md Round 3 (Jon's evidence, 2026-11-04)",
              "pilot runs/leonis_triage work/attrblink.py (Atic Atac door flicker)"]
}
```

## Use / do not use
Use on every build the user tests that switches sprites at a commit point or keeps figure cells on the ULA
(PLAYBOOK 6b): the differential verifiers compare state at hook returns and frame ends, so they pass a build
whose picture is wrong BETWEEN two such points. `python -m nexclash.flicker BUILD --original ORIG --from F`
(docs/CHECKS.md). It complements patch.display-atomic-switch: that card says how to switch; this checks the
switch on screen. Not a proof of hardware timing.

**Assumptions.** JNext draws the picture as the beam passes and saves the machine at the frame edge; the
sprite layer is rendered from the saved attributes and patterns (pixel-exact against JNext's own picture);
one address runs once per game update (for the changes-per-update line).

**Validation gap.** One game (Nightshade): the round-2 blink build and the round-3 fix, one walk of 300
frames. Layer 2 and the tilemap are not modelled; a figure that moves fast across a box edge can hide a
vanish.

## Recognise
- The owner says "blinky", "flashes", "ghost legs"; a figure looks merged with its last pose.
- An engine switches all sprites at one point while the game draws the ULA later (or the reverse).

## Probe and stop
1. Capture the frames where figures animate (`--from`, `--frames`); the original as control.
2. State level: the sprite layer changed and the ULA cells under the figures change on the next frame
   (or the reverse). Kept only when SEEN: the picture in the figures' box changed on two frames running.
3. Vanished: a figure of frame n-1 absent at n and back at n+1, also seen in the picture.
4. Changes per game update above the original's: in-between pictures on screen.
Stop when every flag is gone or explained in games/<game>.md.

## Contract
- Output: out-of-step frames (sprites first / ULA first), vanished figures, picture changes per update
  against the original, attribute cells changed for one frame and back, a strip of flagged frames.
- Frame-edge-only mismatches (a switch finished before the beam reached the figures) are counted, not flagged.

## Resources owned
None.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| sprites first, merged blob | commit before the game's blits | the commit's beam line | blits first, then the attribute burst | slower blits |
| vanished figure | hide at entry, show at exit | the hook order | switch, never hide | ignoring one frame |
| attribute one frame | a kept writer resets the cells a figure leaves | write log on the cells | redirect that writer | sprite timing |

## Verification
Negative control: Nightshade a94ebbb5 (blink) must flag (6 out of step, 2 vanished, 2.62 changes a game
update against the original's 1.12); 1cf6b276 (fixed) must not (0, 0, 1.00). Synthetic cases: `selftest.py --tools`.

## Evidence
- docs/CHECKS.md "flicker" (both runs' result blocks).
- `grep -n 'def analyse\|def seen' nexclash/flicker.py`.
