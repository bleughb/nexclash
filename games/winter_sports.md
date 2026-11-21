# Winter Sports (Electric Dreams Software, 1985) - plain multiload .nex (no engine yet)

## Next session
Stage: 3 (plain .nex done; no sprite build)  State: all six events load and play in JNext 1.2.0 (2026-11-22)
Inputs: the user's files (not in the repo): menu .z80 (48K v1, PC=0x0038, sp 0x5FEA), the .tap; no RZX
Branch: add-winter-sports (local, unpushed)
Start with: the user's hardware report per event (loads on hardware, 2026-11-22), then decide on a sprite build
Open: no RZX, so nothing is proven by differential replay; no record in docs/records, no engine line, no STATUS row

## Sources (five files compared, 2026-11-22)
- `.tap` = `[h].tzx`: the original release, standard 19-byte headers `wisp-1..6` (CODE, 32,824 bytes at 0x7500).
- `.tzx` and `[a].tzx`: the Firebird "Silver Range" re-release with the Bleepload turbo loader. Loader data of the two is
  identical; they differ only in pulse timings/pauses and block labels.
- All six 32,824-byte event blocks are byte-identical in all four tapes. The `.z80` is the 48K menu snapshot.
- The menu code (0x6000, `wispc0`) reads each event with its OWN loader (0x627E -> ROM 0x0562): first a 22-byte
  flag-FF pseudo-header (the Bleepload tape has these, 24-byte blocks; the .tap has standard headers instead, so the menu
  cannot load events from the .tap as it stands), then the event block to 0x7500. The wanted header is at the table 0x63C0 + 22 k
  (pointer in 0x6296). Events: k=0 Downhill/Slalom/Giant Slalom, 1 Ice Hockey, 2 Ski Jumping, 3 Speed Skating, 4 Bobsled,
  5 Biathlon. Main menu keys 1,4,5,6,7,8 (1-3 all load event 0).

## Build (tools/winter_sports_plain.py)
    python tools/winter_sports_plain.py MENU.z80 GAME.tap -o "Winter Sports (1985)(Electric Dreams Software).nex"
One 328,192-byte .nex: events in banks 12-26 (5 pages each), menu screen backup bank 27, a 127-byte hook at 0x6C00 in the
unused tail of the menu block (0x6503-0x74FF is stale loader data that no event or the menu touched in the runs),
`JP 0x6C00` at 0x627E (site checked: 14 08 15 f3). Header request: copy the wanted header, note k. Data request: copy
the event's pages through MMU0 (NextReg 0x50) with interrupts off, restore NextReg 0x50 = 0xFF, border, EI, carry set.
Loading screen: the tape's SCREEN$ is the NEX ULA loading screen (flags 0x82) and bank 5's screen; the stub's setup
(0xD000) waits 260 frames (raster line 192 counted via NextReg 0x1F) then copies the menu screen back: JNext log
SETUP F=500, game start F=761 = 5.2 s on top of the load.

## Evidence (JNext 1.2.0, headless, SD image read-only; scripts were in the working folder, not committed)
- Menu -> each event's option screen -> K + four control keys -> S: Downhill, Ice Hockey, Ski Jumping, Bobsled, Biathlon
  reach play; Speed Skating needs 1 player + keys + event 3 + S (it plays). Event A -> EXIT -> event B works (hook state is
  per request). Screenshots only, no register comparison.
- Real hardware (user, 2026-11-22): the .nex loads and the game runs. Details of events/loading screen not reported yet.
- Not tested: 60 Hz, High Scores entry, two-player modes, joystick.
