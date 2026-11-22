# Hard Drivin' (Domark / Binary Design, 1989; 128K tape)

## Next session
Stage: 1 (design)            State: intake done 2026-11-22; design question put to the user, no answer yet
Inputs: C:\1NEXT\harddrivin_work: hard_drivin.z80 (snapshot 0 of hard_drivin.rzx), hard_drivin.rzx (MD5 c649e04c, 22,116 frames), in\hd.tap (MD5 02e1f96c), in\hd.tzx (61f7d04c), in\hd.dsk ([a], 43a6bc4c). Game data: never in this repo.
Branch: add-hard-drivin (worktree C:\1NEXT\nexclash-hd)    Commit: see git log
Checks: survey (15,001 frames), plain .nex boots in JNext to the options menu (MD5 5b37afa4, --tail 0x6C00)
Pending user answers: the stage-1 design question (Decision below)
Start with: read "## Decision", then PLAYBOOK 3d (feasibility: pacing) for the chosen route
Open: pacing structure (does game time follow updates or the frame interrupt?); recording coverage of the CALL at 0xA402

## Facts
- Tape (.tap = .tzx data): BASIC `HD 128K`, code 100 bytes at 30000, 5,000 at 32960, 200 at 43616, BASIC `-`, then one 41,400-byte block at 24000. Single load, no multiload.
- Snapshot: 128K, 7FFD 0x13 (ROM 1, bank 3 at C000), IM 2, I = 0xC1, vector table 0xC100 -> handler 0xC0C0 (CALL 0xC261 / EI / RET), SP 0xFFFA. Starts on the title screen.
- Interrupts mostly off in play: 742 accepted in 15,001 frames. The handler pages 7FFD (0xCD87/0xCD8A), uses EXX and AF'.
- 3D view: drawn into a back buffer at 0x8000-0x8FFF (write-first), copied to the screen's top 4K (0x4000-0x4FFF) by 0xDC45 (called from 0xDC37; 1,057 copies in 15,001 frames = one view every ~14 frames, ~3.5 a second). Dashboard needles and lamps: 0xE3AF / 0xE3D6 (16-byte plots), attributes 0xF228 / 0xF219.
- Look: the view is monochrome green (ink/paper attributes), the dashboard in fixed colours. No figure clash of the usual kind.
- Plain conversion: the survey's automatic tail fails (SP in the top 16K); `convert --tail 0x6C00` works: 0x6B53-0x6D5F untouched over all 22,116 frames.
- Options menu: 1 keyboard, 2 Kempston, 3 Fuller, 4 Interface 2, 5 cursor; SPACE centres steering, 0 aborts replay or off-road.

## Decision
Pending (stage-1 question to the user, 2026-11-22).

## Stage log
- 2026-11-22: stage 0 (intake), ~25 tool calls, 0 user rounds.
