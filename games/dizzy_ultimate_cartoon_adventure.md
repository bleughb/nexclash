# Dizzy: The Ultimate Cartoon Adventure (Dizzy 1) - XOR engine

48K. Dedicated builder nexclash/dizzy1_patch.py (printer only). Profile:
docs/profiles/dizzy1_ultimate_cartoon_adventure.json. Reference files (private repo,
specnext/reference/dizzy_ultimate_cartoon_adventure/): the snapshot (md5 0659328f; selftest input
dizzy1.z80) and dizzy1rzx (selftest input dizzy1.rzx).

| Output | MD5 |
|---|---|
| dizzy1_sprites.nex | 05d2bce99f4d7654d4e1c9c9c04dc391 |
| dizzy1.nex | 7892b2e0f1f3f9f19165516db307cbe0 |

Verified: dizzy1rzx 6,345 frames, 2,364 plots, 40,881 collision tests - identical. Hardware: untested.

## Facts
- Pure XOR plotter 58113 (entered 59488 erase / 59515 draw), no mask, no undo buffer;
  single screen write 58184; frames 0-38 + pre-shifted copies (+39 = same image 4 px right);
  88 patterns. Visibility = XOR parity (7 double draws cancel on screen).
- Falling objects land on Dizzy: collision 60228 needs a virtual read (screen XOR graphic).
- Printer buffer untouched but stack lives just above it (SP 23549 in game).
- Executes `LD R,A` (machine.py re-runs such frames with exact counting).

## Open
- Generalise dizzy1_patch.py into a generic XOR-parity template (STATUS open work).
