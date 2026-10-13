# Crystal Kingdom Dizzy (Dizzy 7, Codemasters) - plain 128K conversion only

Reference files (private repo, specnext/reference/crystal_kingdom_dizzy/): dizzy7128k.z80 (128K,
md5 0cb1cb26), the 48K version (md5 9297ffd6), dizzy7_auto.rzx, and the built plain dizzy7.nex
(99975f65172dc86ecefbac07db2c0c00; selftest rebuilds it as crystal_kingdom_dizzy.nex).

## Build
dizzy7128k.z80, `nexclash.py convert` (128K; the start-up tail must end below 0xC000, `--tail ADDR`
if needed). Runs on hardware (2026-09-28). Sprite build deferred (needs 128K engine work: analyse
and recorder are 48K-only).
