# Hard Drivin' (Domark / Binary Design, 1989; 128K tape)

## Next session
Stage: 2 (build)             State: route chosen 2026-11-22 (Decision); feasibility recorded; build not started
Inputs: C:\1NEXT\harddrivin_work: hard_drivin.z80 (snapshot 0 of hard_drivin.rzx), hard_drivin.rzx (MD5 c649e04c, 22,116 frames), in\hd.tap (MD5 02e1f96c), in\hd.tzx (61f7d04c), in\hd.dsk ([a], 43a6bc4c). Game data: never in this repo.
Branch: add-hard-drivin (worktree C:\1NEXT\nexclash-hd)    Commit: see git log
Checks: survey (15,001 frames), plain .nex boots in JNext to the options menu (MD5 5b37afa4, --tail 0x6C00)
Pending user answers: none
Start with: "## Design"; find the matrix builder (writers of 43362-43399), then the pace window (games/castle_master.md M3a, asm/lib/hlib_pace.asm)
Open: sound in play; EI points in the loop; the CALL at 0xA402 (time-out path, not in the recording)

## Facts
- Tape (.tap = .tzx data): BASIC `HD 128K`, code 100 bytes at 30000, 5,000 at 32960, 200 at 43616, BASIC `-`, then one 41,400-byte block at 24000. Single load, no multiload.
- Snapshot: 128K, 7FFD 0x13 (ROM 1, bank 3 at C000), IM 2, I = 0xC1, vector table 0xC100 -> handler 0xC0C0 (CALL 0xC261 / EI / RET), SP 0xFFFA. Starts on the title screen.
- Interrupts mostly off in play: 742 accepted in 15,001 frames. The handler pages 7FFD (0xCD87/0xCD8A), uses EXX and AF'.
- 3D view: drawn into a back buffer at 0x8000-0x8FFF (write-first), copied to the screen's top 4K (0x4000-0x4FFF) by 0xDC45 (called from 0xDC37; 1,057 copies in 15,001 frames = one view every ~14 frames, ~3.5 a second). Dashboard needles and lamps: 0xE3AF / 0xE3D6 (16-byte plots), attributes 0xF228 / 0xF219.
- Look: the view is monochrome green (ink/paper attributes), the dashboard in fixed colours. No figure clash of the usual kind.
- Plain conversion: the survey's automatic tail fails (SP in the top 16K); `convert --tail 0x6C00` works: 0x6B53-0x6D5F untouched over all 22,116 frames.
- Options menu: 1 keyboard, 2 Kempston, 3 Fuller, 4 Interface 2, 5 cursor; SPACE centres steering, 0 aborts replay or off-road.

## Decision (user, 2026-11-22)
- Route: "Smoother 3D view" (Castle Master's M3 route): updates keep the original's real-time rate (pace
  ORIGINAL, per update); the renderer runs at 28 MHz and the freed time draws in-between views (display only).
  Rejected: plain only. Not now: coloured scenery (a later switchable extra).

## Feasibility (PLAYBOOK 3d; probes in C:\1NEXT\harddrivin_work\tools, first 3,000-6,000 frames)
- Pacing (card detect.pacing-structure, observed): no frame wait; DI for most of play. Main loop 0x9E34
  (body to 0x9E88, JR back at 0x9E32): one update = logic + render 0x9EA9 (from 0x9E54) + clock 0xA38A (from
  0x9E5E) + view copy 0xDC37 (from 0x9E6B). Update time 7-21 frames (median 13, mean 13.6): busy scenes run
  slower in game time, as in the original.
- Clocks: lap clock 0xA38A counts 5 updates per clock second (38155 to 5, BCD seconds 38156, minutes 38157);
  no real-time clock. ISR 0xC261 (IM 2, CALL from 0xC0C0) is sound only (vars 0xC2CA-0xC2CF, CALLs
  0xCE1B / 0xCEA3; bank 3 at C000 for the music, bank 0 = main code). So a faster update = a faster game:
  the update's original time must be kept.
- Cost per update (loopprof.py, 229 updates): 0x9EA9 87.3 % (845k T), view copy 0xDC37 6.4 % (62k T), the rest
  ~6 % (0xF910 3.3 %, 0xA423 1.3 %, 0xF476 0.9 %). Inside 0x9EA9 (treeprof.py): 0xD50B/0xD548 31 %, 0xD862 15 %,
  0xD9B4 11 %, 0xD584 8 %, 0xDBBE 4 %, maths 0xC7C0 / 0xDA4C: transform, clip, fill. Object list walked with
  SP from (38539); objects clipped against the camera 43400/43402/43404.
- Camera (camlog.py at each 0x9EA9): x, y, z = 16-bit at 43400, 43402, 43404; orientation 3 bytes at
  43407-43409 (copied to 43339-43341 by 0x9EA9); per-update matrix / view block 43362-43399 (0x9EA9 copies
  43362-43370 to 43371-43379). Which routine builds the matrix: open (stage 2).
- Render consumers (consumers.py, 2,500 frames; window 0x9EA9 .. 0x9E57, screen and back buffer excluded):
  23 addresses read later by logic: 43373-43379 (camera copy, read by 0xA6FF-0xA8AB), 0x918E (read 0xA47E /
  0xA4FB, written 0xEA48), 0x91CC-0x91CD, 0x951E (0xA353, 0xF4A9, 0xA71B), list 0xF02C-0xF03B (0xA48D-0xA496,
  written 0xEA46). In-between renders must leave these as the real render leaves them: the real render runs
  last, and these bytes are saved / restored around the extra ones; the differential test proves game RAM.
- Back buffer 0x8000-0x8FFF (4K, write-first) -> screen 0x4000-0x4FFF by 0xDC45 (SP copy). DMA candidate:
  the view copy only (docs/DDMA.md: zxnDMA / DDMA, core gated, plain fallback) - to measure in stage 2.
- Open: sound in play (engine / crash sound: OUT sites, AY from the ISR only?); interrupt windows in the loop
  (EI points) must stay at the original's times so the music tempo holds.

## Design (proposed, stage 2)
- Hooks: the render + copy block 0x9E54 .. 0x9E6E runs at 28 MHz inside a pace window (hlib_pace, as Castle
  Master M3a); window target = the original's time for this update (K x 28 MHz time, measured).
- In-between views: camera linear from the last shown view to the new one (positions; orientation by angle,
  matrix rebuilt by the game's own routine), drawn while they fit before the target; the real view last, shown
  at the original's time. Consumer bytes above saved / restored around each extra render.
- Display: views double-buffered (Layer 2 or a second ULA bank, to decide; the original look kept: green
  monochrome view, dashboard unchanged).
- Verify: RZX replay, game RAM + registers (R excepted per patch.preserve-r decision) = original at every
  update; pace per update vs the original (verify.update-locked-pace); mutants for the save / restore.

## Stage log
- 2026-11-22: stage 0 (intake) + stage 1 (route choice, feasibility), ~50 tool calls, 1 user round.
