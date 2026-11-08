# Game Over (Imagine / Dinamic, 1987, 128K, both worlds)

## Next session
Stage: 3 (prove + deliver)   State: private review build for the owner, nothing upstream yet
Inputs: Game Over (1987)(Imagine)(128K)[re-release].z80, MD5 e1c2ff3cfbd4f6f5a84034d57b666acf
Checks: replay, ABI, negatives, pace, soak, flicker, beam audit, real loader in the run's NOTES.md
Pending: owner plays; Enhanced mock-up approval; then `auto`, the record and registration for upstream.

## Facts
- A true 128K release: AY music from the ISR (no beeper), world 1 code stored in bank 4 (offset +0x5C6), world 2 in bank 6; a swap copies it into 0x8000+. So sites go in the live code and both images. World 2 drawing sites are world 1's +0x28.
- Rendering model: back-buffer composer. Clean bitmap 5DC0, attributes 6AE0; work bitmap 6CA0 (112 rows x 30), attributes 79C0; restore then plots then copy (AF4B / AF73 entries). Screen RAM is never read by the game (only the CLS LDIR).
- Clash: B47E paints a figure's whole box in the work attributes, ink only: scenery in the box changes colour (2-3% of scenery pixels). B47E = RET: plots that do not paint (pillars in front).

## Decision
The owner's standard: the original look with colour clash removed. No figures on sprites: plots overlap in the game's own order, and scenery is drawn over them.
- ULA bitmap = the original's, every byte. Attributes shown = the clean buffer (one operand at the copy).
- Layer 2 overlay (double buffered, published with the copy, below the play area): each painting plot writes its ink pixels in the figure's colour and index 254 (also transparent) on opaque mask pixels; a non-painting plot punches. AF06's attribute block (the barrel) recolours 254 to its paper and ink to its ink.
- Original plot, restore and copy bodies run whole at 28 MHz in K windows (hlib_pace) which pay for the overlay; hlib interrupt time in a window is waited out (isr_extra) so the beat with the frame does not move the pace.
- CPU clear, no DMA: interrupts stay on (AY tempo) and a DMA burst can lose an /INT; the budget is ample.

## Technique use
patch.pace-limiter, patch.preserve-r, patch.restore-speed, patch.whole-altrom-image, patch.display-atomic-switch, verify.update-locked-pace.

## Lessons
- local: a test-only fixture (BA58 INC HL -> NOP, the ISR's RND seed step) gives lockstep pace runs.
- doc: a pace window with interrupts on saves the handler's time; FRAMES counts them.
