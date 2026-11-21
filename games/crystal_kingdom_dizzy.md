# Crystal Kingdom Dizzy (Dizzy 7, Codemasters) - plain 128K conversion only

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
dizzy7128k.z80, `nexclash.py convert` (128K; the start-up tail must end below 0xC000, `--tail ADDR`
if needed). Runs on hardware (2026-09-28). Sprite build deferred (needs 128K engine work: analyse
and recorder are 48K-only).


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
