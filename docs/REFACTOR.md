# NexClash refactor plan (2026-11-04)

The work on branch `refactor`, gathered from the .nxc work (github.com/jattree/nxc), tester reports (Leonis, Dean)
and a speed review. Paths like runs/... and pilot/... are Jon's local evidence folders, not in this repo. Every change
follows CLAUDE.md: a game's output changes only where the item says so, shared code is checked with
`selftest.py --canary` and `--affected`, and lessons go where docs/LEARNING.md says. The order below is the order of
work.

Scope (Dean's rule, 2026-11-04): the shared fixes are the default for NEW engines and builds. Existing games are
frozen: their record "pin" keeps the behaviour they were verified with, and each gets the new standard only as an
opt-in rework with its own proof and version (record "rework"). "Done" below means built and checked in software;
hardware runs are the games' own.

## 1. Bugs in the shared code (new builds get the fix; existing games by opt-in rework)
1. **Whole alt ROM image by default.** Write Sinclair's 48K ROM plus the hooks across 0x0000-0x3FFF, never only the
   hook bytes. The Next fills the alt ROM from NextZXOS's ROM3, whose UDG print and IM 1 reach the hooks. This broke
   Starquake, and five others had the hidden fault (runs/altrom_audit).
2. **The 128K ROM0 fill.** The stub fills alt image 0 from NextZXOS's ROM0, not the 128K editor ROM. Games that read
   ROM0 data may show it wrong; Knight Tyme's star map is the first suspect.
3. **Start state.** Match Day's trophy corruption comes from how the .nex starts (likely the printer buffer), in the
   shared converter. Other games could have the same.
4. **Hooks restore the speed they found,** instead of forcing 3.5 MHz on exit. Harmless today; needed for any speed
   option.

## 2. Bugs in single engines
5. **Atic Atac flicker.** The engine keeps the write that resets the cells a figure leaves, but drops the one that colours
   the cells it enters, so doors and furniture flash red for about 2 frames (runs/leonis_triage).
6. **Commando rock sniper drift** (Leonis). Not reproduced; waiting on where it happened.

## 3. Checks and tools (so authors catch problems themselves)
7. **Verifiers model the real Next ROM** (ROM3 of enNextZX.rom), not Sinclair's. Looking Glass gives the same ROM3.
8. **Palette blind spot.** Robin's verifier missed palette changes; check every verifier.
9. **Coverage.** Recordings that visit menus, define keys, game over and back, plus a freeze soak runner: random input
   for a set time, with the original as the control.
10. **Penalty meter.** Game pace, AY tempo, hook time and time with interrupts held off, original against build.
11. **Flicker check.** Every video frame captured; flag frames where sprites and screen disagree.
12. **Atomic sprite switch.** Check every engine against the technique note (Nightshade's fix).
13. **Look sheet with flags:** straight cuts across flat areas, colours that vanish on black, white rims.
These warn and never refuse. Their results go into the patch's proof record.

## 4. Speed
14. **Hook-speed pass per game,** pace target ORIGINAL by default (the pilot's hook-speed study). Largest hook time per
    frame first: Ikari 42%, Nightshade 26%, Atic Atac 18%, Wally 14%, Rainbow 12%, Starquake 10%, Three Weeks 9%,
    Cyclone 9%. Rainbow Islands' engine is the model.
15. **Fewer speed switches,** with longer 28 MHz stretches. That is faster, and it also stops setting off MAME's
    beeper crash.
16. **Shorter interrupt masking** where hooks hold off the music interrupt (Knight Tyme, Fireman).
17. **"Slowdown removed"** as an engine mode for games the owner names: slow non-sound routines at 28 MHz, capped at
    the original's quiet-scene pace. New Zealand Story first.
18. **Turbo** (later, opt-in only): a limiter, the beeper kept at 3.5 MHz, and a standard option kind in the .nxc spec.

## 5. Look
19. **One shared painter that follows the drawing.** Parts are the regions the ink lines close off. Splits happen only
    where the shape changes. Block or row colouring only if the author asks for it (Dean's "obsessed with attribute
    blocks"; Robin's face, Nightshade's sleeves).
20. **The same part in every frame:** regions matched across animation frames and facings, and one key frame labelled
    by the author carries to the rest.
21. **No white outline by default.**
22. **Sprite sheet export and import** (Dean's idea), building on the existing `recolour`. Export every image as a PNG
    sheet, repaint it anywhere, and import it straight into the build's reserved sprite memory as a new Enhanced set.
    No recompile.
    Built (branch refactor-painter): `python -m nexclash.paint` (regions, paint, export, import; docs/COLOURS.md
    PAINTER, card verify.paint-follows-drawing), proved on samples only, no game repainted. Engines that build images
    at run time (Nightshade, Lunar Jetman) still need item 24 before export and import reach them.

## 6. Output and workflow
23. **.nxc as the default output,** with the packager inside NexClash (both GPL-3). `--nex` keeps today's .nex.
    Done: the default output, every variant packaged (colour sets, the loading screen) and read back, outputs the
    .nxc does not hold kept; the patch author a one-time setting; Dean's credit the default; the version the
    record's (a rework's own), else 1.0; cheats from a .pok; PRF1 from this run's Verify / Unit / Result / Checks
    lines, else the record; `contribute` sends a .nxc. Not done (planned): the title comes from verified.json, the
    record or identify, but the publisher only from `--publisher` (no source has it); play-check results (pace,
    flicker, soak) are not in PRF1.
24. **Sprite sheet layout block** in the .nxc spec, so engines that build images at run time (Nightshade, Lunar
    Jetman, the NZS tilemap) can support export and import. Pending. Nightshade's complete pipeline (paint, export,
    import, owner and hardware review) is pending with it (games/nightshade.md).
25. **Alt ROM warning at packaging,** in nxc.py too. Pending.

## 7. Structure and documents
26. **A shared hook library:** sprite upload, attribute commit, double buffering, saving and restoring the speed. A
    fix then reaches every engine. Done for NEW engines (option 1, Dean's rule: existing engines keep their copies):
    asm/lib/hlib_*.asm (speed latch, R kept, pace limiter, content cache, atomic commit) + nexclash/hooklib.py
    (simulator model, every-site matrix, R and pace helpers; selftest --tools runs its tests and negatives). Item 4 and
    the owner's decisions (2026-11-04: preserve R, the limiter for ORIGINAL) are its defaults for new engines;
    cards patch.restore-speed, patch.preserve-r, patch.pace-limiter.
27. **Bring in our ~20 engines** from the per-game copies under pilot/runs, each as its own branch with its verifier,
    recordings and notes.
28. **Technique notes:** the whole alt ROM image, pace targets, hook speed without changing the picture, painting by
    the drawing, and the atomic switch (extended).
29. **Fixes to documents:** for example, Gryzor's speed notes describe turbo hooks it does not have.

## Not NexClash
- MAME 0.289 crashes when the CPU speed changes while the beeper sounds (23-byte repro in runs/leonis_triage/nr7test).
  It needs a report to the MAME project, if Jon wants one filed.
