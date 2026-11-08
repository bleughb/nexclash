# Mad Mix 2 - en el Castillo de los Fantasmas (Topo Soft, 1990, 128K)

## Next session
Stage: 3 (prove + deliver)   State: private review build for the owner, nothing upstream yet
Inputs: Mad Mix 2 - en el Castillo de los Fantasmas (1990)(Topo Soft)(128K)(ES).z80, MD5 f5f5262f7a41d3c55408b45878c31d00
Checks: replay, unit, negatives, pace, soak, flicker, real loader in the run's NOTES.md
Pending: owner plays, default and Enhanced; colours for stages 4 to 9 need new paint (a later mock-up); then `auto`, the record and registration for upstream.

## Facts
- A true 128K release: flag 0x6001 = 1, AY music in bank 1 (7FFD 0x11 in the handler), nine stages, three stage groups swapped in from banks 3 and 4 through the screen (5DDC). The Spanish tape messages (5DAB, 5DC6, DA98) are the 48K path and are never printed here. All other text is English: READY, OK, SCORE, STAGE, GAME OVER, PRESS FIRE TO START.
- Rendering: the main loop builds a back buffer (bank 0, DB04), the handler copies it with LDI (ABC8) after a delay LDIR, attributes first (one attribute per stage, 8E7B).
- The copy writes 2 then 3 to port 0xFF (ABEF, AC43). On a 128K that decodes to nothing. In a Next .nex it is the Timex screen mode: hi-colour, a scrambled picture (seen in JNext); through NextZXOS's own snapshot loader, the fix line off, the original shows correctly (seen in JNext). The Spec256 snapshot has the same writes.
- Random numbers: LD A,R (9735, 9972, 9A27, 9E74, AA46), and AA4A XORs in ROM bytes 0000-015F. NextZXOS ROM3 differs from Sinclair's in 28 of those bytes: hence the whole alt ROM.
- Keys in the snapshot: table 6003 = T fire, R up, C down, D left, F right; 600D P pause; V music on or off (AA97). Mode byte 6000: 0 keyboard, 1 Interface 2, 2 Kempston, 3 a fixed table.
- Waits: 93A5 waits for all keys up and then one down (READY, OK, STAGE). A script must leave gaps between keys.

## Decision
No clash to remove: the play area is one colour a stage. No figure outline: each figure has its own black edge and white fill. Both port 0xFF writes become IN A,(0xFF): same bytes, T and R; A is reloaded before it is read. No hooks, so no hlib code, no DMA and nothing to prove at a hook but the two sites.

## Enhanced
The owner's rule (2026-11-08): no mock-up or approval to convert a Spec256 set. The set holds stage group 1 only, so Enhanced is stages 1 to 3, the set's colours as they are, a menu option, off by default; the default build's bytes are unchanged. Stages 4 to 9, the menus, STAGE and game over screens stay in the original's colours: Layer 2 is off there.
- The whole picture is on Layer 2, double buffered. The game still builds its 1-bit back buffer and copies it to the ULA, byte for byte, hidden under the opaque window. After each piece (tiles AC46, stars B02A, figures A58B) the same piece goes on the Layer 2 back buffer. Tables by `nexclash/mad_mix_2_art.py`, kept beside the snapshot, never here.
- The Layer 2 index is the set's own value, so a star's inverse is a CPL. The set's v = 0xFF is the plain Spectrum pixel by the master bit: palette entries 253 and 254, kept to the stage's attribute at the flip. Masks in the set are all or nothing; 828 figure pixels are drawn with a graphic over an open mask, which the set ORs with what is below, and here simply draw.
- Text and lives: the set's font and life on Layer 2 as the game prints them (A8F9, 9157). In the window only on the shown buffer, the next flip takes it away; the font's plain pixels are transparent, so the READY box's blue comes through from the screen's own attributes.
- Colours read through slot 0, Layer 2 written through 0x123B's write map, so no game memory is paged out and interrupts stay on. Nothing writes below 0x4000 while the map is on, and SP stays in the game's stack. The map is on only inside one block of code (draw_a..draw_b): the handler's wrapper turns it off, and back on only if it interrupted that block.
- The handler is wrapped (A548, A584): game clock, hold / resume, R as the original. It writes 0x7FFD, so its exit puts slots 0 and 1 back.
- Windows wait out each routine's exact T states at 3.5 MHz, from the replays by path and rows, not a K: pace is within 0.1%.

## Technique use
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM; the game takes random numbers from ROM bytes.
- verify.update-locked-pace: used: lockstep pace runs on the test fixture.

## Lessons
- [local: port 0xFF] A 128K game can write port 0xFF for no reason a 128K sees; on a Next that is Timex hi-colour and a scrambled picture. Found by looking at the plain conversion's JNext screen, not by any check. Grep OUT (0xFF) in a plain conversion before designing.
- [local: nfo words] The .nfo tool words every patch as a clash fix with sprites or layers. This game has no clash, so the review run edits its .nfo after the tool; the tool wants a no-clash case.
- [local: helper name] A helper named dis.py in the working folder shadows the standard library's and breaks PIL's PNG import.
- [local: fixture] Pace fixture: R out of the random numbers, no key waits (93A5, A7FE), lives do not fall. Input changes only at updates, so a wait for input never ends.
- [local: Spec256] The Spec256 snapshot has the same port 0xFF writes; what they do there was not tested.
- [local: fix off] The note first said the fix line off scrambles the picture; the real loader showed the OS loader runs the original correctly. Test a claim about the off path before writing it.
- [local: exact times] A K window was wrong in both directions here: K is a ratio of body time, and the body's clock ratio differs by path (LDI heavy against register heavy). Replays give the original routines' exact T by path; waiting those out gave +0.1% against +-5%, and needs no tuning per emulator. Prefer it wherever the time is a simple function of the arguments.
- [local: a debt window across a frame] The picture takes over a frame in the shifted path. hlib_nest_open..close across a frame wrap loses 311 lines, so the wait ran a frame long, and K tuning hid it (K 48 looked right). The library says tick at least once a frame; col_tiles calls hlib_debt_tick each band.
- [local: flip timing] The copy ends with the beam in the window's upper rows, so a flip there tears. The audit showed it, not the arithmetic. It goes at the copy's start, beam below the window, and the opaque picture hides the copy.
- [local: z80n writes] The simulator's LDIX family dropped writes below 0x4000, so the write map showed nothing in the verifier though JNext was right. sim.low_writes lets a model that handles the map see them.
- [local: a model catches refactors] An MMU line lost in a refactor showed at once as a picture against the model, where the eye would have taken a while.

## Friction
- reuse: [none: the Game Over run's packaging and loader scripts were enough]
- retries: [local: key gaps] The first scripts held keys through the READY wait, which wants all keys up first; a stage fixture looked stuck until the script left gaps.
- environment: [none: the pilot venv and references were enough]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.
