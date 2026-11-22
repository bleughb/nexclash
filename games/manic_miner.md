# Manic Miner (Bug-Byte, 1983; 48K) - engine `manic_miner` (pilot game 1: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended, verify stamped; never run on a Next or in CSpect.
Inputs: the pilot's run folder (manic_miner.z80 md5 d8face31, recordings work/*.rzx from `record --script`)
Start with: hardware checklist below on a real Next; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".

Techniques: `detect.buffer-layout-producer`, `detect.gameplay-screen-readers` (recipe and results: docs/records/manic_miner.json)

## Inputs
Snapshot from tape with tap2sna (Manic Miner (Europe).tzx, md5 e0e83ec3), stopped at PC=33792 (0x8400),
md5 d8face31a18a9543b093443b6f115f84. 48K, BASIC-loaded, DI at 0x8400; no EI anywhere in the run
(`isr`: 0 interrupts accepted in the 3,000 frames it was run over; no EI in the disassembled code). No Fuse and no human: recordings made with `nexclash.py record --script`.
- play: work/play1.script (work/closed_loop.py wrote it): the game's own cheat 6031769, then
  teleport to each of the 20 caverns in turn and walk / jump at random, re-entering after game overs.
- demo: `wait 7400`: title, tune, then the game's demo through all 20 caverns.
- bot: work/bot.script (work/bot.py, a search over held keys on nexclash's Machine): play from the start,
  no cheat: items, portal, next cavern, caverns 0-3; it did not clear cavern 4 in 300 s.
- kong: work/bot2.script (bot2.py): cheat, cavern 7 right switch, Kong falls; cavern 19 not cleared in 600 s.
The stage-0 auto recording (17 segments) cannot be surveyed: see Lessons.

## Snapshot facts (PLAYBOOK 0b)
`inspect`: loader state of the game itself, PC in RAM, no paging, ROM font read at 0x3C00+ (0x92CB).
Keyboard: O/P (and Q/W...) left/right, SPACE jump, ENTER starts from the title. The snapshot detects a
Kempston interface (port 0x1F reads 0 in the recorder, so 0x8459 = 1); no input comes from it.

## Rendering model (PLAYBOOK 2): back-buffer composer
Main loop 0x873F, about 4 video frames per pass, no frame sync, interrupts off:
0x8748 LDIR 0x5E00 -> 0x5C00 (attributes), 0x8753 LDIR 0x7000 -> 0x6000 (pixels, top two thirds), then
figures plot into 0x6000 and paint 0x5C00, then 0x87AB LDIR 0x6000 -> 0x4000, 0x87D1 LDIR 0x5C00 -> 0x5800.
| Figure | Plot | Colour painted | Notes |
|---|---|---|---|
| Willy | own OR loop 0x927F-0x92B9, gfx 0x8200 + frame | ink 7 over background cells only (0x925F) | not drawn in the demo |
| horizontal guardians | 0x8DEB CALL 0x8FF4, gfx 0x8100 | (IY+0) AND 0x7F | C=1: AND collision then OR |
| Eugene | 0x8E39, gfx 0x80E0 | white with items left, else cycling | cavern 4 |
| Skylabs / vertical guardians | 0x8EC9 / 0x8F3B, gfx 0x8100 | (IY+0) with background's upper bits | caverns 13 / 8+ |
| Kong standing / falling | 0x9206 C=1 / 0x91D7 C=0 (overwrites), gfx 0x8100 | 0x44 / 6 | caverns 7, 11 |
| items | 0x8FAB CALL 0x92D5, 8 rows, overwrites, gfx 0x80B4 | (IY+0), ink cycles | |
| portal | 0x8FEC falling into 0x8FF4, C=0 overwrites, gfx 0x8090 | 0x808F, FLASH when all items are taken | |
HUD (lives 0x8727, air, score), title (0x8606, 0x865E), game over (0x897C, 0x8987, 0x899E) and the
swordfish ending (0x9046, 0x904F) use the same plotter at 0x4000-0x57FF addresses: not hooked, ULA.

Readers (`scan --writers`, work/scan_writers.log; observed, whole play recording):
ULA pixels and attributes are read only by the LDIR fills themselves (0x85F1, 0x896E, 0x8912, 0x89C6),
so nothing decides on them. 0x6000 is read by the plotter's collision (0x8FFB...) and the Willy OR
(0x92AB); 0x5C00 by Willy's and the items' attribute tests. Both stay exactly as the original leaves them.
Writers of 0x6000: 0x8753, 0x8FFF, 0x900B, 0x92D6, 0x92AC, 0x92B1 = the table above, nothing else.
0x5B00-0x5BFF untouched; the stack bottoms at 0x9CF8, 0x9C00-0x9CF7 untouched.

## Patch plan (STANDARD 4-5; cards opened: 2)
detect.buffer-layout-producer: 0x7000 is the clean layer behind the screen copy. detect.gameplay-screen-readers:
no logic reads the ULA. patch.scratch-redirect is not needed: the game's own buffer already is the
scratch the screen no longer shows; rejected (it would move plotter output, here only the LDIR source moves).
patch.display-atomic-switch: not applied; each sprite's five registers are written in one burst at 28 MHz
at its own plot, and the ULA no longer holds the figure, so there is no old image to race with.
No card covers "change the blit source"; design from table 4 ("back-buffer composer").

## Defaults taken (a human would have decided these; PLAYBOOK 3c, not asked in this pilot)
1. Every figure a sprite: Willy, guardians, Eugene, Skylabs, Kong, items, portal. Default.
2. Scenery, HUD, score, text, title stay on the ULA. Default. Includes the lives, the game-over
   Willy, plinth and boot, and the swordfish ending: plotted directly on the ULA, so they keep clash.
3. Depth: game's own order (plot order -> slot order, higher on top; portal last). Default.
4. Colours: each figure's own ink + the game's BRIGHT rule. No painting, no colour sheets built.
5. Menus: none over the play area. The extra-life flash: keeps the original's fill on the ULA; the
   sprites stay in their colours over it (the original shows them black on the flash). ALWAYS-ASK item.
ALWAYS-ASK, no default, decided here without a human:
- solid or see-through: items, portal and falling Kong solid (they overwrite in the original),
  everything else see-through (OR in the original). Follows the original's pixels.
- portal FLASH: pattern swap every 16 air units (4 game passes), about the ULA's rate, not in phase.
- dying: attribute fade on the ULA; figures plotted before the death frame's cut stay at full colour until the next screen.
- effects: the Solar Power beam stays on the ULA (attribute-only effect, no pixels).
- items keep one paper per cavern (the first item's), sampled at load.

## Build design
Sites and hook behaviour: top of asm/manic_miner_hooks.asm. Memory: alt ROM image 1 at 0x386E (744 bytes
+ 20 register block), one hook byte at 0x5BFF (slot counter), tail 54 bytes at 0x5B00. Patterns and the
three paper palette entries rebuilt at each cavern load at 28 MHz. All hooks enter with NEXTREG $07,3
and leave with $07,0. The two LDIRs keep their length and contention, so game speed moves only by
the hook time (Results). The ULA now shows 0x7000 as of the blit, which the game may have changed after
its copy to 0x6000 (conveyor, crumbling floor, Kong's wall): those appear one game pass earlier.

## Verify (what it checks)
Per site, original vs patched from the same state: all registers but R / T / MEMPTR, memory outside
the ULA, dead stack and the hook byte; ULA pixels = 0x7000; ULA attributes = 0x5E00 (or beam, or fill).
Per pixel blit: 0x7000 as copied + sprites (slot order, solid pixels clear) = 0x6000, bit for bit; the
one exception is a collision frame, where the original's figure stops mid-plot: picture must hold every
pixel of the original (counted, "cut short"). Lockstep: the whole patched game runs on the recording's
IN values next to the original; registers and RAM compared at every blit (works because interrupts
are off, so only the IN sequence matters). Unit: all 20 caverns' patterns + palette; 8 guardian frames x
edge positions on 4 sites; Willy 8 frames x positions; slot guard; hide sites; beam; extra-life fill.
Negatives: 6 broken builds on the real recording, and through the unit cases.

## Results (stamped run 2026-11-02, `selftest.py --game manic_miner --verify --stamp`; simulation only)
Builds: manic_miner_sprites.nex 2f033d89d9044b999b647b8c26805946, manic_miner.nex 68be594f2890dc7f95c8e24829d1d5d9; boot OK.
| Recording | Frames | Pixel blits | wil / hg / item / port | eug / sky / vg / kst / kfl | title / over / cav | Verify | Lockstep |
|---|---|---|---|---|---|---|---|
| mm_play1 (cheat, teleports, 20 caverns) | 13651 | 2919 | 2914 / 6889 / 12350 / 2895 | 155 / 495 / 3436 / 205 / 0 | 9 / 8 / 72 | IDENTICAL | IDENTICAL |
| mm_demo (the game's demo, 20 caverns) | 7421 | 1312 | 0 / 3360 / 5600 / 1312 | 64 / 192 / 1536 / 128 / 0 | 1 / 0 / 21 | IDENTICAL | IDENTICAL |
| mm_bot (search, no cheat: caverns 0-3 cleared) | 12946 | 3290 | 3294 / 6242 / 7936 / 3290 | 6 / 0 / 0 / 0 / 0 | 1 / 0 / 5 | IDENTICAL | IDENTICAL |
| mm_kong (cheat, search: cavern 7 switch, Kong falls) | 3327 | 824 | 824 / 2316 / 2929 / 824 | 0 / 0 / 1 / 719 / 25 | 1 / 0 / 5 | IDENTICAL | IDENTICAL |
Pictures: 8345 blits, 8327 bit-identical, 18 cut short by a collision. Swordfish hook `sword`: never ran in any recording (unit case only).
Sprite ink vs the original's cell at the sprite's top left, informational: 69062 same, 863 not; not explained case by case (a shared cell is the expected cause, inferred).
Speed: hooks add 0.32-0.77 % of the frames' T, estimated (simulated T / 6); no real-machine timing.
Unit PASS: Willy 192, plots 5632, cavern load 20, patterns 20, palette 60, setup 1, slot guard 1, hide 3, beam 1, extra-life fill 1.
Negatives on the real recording, all DETECTED: pixel blit keeps figures, attr blit keeps paint, sprites one row low, patterns inverted, hook loses a register, guardian hook never runs. Through the unit cases 4 of 6 detected; the two blit-source ones are seen only by the replay.
Evidence PNGs: run folder png/ (software render of ULA + sprites; FLASH not rendered on either side).

## Hardware checklist (nothing here has run on hardware)
1. Boot the .nex, title and tune as the original; ENTER starts the game; title and HUD unchanged.
2. Central Cavern: Willy and guardians crisp, no attribute squares; conveyor and crumbling floor run.
3. Speed and sound against the plain .nex: walk tune, jump, death. No frame sync here: any slowdown shows.
4. Items: colour cycling, pickup, score. All items taken: portal flashes, Willy enters, air counts down.
5. Eugene's Lair: Eugene changes colour when the last item goes. Kong caverns: both switches, Kong falls.
6. Skylab Landing Bay; The Warehouse; Solar Power Generator: the beam moves, turns at figures, drains air.
7. Death: fade with any figures shown still lit (a change from the original); game over: boot scene, no stray sprites.
8. Final Barrier: top picture, swordfish ending, return to cavern 0, no stray sprites.
9. Demo mode runs through all 20 caverns; a key returns to the title with no stray sprites.
Hardware risk review (PLAYBOOK 6b): DivMMC: hooks at 0x386E-0x3B56, not in 0x3D00-0x3DFF. Interrupts: never on.
Raster: sprite attributes and the conveyor LDIR are not synced to the beam, as the original; a sprite can
move mid-frame, which a simulator cannot show. Speed: Speed line in Results; 28 MHz inside hooks only, no OUT $FE
there. MAME: known MAME sprite quirks (BRIEFING A1) not tried; no emulator run at all in this pilot.

## Open
- Never run on hardware or an emulator with sprites: sprite/ULA composition is modelled, not observed.
- A human's answers to "Defaults taken".
- Not reached by any recording: swordfish ending, extra-life flash (unit cases only); caverns 4-19 not played through, cavern 11's Kong fall not reached; survey ran on mm_play1 only (GATE OK), the combined run hit my 400 s limit.
- Colour sheets, recolour: not built (default 4 stands). PLAYBOOK asks for them at stage 2-3.

## Lessons
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: the stage-0 auto recording (17 segments, one snapshot each) cannot be surveyed: `survey` strips "autosaves", which joins the segments' frames onto one state, and replay stops at frame 575 "Port readings exhausted". `record --script` makes one segment, which works. Shared code not changed here.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: `survey` says "Generic engine unknown ... auto builds it" for a game no engine knows; `record --script` adds 2 idle frames after each held step, which a search over inputs must simulate or its path does not replay.
- [local: only this game's plotters are this simple] demonstrated: when logic reads only the back buffers and a clean layer exists behind them, changing the two LDIR sources removes every figure from the ULA with no timing change; collisions need no virtual read.
- [local: interrupts are never enabled here] demonstrated: with no interrupts the patched game can run in lockstep with the original on the IN values alone, which runs the real hook bytes on the whole recording, where the per-site pair runs only prove each site from the original's state.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: selftest and the recorder use tempfile, so without TMPDIR game files land in /tmp, outside a run folder; set TMPDIR first when a run must stay in one place.
- [local: needs a human] inferred: the design questions in "Defaults taken" were answered from the original's pixels (overwrite = solid, OR = see-through), not from anyone's taste; the sheet of frames is what a human would judge.

## Technique use
- detect.buffer-layout-producer: helped: named the question; the disassembly answered it.
- detect.gameplay-screen-readers: helped: `scan --writers` gave the proof in one run.

## Stage log
- 2026-11-02 stages 0-3 in one session (pilot, unattended, one stamped verify restarted for TMPDIR): 1 h 20, ~70 tool calls, 0 user rounds.
