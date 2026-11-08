# Atom Ant (Hi-Tec, 1990; 128K form of the tape)

## Next session
Stage: 3 done for default and Enhanced (v1.1). Hardware: untested. Not yet played by the owner.
Inputs: Atom Ant (1990)(Hi-Tec)(48K-128K).tap, MD5 404e992b4edceb10ef8fae9dfaac364b. Start state: that tape on a 128K machine stopped at 9FF4 (`tap2sna.py -c machine=128 -s 0x9FF4 --press 7:ENTER`); derived game data, never in this repo. Review run: runs/atom_ant/release-20261108.
Build: `nexclash.atom_ant.build(START, OUT)`, then `loading_nex` with the tape's screen. Not yet wired into `auto`, `engines.py` or a record: that comes when it goes upstream after the owner has played it.
Pending: owner's play; hardware checklist below. Enhanced: `nexclash.atom_ant_enh.Patch(start, set256, panel, palette)`; the review run's work folder holds the panel and palette dumps.

## Facts
- The archive's .z80 is a 48K dump: no music. The tape's last block (6,305 bytes to E75E in bank 3) loads only when 5B5C is non-zero, that is on a 128K machine. Code paging 9EEB/9EFB, music init E75E.
- Play area 24 columns x 20 rows, attribute 07 in all seven levels (640 cells): no clash. Panel and menus in colour, as the original.
- Back buffer 8DAC, copied to the screen by A184 through the address table DB37. Tile scroller A1FA, tiles at 5DC2, map from 8C2A.
- DI in play: no HALT in the main loop 9E3B, so pace is the cycle count. Music polled at AB76 from the main loop. Player update A771 from 9E4A; keys read at A775.
- Keys: table AF3F = P, O, A, Q, SPACE. F pauses (9E89), a control key resumes; G goes to 9FF4, the menu. LD A,R at AD97 is only a border buzz length: no game state.
- Figures have their own black masks over the dithered scenery: no outline added.

## Decision
No hooks. The default is the tape's 128K form with the original look. The menu's main line reads `128K build`: off hands the same state to NextZXOS's snapshot loader, which asks for ENTER.

## Known issues
- None found in the default. Pace +0.00% whole runs, quiet and busy thirds, worst 20 updates +0.01%.
- ROM: the ROM runs only in menus and the level screens (DI in play). Addresses below 0x386E match Sinclair's 48K ROM and NextZXOS 26.11's ROM 3; the 128K machine's own ROM 1 keypad scan at 386E up is not ROM 3's. JNext lockstep shows no game-state difference.

## Evidence (review run; JNext 1.1.104; emulator and simulator only)
Final bare .nex MD5 66d682f8cbe184c00ad2271ed8cf2a33. Three seeds of 800 updates at 9E4A, input applied at A778, lockstep at every update; soak 15 emulated minutes, same pictures as the original; flicker none; real .NEXCLASH on 26.11 card copies, default, each cheat and all, byte for byte, 5B5C = 0x10 in play, AY writes present. Full tables: the run's NOTES.md.

## Enhanced
Built 2026-11-08, version 1.1: a menu option, off by default; the default stays the 1.0 build, byte for byte (66d682f8).
- The set's code and art are this release's, so each graphic takes its colours from its own address: 256 tiles at 5DC2 (master identical), 28 figures at F877, F88D, F8A3 with their pre-shifted images. Nothing repainted.
- Value 255 ("use the attribute") stays transparent: the ULA shows, which is what Spec256 renders. So the ULA is kept as the original's, byte for byte.
- Route: full Layer 2, double buffered, tiles redrawn every pass. The pass 9E3E..9E44 and the copy each run at 28 MHz in one K window; the picture is drawn once at 9E44, left out of the window (nest), with hlib_debt_tick per tile row because it takes over a frame.
- Panel: the set's panel, static on Layer 2 in both buffers; the digits BD76..BDFD print (row 23: 4, 10, 15, 17, 18, 20-25, 29) stay ULA text in the original's colours. Menus, stage screens and the end text stay ULA too.
- A figure pixel the set paints with its mask open (112 pixels in all) is OR in Spec256, a plain colour here. Level-end attribute fade shows only on value-255 pixels, until the screen clears.
- Painter not named in the local files: "Spec256 team".

## Hardware checklist
Boot and loading screen; the music on the menu and between levels; keys, Kempston, Interface 2; pause and quit; each cheat; the level end with Infinite time.

## Lessons
- [local: 128K form] The archive's label 48K-128K is true only of the tape: the 48K .z80 lacks the music block. Check the loader's own paging before picking the target.
- [local: debt tick] The picture takes over a frame in one nest: without hlib_debt_tick a whole frame of debt was lost (one wrap allowed), and the run was 36% slow. Found by timing the hook's parts, not by reasoning.
- [local: no clash] A monochrome play area needs no hooks; the build is the conversion, and its proof is the boot check plus lockstep runs against the original. R has no hook to be compared at, and the notes say so.
- [local: the nxc repo's make_nfo is outside this repo] tools/make_nfo.py there always writes the clash-fix paragraph; a game with no clash needs it reworded by hand. Noted in the run's NOTES.md, not changed here.

## Technique use
- verify.update-locked-pace: used: three seeds at the player's update with input after the read.
- patch.preserve-r: no help: no hooks, so no R to preserve.

## Friction
- reuse: [none: pace, soak, flicker and the real-loader script were enough]
- retries: [local: lockstep negative] The immunity poke did not break lockstep in 500 updates (no collision came); the time poke does, at update 17.
- environment: [local: a heavily loaded machine this run] tap2sna hit its first 200-second limit on a loaded machine; it also needs `--press 7:ENTER` for the tape's PAUSE.
- hand-rolled: [local: review scripts] Packaging for a tape target and the boot check live in the review run.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stages 0-3 for the default; mock-up for Enhanced; review build for the owner.
- 2026-11-08 Enhanced from the Spec256 set, version 1.1; review build for the owner.
