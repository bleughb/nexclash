# nexclash - BASIC USE FOR AI Tools (tested with OPUS 5.5 and GPT-6 Astra)

## Maintainers: put the below two line prompt into an AI Agent chat and hit enter
(Contributors cannot clone the private bleughb/specnext: run `python nexclash.py new MyGame.z80`
and use the prompt in the SESSION.md it writes - "Your game is not supported yet" below.)
Recommended OPUS 5.5 on MEDIUM
Tried with Sonnet 5.5 on MEDIUM and it actually uses MORE tokens / overly verbose and less accurate.
Haven't yet tried with lower models on other AI's
Please post your success stories

```
Add GAME NAME to nexclash. Snapshot and my RZX are attached.
Clone bleughb/nexclash and bleughb/specnext side by side and follow nexclash/CLAUDE.md
```

### Continue a game (handoff at meaningful boundaries)
Preserve a handoff at each stage. When context is large or the environment changes, start a new chat with:
```
Continue GAME NAME in nexclash. Clone bleughb/nexclash and bleughb/specnext side by side,
check out the working branch and commit from the previous handoff, then follow nexclash/CLAUDE.md
and start from the "Next session" block in games/<game>.md.
```
The design question (stage 1) lists the defaults: reply "defaults", or the numbers to change.

Hardware round (stage 4): test the whole game in one pass first, then send everything at once:
```
Continue GAME NAME in nexclash (as above). Hardware round: here is my whole list from one pass
(painted sheet attached if any). Fix all of it, then ONE build to check - no confirmations in between.
<list>
```


# nexclash - colour-clash-free ZX Spectrum games on the Spectrum Next

Turns a ZX Spectrum `.z80` snapshot of a game into Spectrum Next `.nex` files: a plain conversion
and a sprite build in which the game's figures are Next hardware sprites (no attribute clash).
`patch` packages the sprite build as a `.nxc` patch to share (`--nex` keeps the `.nex` files too).
Verification coverage varies by game and build; see STATUS.md and games/ for recordings, tests and hardware results.

No game files are included in the release. Contribution packaging excludes known game-data file
extensions; review the files before sharing. Attaching a snapshot or recording to an online AI
service uploads it. GPL-3.0-or-later (LICENSE). Status of every game: STATUS.md.

## Install (once)
1. Download and unzip the latest release, or clone this repository, then enter its directory.
2. With Python 3.10+, create a virtual environment (`python -m venv .venv`), activate it,
   then run `python -m pip install -r requirements.txt`.
3. For the `.nxc`: a C compiler (`cc`, `gcc` or `clang`) builds the bundled ZX0 compressor once; on Windows
   without one, download upstream's zx0.exe into tools/zx0/ (tools/zx0/README.md). Without either the build
   keeps its `.nex` files and the report says why.

## Patch your game
```
python nexclash.py patch MyGame.z80
```
Output in `MyGame_nexclash/`: `MyGame.nxc` and a report. **The `.nxc` is the file to share**: it
holds the sprite build as a patch and needs the player's own copy of the game (the `.z80` it was built
from, same MD5), so no game data travels with it. To play it on the Next, put it beside the game on
the SD card with the `.nxc` loader: loader, card setup and the `nxc.py` tool at
https://github.com/jattree/nxc. The `.nxc` holds every variant of the sprite build (its colour sets and toggles, the
tape's loading screen), each checked on read-back; outputs it does not hold stay beside it, named in the
report (`MyGame.nex`, the plain conversion). `--nex` also keeps `MyGame_sprites.nex` (sprites), to copy
straight to the card. Once only: `--patch-by "Your Name"` puts you on the menu's
credit line and is saved for later builds (or set `NEXCLASH_PATCH_BY`). Optional: `--publisher
"Ocean, 1986"`, `--pok cheats.pok` (default `MyGame.pok` beside the snapshot), `--target-file` (the
name players have the game under; default the snapshot's own, best in TOSEC style), `--no-nxc`.
The `.nxc` carries the proof the report gives (`PRF1`), and says "not verified" when there is none.
The last lines tell you how far it is proven:
- **Recognised snapshot** - check whether the output matches the reference; see the game notes for its verification and hardware coverage.
- **PATCHED** - a different dump of a supported game: every patch site held the original bytes,
  so the same patch applied; it is not yet replayed against a recording of YOUR snapshot. To
  prove it: record an RZX in Fuse (docs/RECORDING_CHECKLIST.md), then
  `python nexclash.py verify MyGame.z80 --rzx MyGame.rzx`.
- **not supported yet** - see the next section.

Snapshot tips: taken at the title screen, controls set to keyboard. The .nex forces 50 Hz video (as
the verified builds); `--allow-60hz` keeps the Next's own setting (then the report cannot match the
verified MD5s).

## Your game is not supported yet: add it with Claude
```
python nexclash.py new MyGame.z80
```
makes `MyGame_session/` with a plain `.nex`, what nexclash found, a recording checklist and
`SESSION.md`: a ready-made prompt for a Claude session (Claude Code, or claude.ai with code
execution) that follows this package's CLAUDE.md to add the game. When it works:
```
python nexclash.py contribute MyGame --report MyGame_session/MyGame_nexclash/MyGame_report.txt
```
builds `nexclash_contribution_MyGame.zip` - only the new code, profile, notes, results and the
`MyGame.nxc` beside the report (game files and `.nex` files are refused). Upload it as CONTRIBUTING.md says (no GitHub account needed); after review it
ships in the next release, for everyone.

## When the report says something is missing
| Report says | Do this |
|---|---|
| `weak recording` / `start=none detected` | add `--start "SPACE"` (or the real start keys, e.g. `--start "4 5, wait 20, 0 5"`) |
| `inputs=none responded` | add `--keys Z,X,SPACE` (Kempston: `--keys K:LEFT,K:RIGHT,K:FIRE`) or `--input kempston` |
| `dead stack ... 54 needed` | record an RZX in Fuse (docs/RECORDING_CHECKLIST.md) and rerun with `--rzx MY.rzx` |
| `unknown engine` / `needs a virtual read` / `FAILED` | `python nexclash.py new GAME.z80` (add it with Claude, below) |

Your own recordings are always welcome: `--rzx A.rzx --rzx B.rzx` analyses and
verifies each one. A recording you supply is remembered as evidence for that game
(`nexclash/evidence.json`), so it only has to be proved once.

## Quick iterations
```
python nexclash.py record GAME.z80 --start "SPACE" --keys Z,X,SPACE -o try.rzx
python nexclash.py record GAME.z80 --script moves.txt -o scripted.rzx
python nexclash.py record GAME.z80 --room-threshold 0.4 -o busy.rzx   (busy screens)
python nexclash.py rzx info try.rzx
python nexclash.py rzx merge a.rzx b.rzx -o both.rzx
python nexclash.py rzx strip fuse_autosave.rzx -o clean.rzx      (Fuse recording made with autosave on)
python nexclash.py auto GAME.z80 --no-record --rzx both.rzx
python nexclash.py auto GAME.z80 --quick 2000          (analyse/verify first 2000 frames only)
python nexclash.py identify GAME.z80                     (engine + derived addresses)
python nexclash.py convert GAME.z80 --rzx MY.rzx         (plain .nex only; 48K recordings - for 128K leave out --rzx)
```
Script format (`--script`, one step per line; `--start` uses the same steps, comma-separated):
```
wait 50            # no input for 50 frames
SPACE 5            # hold SPACE 5 frames
Z+SPACE 20         # hold two keys
K:RIGHT+K:FIRE 30  # Kempston (KR KL KU KD KF also accepted)
```
Recordings made by nexclash are normal RZX files: they replay in SkoolKit's
rzxplay and in Fuse (frame boundaries are defined by instruction counts).

## Supported games and engines
STATUS.md lists every supported game, its engine, what the sprite build does and how far it is
proven (generated from the evidence records, so it is always complete). Games whose engine is
generic (the Codemasters TID engine: Fantasy World Dizzy, Magicland Dizzy and relocated copies;
Dizzy V) are recognised automatically; anything else gets a plain `.nex` plus a report to guide
the next step. New engines (2026-11): three_weeks, starquake, lunar_jetman, robin_of_the_wood, nightshade,
knight_tyme, spellbound_magic_knight, rambo, ikari_warriors, renegade128 (Renegade).

Existing games are frozen: each builds what it was validated against. Improvements come as opt-in
reworks, each with its own proof and version (games/<game>.md "Rework"):
| Game | Rework | Choose it with |
|---|---|---|
| Jet Pac | v1.1: rocket / fuel / flames fix, Enhanced, loading screen | `--altrom-fill whole` |
| Match Day | v2: the trophy screen drawn clean (start-up tail moved) | `--altrom-fill whole` |
| Atic Atac | v1.3: faster hooks, flicker fix, QAOP toggle, Enhanced | `NEXCLASH_REWORK=atic_atac_v13` |
| Atic Atac | v1.4: v1.3 + the pace limiter (original pace, never faster) | `NEXCLASH_REWORK=atic_atac_v14` |
| Rainbow Islands (Z80N) | the sky fix: the squares round objects match the bright sky | `NEXCLASH_REWORK=rainbow_z80n_sky` |

## For patch makers: new tools
- The painter that follows the drawing, sprite sheet export / import: docs/COLOURS.md (PAINTER).
- Play checks soak, pace, flicker and looksheet: docs/CHECKS.md.
- Shared hook library for new engines (speed restore, pace limiter, preserving R, image cache, atomic
  switch): docs/ENGINE_CONTRACT.md and the cards in docs/techniques/.
- Pace target ORIGINAL by default: a new build runs no faster than the original (card patch.pace-limiter).

## Testing on the Next (details per game: games/)
Build with `--nex` and copy `GAME_sprites.nex` to the SD card and run it (or `GAME.nxc` with the loader). Check: it starts; every converted figure is
visible, animates and is never left behind on screen; figures disappear where the original hides
or covers them (boxes, dialogue, room changes, screen clears, scenery in front); music and speed
are as the plain `.nex`. Each game's own checklist is in games/<game>.md. If something is wrong,
record an RZX in Fuse (autosave OFF) showing it and send it with the report.
`run_cspect.bat` (Windows) makes the plain `.nex` and launches CSpect, or launches a `.nex` you drop on it
(edit the CSPECT path at the top).

## Per-game options (maintainers rebuild with their recordings)
Dedicated engines (below) never auto-record: they only use the recordings you pass with `--rzx`.
`auto` writes GAME.nxc like `patch`; the .nex files named below need `--nex`.
### Everyone's a Wally (128K snapshot)
    python nexclash.py auto wally.z80 --rzx my_play.rzx
Outputs wally.nex (plain) and wally_sprites.nex (gang members and masked objects as sprites).

### Chuckie Egg
    python nexclash.py auto Chuckie_Egg.z80 --rzx Chuckie_Egg.rzx --no-record
Outputs Chuckie_Egg.nex (plain) and Chuckie_Egg_sprites.nex (player, hens, duck as sprites).

### Commando (128K)
    python nexclash.py auto commando.z80 --rzx commando.rzx --no-record
Outputs commando.nex (plain) and commando_sprites.nex (player, enemy soldiers, POWs as sprites).
The snapshot is the 128K BASIC loader: `auto` runs it to the game entry and the .nex starts in a
small front end that repeats its key wait and "INFY LIVES(Y/N)?" (no 128K BASIC on the Next).

### Midnight Resistance (128K)
    python nexclash.py auto midnight_resistance.z80 --rzx my_play.rzx --no-record
Outputs midnight_resistance.nex (plain) and midnight_resistance_sprites.nex (player green, soldiers /
gun turrets white, jeep and end-of-level tank in their own colours; bullets and explosions stay on the
ULA). Snapshot at the title screen; Fuse autosave snapshots in the RZX are stripped automatically.

### Rainbow Islands (128K)
    python nexclash.py auto rainbow.z80 --rzx my_play.rzx --no-record [--ink white] [--outline black|blue|transparent|#RRGGBB] [--class-colours map.json]
Outputs rainbow.nex (plain) and rainbow_sprites.nex. Plain 128K conversion of other games:
`python nexclash.py convert game.z80 --tail ADDR` (ADDR below 0xC000, proven unused). Autosave snapshots in the RZX are stripped automatically.
