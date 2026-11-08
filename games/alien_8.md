# Alien 8 (Ultimate Play The Game, 1985; 48K) - engine `alien_8` (pilot game: emulator only)

## Next session
Stage: 4 (hardware). Hardware: untested. v1.2 (2026-11-07, owner approved, review .nxc not yet published): the default
build's palette holds the Next's own ULA colours instead of 205/255 shades; nothing else changes (below). v1.1 published
as .nxc 1.1 (2026-11-07), owner approved: runtime v27, actor
K98 / renderer K98, hook page SHA-256 de4df56e (before the start-up restore), auxiliary 9f921b99. The owner's full
painting of the figures and both cleanup rounds are installed: 118 painted IDs; the 12 unpainted IDs are room
structures in the original ink.
Files: `nexclash/alien_8.py`, `asm/alien_8_hooks.asm` with its includes
`asm/alien_8_{actor,sound_targets,queue,dirty,sprites,sprite_cache,primitive}.asm`, `docs/profiles/alien_8.json`
(hooks, signature, graphic table, static scenery IDs), `docs/profiles/alien_8_sound_sites.json`,
`docs/profiles/alien_8_colours.json` (the painting and floor as text). Build: `python -m nexclash.alien_8 SNAPSHOT
OUT.nex [--enhanced]`; the original graphics are decoded from the snapshot. With the original tape beside the snapshot
(same name, .tap, SHA-256 ab08ab65) the original loading screen is added (NEX header byte 10 = 2, start delay 50).
Registered (2026-11-07): `is_alien_8` in nexclash/engines.py (signature at A68E, 48K only); `auto` builds
`alien_8.nex` and `alien_8_enhanced.nex` and boot-checks both (registers with R, RAM, converter loader and NEXLOAD);
docs/records/alien_8.json makes `selftest --game alien_8` rebuild both (MD5). `verify` and `unit_tests` raise
NotImplementedError (as New Zealand Story's): the replay oracle and unit cases are the pilot run's
(runs/alien_8/release-20261106/art-update-20261107/work), not yet in the repository.
Both builds equalled the published .nxc 1.1 reconstructions byte for byte: default SHA-256 4a8b3e95 (MD5 aa9307fe),
Enhanced a897358a (MD5 5c08c856), so the pilot's proof carries. v1.2: Enhanced unchanged (a897358a); default SHA-256
1704c18d (MD5 e89ed13a) differs from 1.1's in 48 bytes only: 8 palette entries (the seven non-bright colours and bright
magenta, 205/255 shades -> ULA colours), each in the Layer 2 and sprite tables and their bit-7 copies. Those entries
were never drawn: default figures take entries 64 + ink (the ULA colours, unchanged) and static scenery shows the ULA
through Layer 2. Native JNext, input only to the bright magenta room 0x13, 1.1 and 1.2: every coloured sprite pixel
equals the ULA ink under it (287 / 19 / 349 pixels at 40 / 120 / 200 updates), pattern and Layer 2 bytes identical.
`tools/palette_check.py`: default PAL on the master; ENHANCED_PAL (1.1's, kept) and the painting still warn.

## Input and presentation
Target `Alien 8 (1985)(Ultimate Play The Game).z80`, MD5 `91a07828482c3e9b0fb76564abe3fe87`, the original 48K beeper
release; built directly from it. All art comes from the original game: no other conversion's art, colours or
data is used. Default: original monochrome artwork and masks, figures as hardware sprites over the original room.
Enhanced, off by default: the owner's painting of the original figures (15 flat colours in RGB333, full colour-pass
sheet SHA-256 983f59b7, owner sheet 1b961d52) and the dark grey floor (8e23b40b), clipped per room shape from the
room records. Original black detail and masks kept; no white outline; only exterior mask-only black is trimmed from
the player silhouettes.

## Renderer
Original masked draw order is captured into a bounded command list. Colour canvas with tagged pixels: dynamic paint
0..14, static 128..142, inherited ink 126 / 254, transparent 255, with duplicated physical colours, so no ownership
plane. Global aligned 16x16 hardware tiles from a 64-pattern exact hash + full-byte cache; pattern-union exhaustion
shows the complete colour canvas for that frame and rebuilds. One bounded publication per update in a 14-line
reservation. Memory: highest bank 47 (page 95): hook page 26, auxiliary 81, colour 52-57, ownership 40-45, display
28-39, sources 58-80, floors 46-51 / 82-93, Sinclair ROM 94/95.

## CPU, sound and pace
Shared hlib_iff, hlib_speed, hlib_r, hlib_pace, hlib_dma; on main 83bd781 they assemble the same page as at the pilot
baseline 938f8fe. Actor K98, renderer K98; full clear/copy work outside the renderer window is charged to the debt and
repaid from the original delay (A70B: 108 full B loops and 427 inner repeats in the recording, each rejoining at A715
with exact registers and R). Whole sound routines run at the incoming clock. Self-erasing 54-byte start-up tail;
whole hidden Sinclair ROM.

| Window (18 paired native trials, both modes) | Against the original |
|---|---|
| Steady idle, updates 20-80 | -1.71 .. -0.67% |
| Walking before the death, 80-136 | -0.10 .. +1.96% |
| Whole trial, 1-221 | -0.21 .. +1.08% |
| With the death, 80-140 | +0.01 .. +5.07% |
| Repayment, 140-200 | -2.52 .. +0.61% |

The first update after a full room redraw rebuilds every pattern (cold cache): up to 117.5 ms nominal, repaid by the
limiter afterwards. Steady idle and walking meet 2%; the death/redraw transient does not.

## Trainers
Infinite lives 51736=0; No time-out 44460=201; Immunity 45741=126; Freeze objects 49078=201; Mega jumps 49864=0; Start
10 lives 42587=10 (initialiser); Time 999 42592/42593/42598=144 (initialisers); One room goal 45121=1 (packed BCD; the
game's goal is 24 rooms, not 36). Initialiser patches survive restarts. The archive's ID-only inventory POKEs are
unsafe (items need linked world records) and are not offered.

## Evidence (pilot run release-20261106/art-update-20261107, v27)
- Each mode: the 18,000-frame input recording play-08: 57,730 hook comparisons, 25,246 plots, 2,877 publications, 3,828
  player updates, 4 starts, 17 deaths, 3 game overs; registers with R and 48K RAM at every rejoin; an independent
  source-PNG model of the full canvas after every hook; 5 of 5 negatives detected.
- 88 hook ABI cases, 1,504 injected IRQs, 152 whole-sound cases (37,680 FE writes); native layers (nine compositions),
  RAM (442,368 bytes) and beam audit (600 publications).
- Native soaks: 20,000 frames a mode; no overflow, no fast beeper write, no errors.
- Real dot-command loader on disposable NextZXOS v2.10 / 26.11 card copies: default, Enhanced, all eight trainers
  byte-exact; all ten live trainer operands checked.
Known issues: a cold room entry or death redraw lags briefly, then is repaid; Infinite lives with Start 10 lives shows
00 although the count is 10. Missing: hardware; natural completion; an in-repository verify and stamp.

## Hardware checklist
Both modes: walking pace and the death pause against the original; room entries; each trainer; the loading screen;
tearing at publication; beeper effects. Record board and core.

## Lessons
- [local: Alien 8 pace windows] A death-containing window mixes two costs: the sparse-room walking overhead and the cold
  pattern rebuild after the redraw. Split them per update before tuning K: K moved walking by 0.2 to 0.7% a step and the
  death window barely.
- [local: Alien 8 pace input] JNext queues joystick input to the next frame edge; an accelerated actor can read a
  different sample. Pace trials set A right after the original IN A,(1F) instead.
- [doc docs/LEARNING.md §1. Source refresh and verification freeze] Integration onto main 83bd781 (2026-11-07): the
  v27 sources differ from v26 in ACTOR_K and the painting only; main's changed hlib_iff / hlib_pace assemble the same
  page, and both builds equal the published .nxc's: shown by rebuilding, not assumed.
- [local: owner art as text] Painting of the original figures goes in the repository as palette-indexed rows
  (docs/profiles/alien_8_colours.json) and the original graphics are decoded from the user's snapshot, so `auto` and
  the record rebuild Enhanced without private files and no game graphics are stored.
- [local: palette_check reads tables, not draws] palette_check flagged 4 off-standard default entries (205/255 shades); the
  native snapshot showed the build never draws them (figures use entries 64 + ink). Check the indices drawn before
  saying a shade is seen.

## Friction
- reuse: [local: the Filmation renderer is per game; Knight Lore has its own copy]
- retries: [local: v25's replay stopped on the harness's hook-count gate; v26's harness and proof are the valid ones]
- environment: [local: run-relative includes needed moving for a repository build]
- hand-rolled: [local: replay oracle, native pace and loader checks are pilot scripts, not toolkit commands]
- scratch: [none: no scratch files in the toolkit]

## Technique use
- patch.whole-altrom-image: used; both modes restore the complete Sinclair ROM and erase the start-up tail.
- patch.pace-limiter: used; actor and renderer K windows with debt repaid from the original delay.
- patch.display-atomic-switch: used; one bounded publication of protected patterns and Layer 2 per update.

## Stage log
2026-11-07: release round in the pilot: accepted owner art and floor, v26 renderer, replays, pace, soaks, loader.
2026-11-07: integrated on main 213a238 (branch nexttang/alien-8-1.0): pilot scripts folded into nexclash/alien_8.py,
asm moved in, byte-identical rebuild of both modes; pace investigation of the death window (K trial).
2026-11-07: v1.1 (v27): full owner painting and cleanup rounds, actor K98; fresh replay, pace, sound, soak and loader
proof in the pilot; published as .nxc 1.1.
2026-11-07: on main 83bd781: v1.1 sources, painting as text, engine registered (detector, `auto` for both builds with
boot checks, record); both builds equal the published .nxc 1.1's.
2026-11-07: v1.2: default palette = the Next's ULA colours (palette bytes only; Enhanced byte-identical); native check
in room 0x13; review .nxc 1.2 in the pilot (runs/alien_8/package-v1.2).
