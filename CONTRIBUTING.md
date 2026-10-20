# Contributing a game

1. `python nexclash.py new MyGame.z80` and follow `MyGame_session/SESSION.md` (record an RZX, run a
   Claude session with the prompt there).
2. When the sprite build works: `python nexclash.py contribute MyGame --report MyGame_session/MyGame_nexclash/MyGame_report.txt`
   (the report `new`/`auto` wrote; same path as README.md).
   The zip holds only files the session added or changed in the toolkit (code, .asm, profile,
   docs) plus the nexclash report. Game data (.z80/.rzx/.nex/.tap/...) is refused.
   Changed anything outside your own engine (shared modules, shared
   docs)? Say so in the note: `selftest.py --canary` needs the maintainers' private reference
   files, so you cannot run it; the maintainers run it, and `--affected`, before merging.
3. Upload `nexclash_contribution_MyGame.zip`:
   - **No GitHub account:** https://www.dropbox.com/request/7zanmicpbn5oafod24qs - anyone can
     upload there, no sign-in (uploads are visible only to the maintainers). Add your name/handle
     to the file name if you want credit.
   - **GitHub users:** open a pull request with the same files instead.

## What happens next (maintainers)
`python tools/merge_contribution.py nexclash_contribution_MyGame.zip` puts the files on a new
branch and lists them. The maintainers review against CLAUDE.md's rules, put their own copy of
the game in the private reference repo (the game's record, docs/records/<game>.json, names it),
re-verify it (`selftest.py --game <game> --verify --stamp`), run `selftest.py --affected --verify
--stamp` (every other game the change reaches; nothing else) and merge. The game is in the next
release.

By contributing you agree your contribution is licensed GPL-3.0-or-later.
