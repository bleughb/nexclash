# Play checks: soak, pace, flicker, look sheet (refactor plan 9-13; read when you run one)

Four checks a patch author runs on a BUILD in headless JNext, with the original as the control. They catch
what the differential verifiers cannot see: a freeze after minutes of play, a slower game, a picture that
is wrong between two frame ends, figures that look wrong. Each one warns and never refuses, and prints a
result block (`<out>/RESULT.txt`) that games/<game>.md and the proof record quote. They are for going
forward (owner, 2026-11-04): run them on new builds; published games are not re-checked unless the owner
picks one. Game facts come in as arguments and a profile; nothing in them knows a game.

## Setup
- JNext 1.1.104 on PATH (or `$NEXCLASH_JNEXT`), Pillow, an SD card image with NextZXOS (`--card` or
  `$NEXCLASH_JNEXT_CARD`; opened read-only). HOME is set to `<out>/.jnext_home` (or `--jnext-home`,
  `$NEXCLASH_JNEXT_HOME`): never the user's own, so their JNext settings and windows are not touched. The
  first run there records JNext's warm start (about 2 s).
- Frame 0 = the program's start: a .nex starts on the warm start (frame 500, checked on every run: a
  WARNING names a different start), a .z80 at 0.
- Control: the original .z80 (the game on a 128K / 48K machine) or the plain .nex (the same Next machine
  as the build: the closer control for pace).
- Profile (JSON; the format is in nexclash/jnext.py): start keys to reach play, the keys to play with,
  restart keys (game over -> new game), the probe address (once per game update), state addresses
  (lockstep), known waits. Without one a generic profile presses common start keys and QAOP, cursor and
  Kempston: little real play. Keep the game's profile beside its notes (local, not game data).
- `python selftest.py --tools` checks every detector on synthetic data and, with JNext and a card, runs
  Chuckie Egg against itself (pace exactly 0.00%, the same pictures).

## soak: freezes (plan 9)
`python -m nexclash.soak BUILD.nex --original GAME.z80 --profile P.json --minutes 15`
Both runs get the same random holds for N emulated minutes (about 1 min of wall time per 15). Reports a
still picture for 20 s while the input changed (`--static`): a FREEZE when the original never showed that
picture still, a wait (a menu or message the profile never answered) when it did; a LOOP when every PC
sample for 20 s sits in one 64-byte span that is not a profile wait or a span the original sat in; a crash
(JNext exit, the run ending early, errors). Keeps the last pictures before each finding; sheet.png shows
both runs once a minute: look at it, the input must reach play.
Three Weeks 25eab33d against the .z80 original, 15 min, seed 1: no freeze, loop or crash; 1593 and 1544
distinct pictures of 1801; one still period in the build (frames 21925-23775) and two in the original, all
the control menu waiting for its key (a wait: the original shows it still too); the sheet shows play in a
dozen rooms and several game overs in both.

## pace: the penalty meter (plan 10)
`python -m nexclash.pace BUILD.nex --original PLAIN.nex --profile P.json [--probe ADDR] --updates 600`
Input keyed to game updates (card verify.update-locked-pace): the same holds start and end at the same
update counts, so both runs do the same game work and the time between two updates is its cost. Table:
time for the same updates, all / quiet third / busy third (by the original's time per update) / worst
window, penalty %; per second AY data writes (music tempo), port 0xFE writes, interrupts taken, hook time
(NR 7 non-zero: every engine's hooks run at 28 MHz; pace waits count too), time with interrupts off (IFF1
on 20 lines a frame), the longest gap between interrupts taken (a held-off music interrupt). With `state`
addresses: lockstep checked at every update. No probe: the detector plays the original with JNext's
profiler and picks the commonest once-per-update count (slower, ~1 min). Warns beyond +-`--limit` (2%: a
build faster than the original misses the ORIGINAL target too) and on interrupts held off over 5 ms longer
than in the original. ORIGINAL is the default pace target: a negative penalty means a hook needs the pace
limiter (card patch.pace-limiter; new engines have it in asm/lib).
Three Weeks, plain .nex control, probe 0xA8ED, 600 updates in lockstep: d386a699 **+11.38%** (busy third
+11.30%, hook 9.1 ms an update), 25eab33d **+0.05%** (the approved hook-speed build; the pilot's own
route measured +9.8% and +0.15%). Automatic probe (0x8B5D): d386a699 +10.94%.

## flicker: every video frame (plan 11)
`python -m nexclash.flicker BUILD.nex --original PLAIN.nex --profile P.json --from F --frames 300`
Saves the picture and the machine (.jns) of each frame; the sprite layer is rendered from the saved
attributes, patterns and palette (pixel-exact against JNext's picture). Flags (card
verify.frame-layer-capture): OUT OF STEP (the sprite layer and the ULA under the figures change on different
frames, and the picture in the figures' box shows it), VANISHED (a figure missing for one frame), picture
changes per game update above the original's, attribute cells that change for one frame and back (Atic
Atac's red doors), one-frame picture transients. strip.png: flagged frames + neighbours. Frames missing / JNext failed:
NOT MEASURED / INCOMPLETE.
Nightshade walk (frames 400-699, probe 0xE200, plain .nex control at 1.12 changes an update): a94ebbb5
(the round-2 blink build) **6 out of step, 2 vanished, 2.62 changes an update**; 1cf6b276 (the fix)
**0, 0, 1.00** (3 at the frame edge only: its attribute burst ends on lines 0-7, before the play area;
counted, not flagged).

## looksheet: look sheet with flags (plan 13)
`python -m nexclash.looksheet BUILD.nex --at 600,900,1200 --profile P.json` (or `--jns FILES`, or
`--sheet X_REFERENCE_ALL_SPRITES.png` with its layout: a colour sheet, docs/COLOURS.md)
Every figure the build shows at 4x over black and two scenery colours (the commonest ULA colours around the
figures, or `--scenery`), beside a copy with the flags drawn. CUT: two colours meet in a straight row or
column for 3+ pixels with a flat area on each side (parts should follow the drawn lines: plan 19). VANISH:
a non-black colour with a contrast ratio to black under 1.6. RIM: a white outline round an inside that is
not white (plan 21). looksheet.json lists each figure's colours and flags.
Nightshade Enhanced, walk frames 420-690: the earlier part maps (8983d5d7, Enhanced b006e03f) flag every
back view with the hood cut straight at row 12 into the tunic (the owner's "the back of his helmet is the
wrong colour"); the drawn-region maps (b8c3754c, 37f97001) no longer have that cut. One 3-pixel shoulder
cut stays in both, and the newer front views have a 4-pixel collar cut: judge them on the sheet. RIM and
VANISH did not fire on these builds (synthetic checks only).
The painter (`python -m nexclash.paint paint`, docs/COLOURS.md PAINTER) runs the look sheet on every
painted sheet and merges away any colour boundary that would be a CUT. Its samples (2026-11-04, Jon's
pilot evidence, no build changed): Target: Renegade's whole sheet (89 figures), Nightshade's 22 hero
graphics and Robin's 8 walk / front / back graphics: CUT 0, VANISH 0, RIM 0.

## Coverage: recordings and soak profiles that visit everything (plan 9)
A recording or a soak that only plays the first screen proves only that. Cover, besides play
(docs/RECORDING_CHECKLIST.md): every menu (options, define keys: redefine and play with the new keys,
high-score entry), pause and resume, game over and back to the title, a second game. `record --script
FILE` takes the menu steps as written input (nexclash/recorder.py) before its own exploration; a soak
profile's `restart` keys take the game from game over back into play, and its sheet shows whether they did.
A menu the profile never answers shows as a wait in both runs: answer it in the profile and run again.

## Results and the proof record
- games/<game>.md "Results": the RESULT line of each check, the build MD5, the profile and seed.
- Pace and flicker are verify cards: list them in the record's `techniques` (phases []) with a `results`
  entry each (status pass, or partial with the explained warnings; scope = frames / updates, profile).
- A warning is not a failure: explain it (a menu wait, an intentional pace wait) or fix the build.

The sample results above: JNext 1.1.104, 2026-11-04, Jon's local builds (pilot run folders), not hardware.
