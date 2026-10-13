# Crystal Kingdom Dizzy (Dizzy 7, Codemasters) - plain 128K conversion only

Reference files (private repo, specnext/reference/crystal_kingdom_dizzy/): dizzy7128k.z80 (128K,
md5 0cb1cb26), the 48K version (md5 9297ffd6), dizzy7_auto.rzx, and the built plain dizzy7.nex
(99975f65172dc86ecefbac07db2c0c00; selftest rebuilds it as crystal_kingdom_dizzy.nex).
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
