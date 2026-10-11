# Contributing a game

1. `python nexclash.py new MyGame.z80` and follow `MyGame_session/SESSION.md` (record an RZX, run a
   Claude session with the prompt there).
2. When the sprite build works: `python nexclash.py contribute MyGame --report <MyGame_report.txt>`.
   The zip holds only files the session added or changed in the toolkit (code, .asm, profile,
   docs) plus the nexclash report. Game data (.z80/.rzx/.nex/.tap/...) is refused.
3. Upload `nexclash_contribution_MyGame.zip`:
   - **No GitHub account:** https://www.dropbox.com/request/7zanmicpbn5oafod24qs - anyone can
     upload there, no sign-in (uploads are visible only to the maintainers). Add your name/handle
     to the file name if you want credit.
   - **GitHub users:** open a pull request with the same files instead.

## What happens next (maintainers)
`python tools/merge_contribution.py nexclash_contribution_MyGame.zip` puts the files on a new
branch and lists them. The maintainers review against CLAUDE.md's rules, re-run the verification
with their own copy of the game where they have one, run `selftest.py` if shared code changed,
and merge. The game is in the next release.

By contributing you agree your contribution is licensed GPL-3.0-or-later.
