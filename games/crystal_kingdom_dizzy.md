# Crystal Kingdom Dizzy (Dizzy 7, Codemasters) - 128K sprite engine `crystal_kingdom_dizzy_sprites`

Reference files (private repo, specnext/reference/crystal_kingdom_dizzy/): dizzy7128k.z80 (128K,
md5 0cb1cb26), the 48K version (md5 9297ffd6), dizzy7_auto.rzx, and the built plain
crystal_kingdom_dizzy.nex (99975f65172dc86ecefbac07db2c0c00, the record's output name; was dizzy7.nex
until 2026-10-14).
dizzy7_auto.rzx is NOT usable for sprite work (dry run 2026-10-13): made by the 48K recorder, it
desyncs at frame 883 of 6,369, and the part that replays sits in the inventory menu. A sprite build
needs a Fuse recording from dizzy7128k.z80 (docs/RECORDING_CHECKLIST.md) - ask Dean first.
Known so far: IM 2 with a NON-uniform vector table (I=0xFD, the bus byte matters), handler at
0xFDFD uses IX, IY, EXX and EX AF,AF' (saved), 28 bytes of stack; ISR never touches slots 1/2/3/5;
screen writers 0xFC74 / 0xFAE0 / 0xFB56 (isr / scan --writers, 850 frames).

## Build
Plain: dizzy7128k.z80, `nexclash.py convert` (128K; the start-up tail must end below 0xC000, `--tail ADDR` if
needed); runs on hardware (2026-09-28). Sprite build: below; the record (since 2026-11-22) covers the sprite
build only (`auto` writes no plain .nex).


## Sprite build (2026-11-21, engine `crystal_kingdom_dizzy_sprites`)
- Draw model: every frame (DI at 0xDDC3) 0xF433 puts back the saved backgrounds, then the object list at 33639
  (record IX, 32 bytes, 0x7E00-0x7FFF) is drawn through the routine patched into the CALL at 0xF50C: masked
  save-under 0xF52D (1 byte), 0xF5EE (3, odd lines stored right to left), 0xF63E (4), 0xF6A4 / 0xF718 (3 / 4
  mirrored via the bit-reverse table at 0x8000); plain copies 0xF55D / 0xF5BE (record flag bit 5; 0xF55D paints
  its cells ink 7). Objects are monochrome and take the cells' ink: the clash.
- Hooks: 0xF508 shows the record's 4 sprites (white, 16 x 16 tiles) from the bytes the game ORs in, with a pattern
  cache (page 26 at 0x0000 inside the hook: pointer, routine, rows, signature; expansion table at 0x1000);
  0xF433 hides the records shown; 0xF8DD (room drawn) and 0xFBE1 (window) hide all. Plain copies stay on the ULA.
- Recordings: the pilot's 128K recorder (m128.py), walks ck_w1-4 (seeds 1-4, 9,000 frames each). Keys Z, X,
  SPACE, ENTER (found from the key test at 0xFA1F). Cheats: hearts DEC (HL) 0xED88, lives 0xDFB3.
- Results: IDENTICAL on ck_w1-4 (36,183 frames, 38,886 draws checked against the game's own writes, 4.7M sprite
  pixels); 840 unit cases; negatives 8/8. Hook cost about 28K T at 28 MHz a frame (estimated up to 5% slower).
  OverSpec from the .nxc menu: plays. Tang board: not reached (board offline 2026-11-21).
- Review fixes (2026-11-22): the cache signature is order-sensitive (a sum with RLCA and an XOR with RRCA: two rows
  swapped no longer hit the cache); site 0xF508's original bytes pinned; the detector reads 128K banks and SkoolKit
  snapshots; auto checks that draws were compared against the game; the window and room-drawn hooks get unit cases
  from captured states (every sprite shown, all hidden after), so their negative controls are caught on every walk.
  Re-verified: IDENTICAL on ck_w1-4, negatives 8/8. Record docs/records/crystal_kingdom_dizzy.json upgraded from
  plain-only to the sprite build (ad1e85b0), verified and stamped.

## Lessons
- [local: the walks reach hide hooks rarely] the window control was caught on one walk of four; hide hooks need
  unit cases from captured states, not luck in the recording (queued as a shared helper for all engines).
- [kb lesson.graphic-keys-collide-or-move: a sum is not a signature] an additive pattern signature matched rows in another order; signatures mix
  the position (rotate before add / xor).

## Friction
- reuse: [local: Finders Keepers' hide-hook unit case shape reused]
- retries: [kb lesson.auto-takes-one-rzx-per-recording: the first four-walk rerun passed several RZX files to one --rzx; auto takes one --rzx per recording] 
- environment: [local: the walks live in the scratchpad; reference folder staged by MD5 for the record]
- hand-rolled: [none: the record was upgraded with the records module's own checks and selftest]
- scratch: [none: the staging stays in the session's scratchpad]

## Technique use
- detect.gameplay-screen-readers: helped: scan --writers found the save-under routines and the plain copies.
- patch.xor-overlay-keep-ula: used in spirit: every pixel write kept, white sprites from the bytes the game ORs in.
- patch.restore-speed: corrected: the hooks forced 3.5 MHz on exit; the caller's NR 7 is now kept on the stack and put back.

## Next session
Stage 4: owner play; Tang board run of the sprite build; walks and the .pok to specnext; republish the nxc patch
(hook bytes changed) after the owner's quick test.
