# Castle Master (Incentive Software, 1990; 48K, Freescape) - stage 0 intake done, stage 1 question open

## Next session
Stage: 1 (design)            State: intake 2026-11-19; the design question is with the user (Pending below)
Inputs: C:\1NEXT\castle_master_work\castle_master.z80 (extracted from the RZX), C:\dev\castlemaster\castle.rzx,
C:\dev\castlemaster\Castlemaster1.tap    Branch: add-castle-master    Commit: (this file's commit)
Checks: survey --stop 15000 (castle_master_survey/), survey full run (survey_full/), scan of the view buffer (3,000 frames)
Pending user answers: none (goal + speed answered 2026-11-19, Decisions); design approval after feasibility
Start with: feasibility items (1)-(4) in Decisions, and the face-colour source (Feasibility, last bullet)
Read: PLAYBOOK stage 1 + 3d; cards detect.pacing-structure, detect.routine-removal, patch.hybrid-display-replacement
Open: who maps a face's colour to its dither pattern (the colour source for a colour route); unreached CALL sites (Coverage)

## Inputs
- Snapshot: the RZX's embedded .z80 (`nexclash.py rzx extract`), in game: 48K, PC 0xFDFD (RAM), IM 2 I=0xFE, vector
  0xFEFF -> 0xFDFD -> 0xC01F; handler DI / PUSH HL,BC,AF / SET 7,(29518). SP 0xFFEC. RAMTOP 32767. Border 0.
- Recording: castle.rzx, 1 segment, 167,134 frames (3,342.7 s), no autosave snapshots.
- Tape: Castlemaster1.tap = BASIC "CASTLE" (LINE 10), "CMT" CODE 32768,260 (loader), then three headerless blocks
  (6,914 / 36,098 / 6,914 bytes with flag 0, i.e. the turbo/custom loader's data); one 6,914-byte block may be the
  loading screen (not yet checked). Single load: no multiload files.

## Rendering model (survey, scan of the view buffer, first 3,000 / 15,000 frames)
| Stage | Code | Buffer |
|---|---|---|
| clear the view | 0xA502 (x158,996 writes in 3,000 frames) | 0x5CBC-0x673F (24 bytes x 112 lines, linear) |
| fill polygon spans (dither patterns, read-modify-write) | 0x9DC9-0x9DF8, 0x96F2-0x9731, ~105 routine spans 0x8637-0x8F0F | same |
| buffer to screen (LDI/unrolled block copy) | 0xA38D, called from 0x9F19 and 0xB62C | view x 32-223, y 32-143 |
| panel text / messages | 0xCA4E (17 call sites), 0xD028 | panel and message strip |
| area pictures / panel blocks | 0xB66E, attributes 0xB347 | |
The view's attributes are one ink/paper for the whole window per area (cyan, yellow, ... in the preview);
faces differ only by dither pattern. ISR at 0xC01F writes 65,856 attribute bytes (the flashing border towers /
panel) and uses LD A,R (49291, 49342); slots 1, 4, 5 never touched by it.

## Clash: kind D (one colour per area), none
No figures: everything in the view is the Freescape renderer's polygons. There is no colour clash to remove; a
Next version's gain would be colour (faces in their own colours), as with Quazatron.

## Decisions (user, 2026-11-19)
- Goal: colour the 3D view (faces in their own colours; Layer 2 presumably, panel on the ULA - design detail open).
- Speed: "utilise the Next's new hardware to dramatically speed up the rendering, without affecting the gameplay"
  = an owner-named faster pace for the renderer (patch.pace-limiter: not ORIGINAL). Constraint to settle in
  feasibility: what the game's movement / timers count (rendered frames or interrupts, 29518 bit 7 set by the ISR);
  if movement is per rendered frame, a faster renderer changes gameplay unless steps are scaled or the frame rate
  is capped - that answer goes back to the user before the design is approved.
- Speed, answered 2026-11-19: "Original pace, smooth view". Game updates keep the original's real-time rate
  (pace target ORIGINAL for game state); the time the faster renderer frees renders in-between camera positions
  (display only, never writes game state) so the view moves smoothly. Rejected by the user: faster updates
  (walk/turn faster in real time) and smaller steps (changes game logic).
  Feasibility must establish: (1) the camera state (position, yaw, pitch) and the step per update, so a tween can
  interpolate between the previous and the new camera; (2) that the renderer can run on a copy of that state
  without writing game memory (removal / isolation experiment); (3) the original's per-update real time to pace
  to (renders 2-52 frames: pace each update to its own original duration, card patch.pace-limiter); (4) the
  render cost at 28 MHz + Layer 2 + DMA, i.e. how many tween frames fit per update.

## Feasibility (PLAYBOOK 3d; first 15,000 frames)
- Pacing (card detect.pacing-structure, observed): no frame wait. Main loop body 0x8542 (callers 0x6A8C, 0x6A96,
  0x8519, 0xBD49) polls ~30x per frame (588 T) while nothing changes; on a change (move, turn, action) it runs the
  whole update + render: 0x8542 -> 0xBE03 (48643), 0x9EA3 (40611), 0x9F19 (40729 = buffer copy 0xA38D, 51,503 T).
  pacing_census --update 0x8542: renders take 2-52 frames (median ~16 = ~0.3 s, ~3 fps), one 151; 62.1 % of all
  frame time is inside 0x8542 (cost). Updates are event-driven, not frame-locked.
- Clocks (observed, ISR 0xC01F): 29559 counts down per interrupt; 49182 /120 -> 27408++; 27407 /10 -> 27411++;
  29518 bit 7 = "inside the ISR" (the printer 0xCC17 checks it before EI). Timers are real time, independent of
  render speed. The ISR also rewrites the view attributes 0x5884 (24 x 14 cells) from 27353 / table 49168
  (view flashes) - a colour design must follow those writes.
- Consequence for "faster without affecting gameplay" (inferred, to confirm by a removal experiment): one move or
  turn step per update. A faster render = more updates per second = faster walking and turning in real time,
  while the real-time clocks stay the same. Per-update game logic stays identical either way (same inputs per
  update -> same game); only the real-time feel changes. Options for the user (below, Pending).
- Sound: OUT 254 at 0xC821 (20,932, in 39 updates), 0xC117 (195), 0xB374 (16) - check which run inside render
  code before any speed-up (patch.timed-side-effect-replay).
- Colour source (observed, static code): span setup 0x9660-0x9686 sets (29662) = view line address
  (23740 + 24*line) and (29664) = 53825 + 4*((29501)-1): (29501) = the face's colour index 1-16, table 53825 = 16
  four-line dither patterns (1 empty, 2 and 11 solid, 3-10 / 12-16 dithers). Span filler ~0x969E-0x9731 reads
  (29664)+(line&3) (29658 = y), masked fill: CPL / AND (HL) / AND pattern / OR / LD (HL),A at 38633-38642, then
  whole bytes. 0x9682 is the only writer of 29664. A colour hook can take the index from (29501) per span and
  write it into a byte-per-pixel Layer 2 view: no reverse mapping from patterns needed. Which colour each index
  shows: the 16-bit versions' palettes or the user's choice (stage-1 colour question, later).
- Not the filler: 0x9DC9-0x9DF8 writes variables 24369-24382 that lie inside the view buffer's address range
  (geometry / clipping scratch, run when (29502) > 1); the scan range 0x5C80-0x673F mixed both.
- View buffer (observed): 0x5CBC-0x673B, 112 lines x 24 bytes, row table 28975; copied by 0xA38D (LDI x24 per
  line); 0xA502 clears it.

## Coverage (survey GATE, 15,000 frames)
Unreached CALL sites: 0xD028 (2/3), 0xCA4E (17/18), 0xB66E (2/6; 48357 not reached). All text / panel / area
pictures, no figure plotter. The full run (survey_full/) may reach them.

## Stage log
- 2026-11-19, stage 0 + 1 (feasibility started), ~70 min, ~45 tool calls, 2 user rounds: intake, survey 15k,
  goal + speed answered, pacing census, colour source found.

## Lessons
- [doc docs/RECORDING_CHECKLIST.md §Making a recording (Fuse)] An RZX alone (no separate .z80) is a complete intake: `nexclash.py rzx extract R -o
  GAME.z80` gives the snapshot it was recorded from (here a .tap came with it, not needed for a single load).
- [local: one game's misread; the survey reports what the copier reads] The survey's buffer range (0x5C80-0x673F, rounded) mixed the view buffer with renderer variables, so
  `scan --writers` on it listed geometry code first; the copier's own pointer (LD HL,23740 at 0xA39A) gave the
  exact buffer.

## Technique use
- detect.pacing-structure: helped: pacing_census on the main loop 0x8542 showed event-driven renders of 2-52
  frames and no frame wait, which set the speed question.

## Friction
- reuse: [tool tools/probes/pacing_census.py] used as it is; `nexclash.py cost` too
- retries: [local: the skoolkit helper first named dis.py shadowed the stdlib module `dis`; renamed]
- environment: [none: local Windows checkout, no workarounds needed]
- hand-rolled: [local: byte searches for CALL / LD (nn) sites with skoolkit's snapshot reader]
- scratch: [local: the disassembly helper stays in the session scratchpad; nothing added to the repo]
