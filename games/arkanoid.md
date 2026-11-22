# Arkanoid (Imagine, 1987; 48K) - engine `arkanoid` (pilot: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended, verify stamped; never run on a Next or in CSpect or JNext.
Inputs: pilot run folder: arkanoid.z80 md5 1f0faef5 (archive), recordings work/ark_*.rzx (work/bot.py, work/rec.py).
Start with: the owner's decision under "How much clash"; if yes, the hardware checklist.
Read: this file. Open: "Defaults taken", "How much clash", floating bus on the Next.

Techniques: `detect.gameplay-screen-readers` (recipe and results: docs/records/arkanoid.json)

## Inputs
Snapshot: Arkanoid (1987)(Imagine).z80 from the archive, ZXDB 0000255, md5 1f0faef52a701cfc9434e2745ccb7fc2. `inspect` warns "loader
snapshot" (PC in ROM PAUSE): a false alarm, the game is in RAM and runs its title from the first frame.
Controls (0x8449): left row FE (SHIFT..V), right row 7F (SPACE..B), fire A..G / ENTER..H, Kempston. Port 0x1F reads 0 in the
recorder, so Kempston is enabled at 0x8000 as on a machine with an idle Kempston. Any key: title -> score table; any key there -> story
-> game; no key for about 4100 frames -> attract demo (0x8155 rewrites CALL 0x8403), 100 frames, back.
No Fuse and no human: recordings by work/bot.py, closed loop on nexclash's Machine, keys only (the ball's X, capsules, the exit door):
- ark_play: no cheat, rounds 1-11, all 7 capsule kinds, 30001 frames.
- ark_r9, ark_r17, ark_r25: 6001 frames each; the game's continue flag and round counter poked at the title, before the RZX snapshot.
- ark_doh: round 33; also pokes 0x8259 (AND $3F) and the saved SP 0x94CA, then game over; 3001 frames. Not the normal way into Doh.
- ark_demo: keys and wait: attract demo, its exit with figures on screen.
Not reached: rounds 12-16, 19-24, 27-32 (same engine, level data only); beating Doh and the ending; high score name entry.
**Floating bus.** 0x848F, the main loop's beeper + frame wait, polls port 0x28FF: `IN A,(C): INC A: JR Z` until the bus is not 0xFF, then
until four 0xFF reads. `machine.py` answers 0xFF on that port, so `record` hangs there for ever at the first ball launch. work/arkm.py adds a
floating bus model (pixel / attribute by T state, 0xFF in border and between). Its timing is approximate: the main loop ran 1.48 passes per
recorded frame, so the recordings are right for logic but not for speed, and all percentages below are per main loop pass, not per TV frame.

## How much clash (owner's question, 2026-11-02: "no clash seen in JNext")
run folder work/arkanoid_clash.py, per main loop pass, each figure's ink pixels: the colour shown on the ULA against the figure's own (the
sprite's). Same hue but other BRIGHT counted apart. No cheat and cheat rounds together, not Doh: 70,997 passes.
| Figure | Passes shown | With wrong hue | Wrong hue pixels / ink pixels | Passes BRIGHT only |
|---|---|---|---|---|
| bat | 70,997 | 82 (0.12 %) | 0.04 % | 0 |
| ball | 70,866 | 4,641 (6.5 %) | 2.6 % | 15,516 (21.9 %) |
| alien | 40,166 | 1,666 (4.1 %) | 0.5 % | 27,324 (68.0 %) |
| capsule | 7,033 | 1,602 (22.8 %) | 16.2 % | 19 |
| laser | 3,074 | 101 (3.3 %) | 1.6 % | 599 (19.5 %) |
Any figure: hue changes in 7,760 passes (10.9 %), 21 pixels on average, of 49,152. Ball's wrong-hue passes: over a brick 2,597, in a cell a
capsule or alien painted 1,736, XOR hole 244, in the bat's rows 127. Capsule: over a brick 1,264 of 1,602.
Doh, on its own (cheat): 515 of 777 passes (66 %), 52 pixels on average: the bullets over his face.
BRIGHT only: 53 % of passes, 1.22M pixels: the original dims a figure in the bricks' and walls' shadow cells; the sprite stays BRIGHT.
That is a change a human may not want; it is arguably the game's own shading.
So the owner's view holds for a typical frame (png/typical_no_change.png: nothing changes in hue), and the design explains it: bricks and
empty cells share one paper, each figure keeps to its own cells, the ball is white on any paper. Clash exists at these moments only:
capsule crossing bricks (png/clash_capsule_over_brick.png), ball under a capsule (png/clash_ball_under_capsule.png), ball into a brick
(png/clash_ball_over_brick.png, 13 pixels), Doh's bullets (png/clash_doh_bullet_over_face.png). PNGs are the worst frames per cause,
picked by the tool: not representative. No colour or graphics option: no such word in the game's text in RAM (ASCII search); the front end has no menu: at the
title 38 of 40 keys tried do the same and SHIFT, SYM nothing; at the score table any key starts (0x820C, code read); "SPACE TO CHEAT" is the continue prompt.

## Rendering model (PLAYBOOK 2): XOR to the screen, game reads figure pixels
Main loop 0x83DF, frame locked by CALL 0x848F (beeper note + floating bus wait, DI). Draw: balls 0x93BA, aliens
0x87DB, capsule 0x8C18, bat 0x9B8D, laser 0x8CE2; wait 0x848F; erase: capsule 0x8BE3, aliens 0x88BE, balls 0x9420,
bat 0x9B4A. Everything XOR, graphics read with POP (SP in the graphics).
| Figure | Draw | Erase | Size | Colour in the original |
|---|---|---|---|---|
| ball x3 (IX 94F6 +0x11) | 0x93ED | 0x9444 (0x9420, 0x9429) | 2 x 5 rows | cell's ink (7 in empty cells) |
| bat | 0x9C71, big 0x9C04 | same code, entry 0x9B7D | 4 or 6 x 12 rows | paints rows 22 ink 5, 23 ink 0 |
| alien x3 (IX 9529 +0x10) + explosion | 0x888D, wide 0x87A0 | 0x8913, 0x8A47 | 2 or 3 x 11-16 rows | AND mask on cell ink (0x94CE), OR 7 at erase |
| capsule | 0x8C78 both ways, rows zig-zag | 0x8C0E | 2 x 8 rows | paints 0x94E8 unless a brick is in the cell |
| laser | 0x8DA3 | 0x8D39, 0x8D9D via 0x8A19 | 3 x 8 rows, zig-zag | cell's ink |
Readers: 0x8917/0x891F/0x8A4B.. an alien's erase ANDs its own pixels: any overlap = hit, so logic reads figure
pixels. Bricks and walls use the shadow attribute map 0x7800 and 0x7B00, the screen is not read for them.
Scenery XOR: 0x9367 brick shine. Non-XOR: exit door 0x8CBF, text 0x9D35, HUD. Doh (round 33): big ULA face, attribute
animation 0x9892, its bullets (0x9927).

## Patch plan (STANDARD 4-5; cards opened: 0)
Decision table row "Logic reads XOR-drawn figure pixels and the figures go in front" -> overlay, LEARNINGS 2.1d. No
ULA write changes, so game logic and memory stay the original's by construction. Stateless hooks, alt ROM.

## Defaults taken (a human would have decided these; PLAYBOOK 3c, not asked in this pilot)
1. Every figure a sprite: ball, bat, aliens, explosions, capsule, laser. Default.
2. Scenery, bricks, brick shine, HUD, text, exit door, Doh's face stay on the ULA. Default.
3. Depth: XOR has no depth; balls over laser over aliens over capsule over bat (slot order). Chosen.
4. Colours: figure's own (ball, laser ink 7; bat ink 5 / 0 by row; alien mask; capsule 0x94E8), level BRIGHT. Chosen.
5. Menus: none over the play area. Default.
ALWAYS-ASK items decided without a human: see-through (XOR figures have no solid part): pixels only. Effects: explosion
is a sprite in yellow (the original's mask 0xFE). Doh's bullets are aliens to the engine, so sprites too. BRIGHT: level BRIGHT, not the
cell's (see "How much clash"). Colour sheets and recolour: not built (a figure has one colour).
Attribute paint of the figures is kept (the overlay keeps every write): paper never changes (0x94E8 = level attribute + ink, 0x9261), and
ink only touches cells with no other pixels, except Doh's face under a bullet (repainted each pass by 0x9892; inferred, not measured).

## Build design
Sites: asm/arkanoid_hooks.asm header, nexclash/arkanoid.py SITES. Memory: alt ROM image 1 at 0x386E (hooks 1059 bytes);
no RAM but dead stack (28 bytes below SP; 0x5E40-0x5EB5 proven unused); tail at 0x5B00. Patterns are uploaded at each
plot from the game's own pointer at 28 MHz (rows only).
Verify: per site, original and patched from one state to the common resume point, all registers but R/T/MEMPTR, all memory
but dead stack. Figures: the game's own XOR writes followed by PC per class (parity), compared with the XOR of the class's sprites' ink
pixels at every 0x848F entry and every main loop head; writer PCs in WRITERS. Parity per class, not per IX: Disrupt's copy makes one ball's
erase run three times. R is not compared: 0x89C5 uses LD A,R for a bounce, so the patched game's random stream differs from the original's. Unit: every plot kind x graphics x positions, original XOR
against sprites; hide sites. Negatives: 8 broken builds on the real recording.

## Results
Stamped run 2026-11-02, `selftest.py --game arkanoid --verify --stamp`, simulation only; report: run folder out/verified/arkanoid_report.txt.
Builds: arkanoid_sprites.nex 5c95f67d4485c1c925397885f9b21062, arkanoid.nex dd1b36091dae5a99dd6a388b0e12b844; boot OK.
| Recording | Frames | Sprite pixels compared | Verify |
|---|---|---|---|
| ark_play (no cheat, rounds 1-11) | 30001 | 13,646,886 | IDENTICAL |
| ark_r9 / ark_r17 / ark_r25 | 6001 each | 2,962,317 / 2,787,945 / 2,952,124 | IDENTICAL |
| ark_doh | 3001 | 214,829 | IDENTICAL |
| ark_demo | 4438 | 0 (one pass, exits at once: see below) | IDENTICAL |
Hooks, all recordings: ball 76685, balls off 71591, ball off 29, bat 68312, big bat 3513, bat off 71812, alien 69721, wide alien 31029, alien off 100741, capsule 7103, capsule off 7103, laser 3074, laser off 3058, laser off 2 16, front end 8, wipe 17. Never ran: none.
Unit PASS: ball 56, bat 80, big bat 80, alien 96, wide alien 96, capsule 84, laser 20, 8 hide sites.
Negatives on ark_play, all DETECTED: sprites one row low; ink lost in upload; ball draw hook sets no sprite; ball erase leaves a ball shown; wipe leaves sprites; hook loses DE; displaced store lost; alien site not applied.
Speed: hooks add 11,754 to 13,323 T per frame at 3.5 MHz, estimated (28 MHz T / 6), 17-19 % of a frame; unmeasured on a machine and could drop frames.
Attract demo: 0x8DC6 leaves the demo when NO key is held, so with no key it runs one pass; held, the bat follows the ball (code read, not recorded).

## Hardware checklist (nothing here has run on hardware or an emulator)
1. FIRST the plain .nex: launch the ball. If the Next's port 0xFF floating bus reads constant 0xFF here, the game hangs at 0x848F, as the
   toolkit's recorder did. The whole game depends on it, sprites or not. Then speed and tune against a real Spectrum.
2. Sprite .nex: ball, bat, big bat, aliens, capsule, laser sit exactly on the figures, no fringe; explosion yellow.
3. Speed: hooks cost about 11,000 T per frame (estimate, T / 6) against a loop that waits for the end of the display: any dropped frame shows here.
4. Round clear, door exit, life lost, game over: no stray sprite on the next screen. Attract demo and its exit.
5. Doh: bullets over the face stay green.
Hardware risk review (PLAYBOOK 6b): DivMMC: hooks 0x386E-0x3C91, not in 0x3D00-0x3DFF. Interrupts: on at only one hook event (0x8025 from
the title), hook keeps SP on the stack and IX/IY/I. Raster: sprites change where the figures are redrawn, after the wait, as the ULA does;
tearing unmeasured. Emulator differences: floating bus above.

## Open
- Owner: is this small clash worth a sprite build with its hook cost? BRIGHT: keep the game's dimming in shadow cells or not?
- Next's floating bus on port 0xFF; real speed; a human recording; rounds and endings listed under Inputs.

## Lessons
- [local: guard every displaced byte] apply() checked 3 bytes at sites that displace 4-6 (LD (nn),SP at 0x93E7, the
  5-byte run at 0x9420): DISPLACED now holds each site's full span (Codex, 2026-11-22). Outputs unchanged.
- [deferred Open: reconsider when a maintainer reviews the pilot] demonstrated: a game that polls the floating bus hangs `record`, `survey` and every free run (machine.py returns 0xFF on odd ports). Add a floating bus to Machine; nothing in docs/ mentions it. Workaround: work/arkm.py.
- [deferred Open: reconsider when a maintainer reviews the pilot] inferred: 0x848F makes the Next's floating bus load-bearing for this game; unverified, first item of the checklist.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: routine attribution called the main XOR plotters "top": they are inline after SP moves; `scan --writers` and the disassembly found them. `inspect` warned "loader snapshot" for a snapshot running its title.
- [deferred Open: reconsider when a maintainer reviews the pilot] demonstrated: measure the clash before building. On this game the owner had to ask; the count here reuses the verify's replay, so it took about 20 min once the hooks existed. A cheaper count from the XOR writes alone should fit stage 1 (not tried). Candidate step: "is there clash to remove?" with this number in the design question.
- [local: only XOR overlays have such a parity check] demonstrated: an overlay needs no model of the ULA: one independent parity check on the game's XOR writes caught the Disrupt case and every pixel negative.
- [local: this verify's compare points] observed: checking figures only after the redraw missed "sprite left on after erase": 2 of 8 negatives until the loop head was compared too.
- [deferred Open: reconsider when a maintainer reviews the pilot] inferred: 11,000 T per frame is large for what it buys; a pattern cache would cut the bat's uploads. Not done, given the small gain.

## Technique use
- detect.gameplay-screen-readers: helped: named the question; `scan --writers` + disassembly found the alien erase test.

## Friction

- reuse: [none: a landing, no new code] Files from the add-arkanoid branch (460a719).
- retries: [local: the record named the pre-automap build] The branch predated the automap-off start, so its record's sprite MD5 was 1.0's; the rebuild is 1.0 plus that start, which nxc 1.1 now ships.
- environment: [none: no workaround]
- hand-rolled: [none: selftest --verify --stamp]
- scratch: [local: two probes dropped] arkanoid_arcade_paint.py and arkanoid_figs.py had no docstring contract or smoke test. The arcade map (arkanoid_arcade_colours.json) stays out of the repo: its
  ink bits rebuild the game's graphics bytes (Codex, 2026-11-22), so it is a local reference input like Spec256 maps.

## Stage log
- 2026-11-02 stages 0-3 in one session (pilot, unattended): about 1 h 10, ~55 tool calls, 0 user rounds, 1 coordinator question.
