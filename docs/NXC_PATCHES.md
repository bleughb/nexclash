# An NXC patch for the nxc repo, by hand

When `auto` makes no .nxc (a tape, a multiload: BRIEFING C2 #46), or the owner wants build options on
the loader's menu. Worked once, end to end: Cisco Heat 1.0, 2026-11-22 (jattree/nxc 7d9800a; the
scripts nxcb.py and mkpatch.py in the owner's C:\1NEXT\cisco_heat\work\nxc). The format is the nxc
repo's spec/NXC-FORMAT.md; its README covers `nxc.py` commands.

## 1. Build options as menu toggles
- Give each option ONE byte of its own (hook RAM or the hook page), read at run time. Each variant is
  then the base build with that byte changed: the same length, no two options on one byte, which is
  what a toggle must be (NXC-FORMAT "Toggles").
- Build every variant and diff them against the base byte by byte before packaging.
- Variants built by calling the engine's `build()` directly miss what `auto` adds last
  (`finish_outputs`): apply `z80tonex.automap_off` to each, or the patch starts with DivMMC automap on
  (Cisco Heat 1.0, fixed in 1.1). Check: the variant with the bare build's options equals the
  record's MD5.
- Display-only options are kind 3 (`--toggle "Name=VAR.nex"`); one that changes game logic is kind 4
  (`--toggle-logic`, plus a `toggle_N` proof line). Without rules a menu lets two be on at once;
  `--no-cap` lifts that when any combination plays.
- Verify each variant's own state on at least one recording (Cisco Heat: V2 with the car's sprites off,
  stage 1; with the 25 cadence, stage 3). Name toggles by what the player sees (at most 25 characters).
- Options belong in the patch, not as extra builds: one patch, one menu.

## 2. A tape target
- `nxc.py make BASE.nex GAME.tap --start START.z80 --tape-bank N,N -o OUT.nxc`: the start is the
  snapshot the build was made from (an RZX's embedded snapshot is fine); `--tape-bank` names the extra
  banks that hold a multiload's blocks, so the tape supplies them too. The tool prints what comes from
  the tape and what is carried (sites, at most 8,192 bytes). Cisco Heat: 61,044 bytes from the tape,
  3,096 carried; the rest the patch carries is the engine (stub, hook page, alt ROM) and SCR1.
- Name the folder and patch as the other patches (TOSEC-style title); `--file` is only the default name:
  the loader also finds the game under any name by length and MD5. `--zxdb ENTRY`.

## 3. The loading screen at ENTER
- `nxc.py set PATCH GAME build_screen OFFSET`: the SCREEN$ data's offset in the .tap. A .tap block is
  2 length bytes, a flag byte, data, a checksum, so the data of the 6,914-byte block starts 3 bytes in.
  It shows before the game is checked, read from the player's own file (`nex` instead shows SCR1, after
  the key is made). Needs the loader with build_screen (nxc PR 9 until merged); older ones keep the menu.
- The owner's rule (2026-11-22): no hold of the screen after loading in the NXC build (Cisco Heat:
  boot_frames 0; the bare .nex keeps 4 s or a key).

## 4. Cheats
- The archive .pok: spectrumcomputing.co.uk/zxdb/sinclair/pokes/<letter>/<Title (Year)(Publisher)>.pok,
  linked from the game's entry page (the entry id is its ZXDB number).
- Read each POKE's code, then run it: the simulator from captured states against the plain build (for
  Cisco Heat, `Machine.run(0x8BE1)` returns at once when already there, so step one instruction between
  updates). Leave out a POKE that does not help the player and say why in `trainers_played` (Cisco Heat:
  No Time Bonus only skips the stage-end bonus).
- `nxc.py import-pok PATCH GAME.pok GAME -o OUT --only "Name"`; a POKE in bank 8 at 0xC000+ on a 128K
  game needs `--top-bank`.

## 5. Text and order
- `--proof-file` takes PRF1 keys only (replay, emulator, hardware, coverage, pace...). INF1 notes
  (`tested`, `notes`, `changes`, `trainers_played`, `cheats_source`, `build_screen`) go in with
  `nxc.py set`, one call each; help lines with `nxc.py help --line fix=... --line toggle_N=...` (two rows
  of 32). Then trainers (`import-pok`), then the nxc repo's make_nfo.py (its tools folder).
- Script the whole chain: each step writes a new file, and a later change means remaking from `make`.

## 6. Checks before committing
- `nxc.py PATCH GAME --bare [--toggle T]...` must equal each variant's MD5; try toggles together, a
  trainer, the menu .nex and `--original`.
- The real loader on the nxc repo's Z80 harness (tests/nexclash_harness.py, as
  tests/test_nexclash_build_screen.py does): the menu's lines, the screen before the game check, each
  toggle, all together, a trainer, fix off. It needs the `z80` Python package and sjasmplus on PATH.
- The repo: patches/<folder>/<name>.nxc + .nfo and one patches/manifest.tsv line (patch, title, game
  file, patch MD5; the repo stores LF). Commit `feat: <Game> 1.0` with what was verified and what was not.
