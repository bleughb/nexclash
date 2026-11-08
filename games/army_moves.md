# Army Moves (Imagine / Dinamic, 1987, 128K, both parts)

## Next session
Stage: 3 (prove + deliver)   State: private review build for the owner, nothing upstream yet
Inputs: Army Moves (1987)(Imagine)(128K)[re-release].z80, MD5 9c14e2564e3f9956ff6ff973dac77537
Checks: replay, ABI, negatives, pace, soak, flicker, beam audit, real loader in the run's NOTES.md
Pending: owner plays; Enhanced mock-up approval; then `auto`, the record and registration for upstream.

## Facts
- A true 128K release: AY music from the ISR, part 1 code in bank 4 (offset +0x6A0), part 2 in bank 6, up to 0xA1FE; the plotter above that is never swapped.
- Same library as Game Over. Clean bitmap 6B90, attributes 77C0; work bitmap 5DC0 (104 rows x 30), attributes 69F0.
- Clash: A36C = RET in most plots: figures take the cell's ink (the jeep goes red over the bridge, jets blue over the sea); painted plots (A36C = FD) change scenery around them.

## Decision
As Game Over: original bitmap on the ULA, clean attributes, ordered double-buffered Layer 2 ink. New here: an unpainted part 1 figure (graphics C000..D3FF) draws in the sky's ink, the colour it has in the open; unpainted scenery plots (clouds, mountains, islands) and part 2's unpainted items punch.
The copy's DE at return differs (attributes last): the hook restores it. Direct screen clears (BA84, with HL on the screen) and the clean picture copy (A460) hide the overlay.

## Technique use
patch.pace-limiter, patch.preserve-r, patch.restore-speed, patch.whole-altrom-image, patch.display-atomic-switch, verify.update-locked-pace.
