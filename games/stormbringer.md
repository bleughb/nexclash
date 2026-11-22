# Stormbringer (Mastertronic Added Dimension 1987, 128K edition) - engine `stormbringer` (Knight Tyme's, relocated)

## Next session
Stage: 3 (prove + deliver)    Branch: add-stormbringer (from sprites-hide-all)
State: built 2026-11-21 from Knight Tyme's engine by an address map: IDENTICAL on 4 machine-played recordings, unit
  PASS, 16/16 negatives, rom_paths pass. Release 1.0 = the clash fix + checked cheats; no loading screen yet.
Inputs: specnext/reference/stormbringer/ (stormbringer.z80 md5 d462589b, sb_walk / sb_rooms / sb_cmds / sb_cmds2 .rzx,
  stormbringer.tap = the archive's [128K] tape).
Read: this file; games/knight_tyme.md for the method (rendering model, sites, hooks, verification).

## Port (how the engine was made)
The same engine as Knight Tyme, moved: instruction-skeleton windows and operand votes mapped every game address the
Knight Tyme engine names (hex and decimal) to Stormbringer's (32 code, 36 data; data wins where both). By hand:
0x6D7B / 0x6D81 -> 0x6E18 / 0x6E1E (either side of the room-build site), the Knight loop's HALT 0xAD48 -> 0xA8B2, the
96-byte buffer 0x64E0-0x6540 -> 0x63DA-0x643A (LD DE at 0xACEA / 0xA857), the window table's first entry (own windows).
Not mapped: hook-page addresses (0x80xx, 0x9440 = PAGE_ORG / HSTK, 0xA0xx). Site and signature bytes re-read from
Stormbringer. The Knight blit's continuation is 0xA8C7, not the matched 0xA8CE: Stormbringer adds LD A,(43162):
OR A: CALL Z,0x8EC7 after the blit CALL (the map's window match skipped them; fixed 2026-11-21, found by a full trace).
Knight Tyme only, off here (no 'overlay' in the profile): the Bridge crew tiles and their three negatives.

## Stormbringer's own
Flying things: 0x8EC7 (after the Knight loop's HALT and after the blit) XOR-plots up to 4 8 x 8 graphics through
0xAE0A in rooms 21-26 and 35 (table 0x8EA7: x, y, ...). They stay on the ULA, behind the sprites. Where one crosses the
Knight the original's XOR inverts his pixels and leaves screen bytes in A'; the sprite build shows him whole and A'
holds the clean screen's bytes. 0xAE4C / 0xAE51 / 0xAE70 discard A' before any use in these routines; across the
recordings the difference never reaches another register, RAM or the PC. Counted exceptions (flyer_boxes).
Lightning: 0x7240 draws a line from the sky to the Knight with ROM DRAW (0x24BA): identical (sb_cmds, sb_cmds2).

## Results
| Output | MD5 | Status |
|---|---|---|
| stormbringer.nex (plain) | see the record | boot OK |
| stormbringer_sprites.nex | see the record | 4 RZX IDENTICAL, unit PASS, 16/16 negatives |

## Hardware checklist
1. Menu (Z down, SPACE): PLAY GAME; the Knight walks (N, M) and the command window opens (SPACE).
2. Rooms 21-26 and 35: the flying things pass behind the Knight.
3. Characters and objects keep their colours; a window hides the figures under it.

## Lessons
- [local: an address map matches code that follows, not code that was inserted] A return address taken from a window
  match landed 7 bytes late; check every "after the call" address is the call site + 3 in the new game.

## Friction
- reuse: [local: Knight Tyme's engine relocated by address map; its loading-screen code came with Knight Tyme's checksum, found by the Codex review and replaced with Stormbringer's own]
- retries: [local: the review's recolour finding reproduced only with a normalised map (entries + palette): the engine's own map form is not what recolour.run reads]
- environment: [local: Stormbringer's reference files are not in the shared reference folder; staged from the scratchpad by MD5 for the rebuild check]
- hand-rolled: [none: the fixes use the engine's own functions and recolour.run as they are]
- scratch: [none: the recolour check ran inline; nothing added to tools/]

## Technique use
- detect.gameplay-screen-readers: helped: found the flying things' XOR (0xAE0A) as the one figure-pixel reader.
