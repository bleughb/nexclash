# Contributing a game

1. `python nexclash.py new MyGame.z80` and follow `MyGame_session/SESSION.md` (record an RZX, run a
   Claude session with the prompt there).
2. When the sprite build works (`patch` / `auto` wrote `MyGame.nxc`; `--nex` for the .nex files to
   test): `python nexclash.py contribute MyGame --report MyGame_session/MyGame_nexclash/MyGame_report.txt`
   (the report `new`/`auto` wrote; same path as README.md).
   The zip holds only files the session added or changed in the toolkit (code, .asm, profile,
   docs), the nexclash report, and `MyGame.nxc` from the report's folder: the patch to share, which
   needs the player's own copy of the game (loader and card setup: https://github.com/jattree/nxc).
   Game data (.z80/.rzx/.tap/...) and the .nex files are refused.
   Changed anything outside your own engine (shared modules, shared
   docs)? Say so in the note. Without push access the only check of other games you run is the
   single canary, `python selftest.py --canary` (Chuckie Egg, if you have its reference files);
   selftest.py refuses `--affected`, `--full` and release runs for you (exit 3). The maintainers
   run those, which rebuild and re-verify every game a change reaches, before merging.
3. Upload `nexclash_contribution_MyGame.zip`:
   - **No GitHub account:** https://www.dropbox.com/request/7zanmicpbn5oafod24qs - anyone can
     upload there, no sign-in (uploads are visible only to the maintainers). Add your name/handle
     to the file name if you want credit.
   - **GitHub users:** open a pull request with the same files instead.

## What happens next (maintainers)
`python tools/merge_contribution.py nexclash_contribution_MyGame.zip` puts the files on a new
branch after checking a clean checkout, archive hashes and original-file hashes (the report and
the .nxc go to contrib_reports/, outside git). Conflicts with newer files are refused before writes;
use a PR to merge them. Legacy zips without original hashes can add files, but cannot replace files. The maintainers review against CLAUDE.md's rules, put their own copy of
the game in the private reference repo (the game's record, docs/records/<game>.json, names it),
re-verify it (`selftest.py --game <game> --verify --stamp`), run `selftest.py --affected --verify
--stamp` (every other game the change reaches; nothing else) and merge. The game is in the next
release.

By contributing you agree your contribution is licensed GPL-3.0-or-later.

## Git and release packages
In a Git checkout, start a branch from current main and record the starting commit.
`contribute` compares against the merge base with origin/main, including committed and uncommitted
changes. If main moved or the base is otherwise ambiguous, pass `--base COMMIT` with the recorded
starting commit. Deletions and renames are refused: submit those through a pull request. Review
the printed file list before uploading.

An unpacked release has no Git history: preserve the entire modified package between sessions;
its manifest identifies changed files and their originals. Do not run Git refresh or commit commands in it.
Contribution metadata records the source baseline and original hashes; retain them for safe import.

For your new game, place the snapshot and recordings in a local reference directory outside the
checkout, using the paths in the record's `inputs.snapshot.path` and `inputs.recordings[].path`.
Run `python selftest.py /path/to/reference --game <record> --verify --stamp` (or set
`NEXCLASH_REFERENCE` to that directory). Missing files are not verification passes.
