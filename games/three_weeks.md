# Three Weeks in Paradise (Mikro-Gen 1986, 128K release) - engine `three_weeks` (unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-04 (record three_weeks, stamped); JNext only, never on a Next or in CSpect.
Inputs: specnext/reference/three_weeks/ (three_weeks_128.z80 = the archive file stepped to USR 0x6C00, 16 recordings t128_*.rzx).
Start with: the hardware checklist below. Open: everything under "Open".

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04 (pilot clone runs/three_weeks, base d7abd1c, head dbfe17f). Published .nxc: Three Weeks in Paradise v1.0 (md5 5443f903, github.com/jattree/nxc).
Rebuild in today's tree = the approved build: plain 1a6f1bbe, sprites 90eeeb14, Enhanced e6e6f6b0, each equal to `nxc.py --bare` (default / `--colours Enhanced`) of the published .nxc on the archive file bf0eff84. Trainers are pokes the .nxc applies over that .nex.
Pinned (record "pin"): `altrom_fill` rom3. The approved build has NextZXOS's ROM3 + the hook bytes 0x386E- as alt image 1; the new whole-image default gives sprites abc0f2e0 / Enhanced bec1527a (opt-in rework: `--altrom-fill whole`, then the ROM path check and a new proof).
Shared code the clone changed: nextboot.boot read the raster line (NR 0x1F) as a counter, and check() accepted 128K paging left unlocked. Both now live in the engine (`boot_check`, a wrapper around nextboot.check); nextboot is unchanged.
Moved into `auto`: the Enhanced build (docs/profiles/three_weeks_enhanced.json = work/enh.json) and its replay on ENH_VERIFY, the guard and effect unit negatives, and the negatives on the recordings that reach them (NEG_PLAN; the two pace negatives added to negative_patches). Left in the pilot folder: the negatives that need old builds' tables (162e6b6d, 773902f2, 177f2213, dense bush, cells over an item, palm exception), all DETECTED there (work/gb/neg12.log).
Profile colour_inputs was the 48K engine's (cbb1c2dc): now the 128K start's (1c89025f), so `recolour` accepts the build (selftest recolour guard).

## Hardware checklist
Boots to the picture, holds it until a key; 4 starts. Wally and every creature sprites, own colours, no clash; bats whole (no seam). Wally walks behind plants and palms (right-edge palms of rooms 1, 3, 7, 14, 15 in front); black never covers him. Room changes clean, no stray sprites after a death or the game over. Room 21 dark effect. Pace as the original (the slowdown and the lagging tune are the original's). Menu set Enhanced: colours as in JNext. Trainers 1 and 2.

## Snapshot and start
Archive "Three Weeks in Paradise (1986)(Mikro-Gen)(128K).z80", bf0eff8438e543f18e76d14940665d7d, the bytes of the `.256`. ZXDB filecheck: 502, once.
128K. The file stops in a 128 BASIC direct command: PAUSE at 0x1F3D in ROM 1, the tape's picture on screen, then RANDOMIZE USR 0x6C00. Stepped with a key held to PC 0x6C00: rzx/s0.z80. It differs from the file in 39 bytes of bank 5 (system variables, BASIC's stack). The .nex starts there, so 128 BASIC never runs on NextZXOS's ROMs. From 0x6C00: DI for ever, no ROM fetch in any recording (work/p1.py), 7FFD always with bit 4.
The tape block's first 6,912 bytes are the file's screen (work/scr.py): the loading picture is bank 5 as it stands. The set-up holds it until a key or 250 frames, waits for the key to go. Game memory at 0x6C00: boot check OK.
Keys: 4 leaves the title screen and starts from the menu (keyboard is the default; pressing 3 at the menu also toggles Wally's colour, as in the original). Any key after the Start. P / O right / left, Z jump, A down / door, 1 2 items. In play 3 Wally's colour, 4 pause, 5 tune.

## Banks at 0xC000 (the 128K difference)
0 figures and data (default in play); 3 Wally, 18 frames at 0xC006 (0xB8C2 pages it around his plot); 1 and 6 tiles; 4 text; 7 the picture. Figures also at 0x7115 and 0x8450-0x8AF0 (RAM). AY player at 0xC116, polled from the main loop in DI. Every blit in every recording ran with bank 0, but tiles leave bank 1 paged, so the commit reads MMU 6 by port, pages 0 or 3 for each figure, and puts it back.
Address map from the 48K engine: instruction streams matched (work/a128c.py), each site then read. All code moved by uneven amounts; no shared offset.

## The owner's finding, by layer
"wally has no clash but all the enemies do". png/owner/v1_sheet.png, the 48K build in JNext, layer by layer: no enemy on the ULA, every enemy on the sprite layer, and a bat half yellow half green on the sprite layer. The engine gave each plot "the ink of the clean cell under its centre", and a bat is two 16 x 16 plots, so each half took its own cell's colour, and colour changed as it crossed cells. Clash in the sprite colours, not on the ULA. Only Wally had a colour of his own.
Fix: FIGS (docs/profiles/three_weeks_figs.json), one fixed ink per figure family by graphics address, first entry Wally. Nothing reads the cell any more.
The game has no colours for these figures, so the default ink is a default: the bright Spectrum colour nearest the .256's main ink for that family. A human would choose these.
706E: a second plotter, XOR straight to the screen: all calls in the recordings have y >= 128 (panel, messages); no figure uses it.
Moving on the ULA (verify counts cells of the clean buffer and clean attributes changing within a room, front cells aside): see Results. 

## Rendering model
Main loop 0x8DD4: 0xA90D attributes 7400 -> 7600; figures plotted into the back buffer 0x5B00-0x6AFF (rows 0-127), save-under to 0x7800 (pointer 35663, count 27858); 0xA1E9 the room's front routine; 0xA8ED blit (line table 27926, attributes 7600 -> 5800); 0xB7D7 restores the list. Second copy of that order at 0x9080 (death). Room entry: 0xA91D clears, tiles through 0xB78E, 0xA1E9, 0xA89C 4-pass wipe that reads the buffer and the screen, 0xB7D7.
Plotters, prologue FD E5 D9: B82C OR 16x16 (base (47723) + A*32, pos 27906/7; y a word), BA5F masked 16x16 (A*64; items: return address BB53), B9B0 OR 24x32 (A*96, pos 27839/40), B8B4 masked 24x32 (A*192), B8C2 Wally masked 24x32 (C006 + (27841)*192, pos 27830/1).
In-place changes to graphics: Wally 0xB75C mirrors all 18 frames on a turn (35634); 0xB52E mirrors the spear carrier (0xD680, 384 bytes) when his direction (35669) changes sign; 0x8F23 copies frame 17 (0xCCC6) over frame 0, which differs from the snapshot's in 27 bytes; 0x8F3B shifts frame 0 down a line per step while he sinks ((27887) non-zero).
Attribute buffer writers: 0xB787 tiles (7400 too), item paint, 0x9451 Wally's paint (skipped if 27866, key 3, or 27876, set while he goes through the hut door), 0xA3F1 room 21's effect.

## Room 21 and the plots-survive guard
0xA3F1 (48K 0xD08B) is inside room 21's handler 0xA3E5, every game frame while (27886) is 0: the room is dark, the attribute buffer goes white on black; replayed on t128_r21, its negative detected. "Plots survive 0xB7D7": plots are never pending when the list is restored in any play recording; the guard is kept (one site) and tested directly (unit test: log a plot, run 0xB7D7, log empty; t128_pend, a forced start state).

## Design
The game's code runs unchanged; plotters only log. e_bl walks the save-under list without changing it, so the blit shows no figures, 0xB7D7 then writes the same bytes again; e_at takes attributes from the clean copy 7400 (7600 if the effect ran). So no game memory differs but the screen, and two dead-stack bytes.
Page 26 at slot 0 in a hook: variables, code, cache, tables, stack; stubs in the alt ROM's free 0x386E-. Patterns built at run time from the game's bytes, cached by kind, address, a rotating hash, inks. 48 small entries, 20 large.
Front cells (e_fon, e_fof, e_tile) go to Layer 2 over the sprites; order L S U. The game's own depth.
Outline and fill (brief's rules): opaque pixels = ink, or mask clear. Fewer than 24: neither (bullets, sparks). A clear pixel with opaque ones left, right, above and below in line: black fill, details kept. A clear pixel 4-next to the result: outline, white, black on a figure whose ink is white. The box has a pixel of margin on all four sides (88d3f7a: 2 x 2 tiles, or 2 x 3), so an outline pixel can fall one pixel beyond the graphic anywhere; before it the top row (and the bottom and left) were cut when a frame's graphic reached its box edge, the owner's high step and cry. work/check_outline.py, through the real hook code, every figure frame: 16,171 of 16,171 outline pixels drawn, top 1,152 of 1,152. Masked pixels stay the game's black. Game logic unchanged.
Defaults a human would decide: every figure a sprite; panel, text, scenery on the ULA; inks as above; Wally bright yellow as the game paints him; items their table cells; key 3 off gives Wally the room's ink, whole; at the hut door he keeps his colour (the original drops it).
Figure off the right edge clips; the original wraps it to the left a line down (counted, margin wrap).

## Go-behind scenery (owner's asks, 2026-11-03)
Upright scenery drawn on Layer 2 over the sprites, so figures pass behind it. The game's own front cells stay as they were (whole cells, as the original prints them; room 0's and 29's sign poles and 29's tall grass are the game's own).
By whole items (the owner's second round: the 177f2213 build, chosen by cell, split a flower, a tuft, the yellow grass and a rock). Items are the game's own room objects: the room list (39900, walked at 0xA96E) calls the object drawer 0x6F29 at 0xA9A3 once per object with its place and number; a cell belongs to the last object printed in it (tiles are copied, not ORed), and objects of one number whose cells touch are one item (a palm trunk is stacked segments). work/gb/survey.py logs the calls and tile prints for all 37 rooms; work/gb/items.py, items_NN.png.
Pixel-accurate: a cell whose paper is the room's background goes in front by its ink pixels only (paper transparent); a cell whose paper is not (a red trunk is red paper with black dots) goes in front whole, ink and paper (solid, bit 7 of the run's column).
Choice: work/gb/choose2.py by eye, then the owner's limits decide, an item whole in front or whole behind. His words: "Wally must never vanish entirely (at least his outline or most of him stays visible)": at every place, the better of (his pixels showing, his outline pixels showing) must be at least half. work/gb/wallyvis.py checks it before any replay: Wally's sprite layer from the real hook code (work/check_outline.py), in every pose (frame and height) the recordings show (work/gb/poses.py: 76 poses), both facings, at every even x, each item alone (wallyvis_all.json). The replay census checks the same rule at every commit, and drops any item over a collectable. Result: docs/profiles/three_weeks_gb.json, 37 items, 216 cells, 16 rooms (0, 2, 3, 4, 7, 13, 14, 15, 16, 18, 24, 25, 26, 28, 29, 30). Contact sheet: out/three_weeks_fix2.png, lower part.
Behind by the rules (worst per mille, outline or all): the big flowers, every tree and palm trunk (none reaches 500 over his walk range x 4-230), the conifers, room 31's post. Tufts and grass pass by his outline, not by his pixels alone: the rule as the owner worded it keeps them in front. Poles and signs of rooms 0, 4, 25, 29 are the game's own front cells, in front in the original too.
The owner's exception (2026-11-03): the right-edge palm trunk (#8, columns 30-31) of rooms 1, 3, 7, 14, 15 is in front, whole, although at x 228-230, his last steps before the room changes, it leaves 35.6-46.1 % of his body showing. EDGE_EXCEPTION allows exactly that (those rooms, x >= 228, the rest of the front still keeps the rule); negative "the palm exception taken out of the check". work/gb/roomvis.json checks every room's items together.
Third round (773902f2, black inside Wally): black is transparent on Layer 2, ink or paper, for go-behind and the game's own front cells; solid is a non-black paper only; visibility counts his body (pixels inside the outline). Collectables (plotter called from 0xBB53) are drawn under every figure (ITF flags, two passes in h_com); conditional room objects (0xFE) are never chosen. Check "a figure pixel under a black front pixel". 42 items, 402 cells, 18 rooms.
Fourth round (162e6b6d, bat seam): two-part figures (bats 0xD9C0 / 0xDA00 side by side, others above or three-part; work/gb/pairs.py) were outlined part by part. h_nb finds the parts at each commit (same kind, graphics one frame apart, abutting), h_nbcut drops the outline where they meet. Checks: "a figure cut by its other part's outline", "a part of a figure not shown whole on the sprite layer"; every creature at least half visible behind go-behind items (dropped room 24's spikes). out/three_weeks_bat_fix.png.
Not chosen (work/gb/choose2.py): pillars, skeletons, walls, wide trunks, the dark room 21, barrels and weapons, room 23 (fills in play), robot rooms 32-36 (unrecorded), and the interactive objects.
Hooks: pointers at 0x1A00 (room * 2), lists at 0x1140-0x13FF; an item is runs (col | 0x80 if solid, row, rows) then 0xFE; 0xFF ends the room. h_gb, called from h_front before the front cells: whole items in table order, a new item only while fewer than 16 cells were drawn this commit, never in the commit after a wipe (V_NOGB), so the room change does no go-behind drawing. h_gcell 34 T a pixel (clear colour in IXL: transparent, or the paper). h_l2clr's clear loop unrolled.
Verify: the model draws the same items on the same commits from the module's table, checks Layer 2 pixel by pixel against the clean buffer; every commit, "Wally mostly hidden" (below 50 %) and "an item hidden" fail; once a room's items are all drawn, "a scenery item split by go-behind" fails if any item of this replay's own room build has some cells in front and some not, and "go-behind cells not owned by a room object" if a chosen cell belongs to no room object.

## Pace (owner: "the patched version could be a little slower", 2026-11-04)
Measured in headless JNext, update-locked (work/pace/cap.py, lock.py): input and pictures by game update, not video frame, so every build is in the same state at the same update (X, room, lives, Wally's frame checked at all 561 updates). The game runs DI throughout (no interrupt in play, 0 counted), never sync'd to the frame: an update is 1,190-1,530 lines. The blit 0xA8ED (128 lines by LDIR, then 512 attribute LDIs) alone is 538.6 lines at 3.5 MHz (JNext, contended, mean of 768, sd 12).
Music: the in-game tune is the beeper, not the AY (AY writes in play: 0). 0xBEAF plays one step every second main-loop pass (counter in 27909, bit 7 = tune off, key 5). The effects (0x718B, a table of pitch sweeps: the hurt tick/tweet) are cycle-timed OUT loops inside the update, DI. An update with an effect lasted about 1.5 times a normal one in the original (JNext), so the tune's next steps come late: the lag is the original's own, and the d386a699 build only added its hook time on top.
d386a699: hooks cost 5-11 ms an update, 8-13 % slower (e_at by LDIR at 3.5 MHz was slower than the LDI chain it replaced).
Now: (1) cheaper hooks with the same results: h_find's and h_front's hash unrolled (the same function, so the same cache keys and patterns), h_rest unrolled, h_ink memo (32 entries; INKT is fixed). Simulator, t128_walk 3,000 frames: h_find 48.6 -> 30.4K T a commit, h_front 34.9 -> 24.0K, h_rest 18.5 -> 13.4K, h_ink 11.9 -> 1.8K. (2) The pace window: e_bl reads the video line (NR 0x1E/0x1F); the machine stays at 28 MHz through the hooks, the game's own blit and the attributes (e_at); x_pad then waits until the original blit's 538.6 lines have passed, less V_DEBT, the hook time spent outside the window since the last blit (plots measured by the video line, 0 or 1 line each, right on average; tiles 5/16 line each by estimate; the room change e_wp/e_aw measured with a tick per figure and per built row). Time over the window (a long build, a room change) carries in V_DEBT, at most 3,072 lines, and is repaid by the next windows. No game byte, register or flag differs (verified); only time.
Results (update-locked, seconds, plain / d386a699 / this): room 0 with bats 5.66 / 6.24 / 5.66; hurt with effects 9.54 / 10.82 / 9.56; room 2 across 9.55 / 10.27 / 9.63; room 3 across 9.07 / 9.92 / 9.04; updates 21-561 in all 46.73 / 51.29 / 46.80 (+0.15 %).
Left: each room change's hook time (about 100 ms: e_aw builds every new figure) is a hitch of the change itself, repaid within the next one or two updates, which run that much faster. JNext only; on a Next the line counter and the 28 MHz waits are the hardware's own, so the window holds the same lines, but this is not measured there. 60 Hz: the lines per frame are learned at each wait (311 until then).
Negatives (timing, JNext): the window without the wait (TGT16 0): -18 to -32 %; V_DEBT ignored: +1.2 to +2.7 %. Replay: "the pace wait loses AF" (registers differ: 373), "the blit left at 28 MHz" (MMU / speed not restored: 224).
Captures: by update, the frame after the blit, d386a699 against this build: 7 of 7 pixel-identical (work/pace/out/C_old, C_new). During the hurt the death path's render runs, so those updates have no capture.
Note: the game reads R (LD A,R at 0xAD85); hooks change R in every build, so random choices can differ from the original's (the update-locked runs stayed in step).

## Enhanced (menu set, off by default)
work/paint128.py, method of paint256.py: master bits must equal the game's, then palette index per bit -> RGB. .256 master: every non-zero byte of banks 0, 3, 4, 6 the same; bank 1 same; bank 2 all but 2. Colours from the MVV package's older Spec256 conversion (SOURCES.txt: mvv_games/Spec256-Games-master/TreeWeeks128k), painter not established. No --colours-by.
Each family a palette line (15 in use), up to 12 colours in RGB332, nibble 8 black, 15 white, 7 near-white ink so the outline goes black. Items by frame, 5 colours each. Wally's frame 0 painted from 0xCCC6. Mirrors handled for Wally and the spear carrier. While Wally sinks no map fits: he stays whole in his main colour. Keys: figures their address, Wally address - 0x6000 (bank 3 overlaps bank 0's addresses).
Census (work/cens.py, by plot, in recordings): see Results. 0x7115 and 0xDBA0 have no colours in the .256 at all: one fixed ink, whole.
Limit: quantised to RGB332 and merged to fit lines; a family's rarest colours move to the nearest kept.

## Results
| Output | MD5 | Status |
|---|---|---|
| three_weeks_128.nex (plain, tail 0x6000) | 1a6f1bbe0abfbcfbb5712ad4f4700e95 | boot sim OK, reaches play in JNext |
| three_weeks_128_sprites.nex | 90eeeb14fa20edc3585124422530a41d (was 5bdaf86b, now .prev6.nex) | the pace window and cheaper hooks (see Pace); outline margin + go-behind by whole items, black see-through, collectables under, two-part figures whole, the edge-palm exception; boot sim OK, replay IDENTICAL, reaches play in JNext headless; not through the real loader again; hardware untested |
| three_weeks_128_enhanced.nex | e6e6f6b06c3cff4f2cd259ce27de035a (was c102b389, now .prev6.nex) | the same, the menu set |
| three_weeks_128.nxc | 25eab33d1e955ba3e0630ae3f1d75e9c | the pace build (published as v1.0, 5443f903): apply --bare byte-exact, default and Enhanced; through the real loader, MD5 exact (work/gb/loaderw.py). Earlier .nxc: d386a699, 162e6b6d, 773902f2, 291529d3, 177f2213, 6b62306f (out/*.prev*.nxc) |
Import verify (selftest --verify --stamp, 2026-11-04): 16 recordings default + 5 Enhanced IDENTICAL, unit PASS, 21 of 21 negatives + 2 unit negatives DETECTED.
Pilot replay of the pace build (work/pace/v1/): 16 recordings, 62,696 frames default and 5, 28,930 Enhanced, all IDENTICAL. Go-behind on t128_tour: 563 room checks, 0 split; Wally's body least 52.1 % (47.5 % at the palm exception); no figure pixel under black; no item hidden; all 18 go-behind rooms replayed. Static: every kept item at least 50.0 % over 76 recorded poses at every even x. Unit 80 cases, full log, pressure, map, guard, effect: PASS.
Hooks, t128_tour (45,116 frames): 6F09 3, A1E9 8057, A204 8057, A89C 567, A8ED 7490, A9B8 567, B78E 364771, B7D7 8624, B82C 10076, B8B4 1383, B8C2 7490, B9B0 1375, BA5F 14329. t128_r21: A3F1 185. 9,529,434 sprite pixels compared; most sprites in a frame 17.
Pilot negatives (work/gb/neg12.log, work/pace/negpace.log): 27 of 27 DETECTED, among them the old builds 162e6b6d (a part not shown whole) and 773902f2 (figure pixel under black), the palm exception taken out, a dense bush, cells over an item, the 177f2213 table (split). "plots survive 0xB7D7" only on t128_pend and in the unit test.
ULA by layer: no figure moves on the ULA. Only room 23 changes, 451 cells, whole rows filling as scenery (work/u23.py). 706E: y >= 128 only.
Enhanced census by plot (work/cens_final.log, 13 recordings, 51,871 plots): no half-painted figure. Three have one stray default pixel (0xCD40 52 of 53, 0xD320 44 of 45, 0xD340 150 of 151); four frames have no .256 colour and are one fixed ink whole (0x7115, 0x7135, 0xDBA0, 0xDBC0).
Sound: JNext WAVs of both builds play; not compared by ear.
Speed (simulator): 155-177K T per game frame at 28 MHz against about 425K T at 3.5 MHz, about 5 %; the go-behind adds 3.8 % a frame (h_nb). Pace in JNext: see "Pace".
Cheats: lives held at 3 with each POKE, 3 down to 0 without, same inputs, simulator on the original code. Through the loader with both on, played by a script; effect in the patched build not checked.

## Coverage
t128_tour (cheats poked in the start): 19 rooms by walking, 45,116 frames. t128_gameover (no cheat): deaths, game over, picture, menu, new game. t128_rN: teleports, the game's own room change run with a poked room: 6, 8-12, 18-21, 23, 24, 31 (some leave at once; 8 to 9, 10 to 12). Not reached: solving the puzzles, Wilma and Herbert, the ending. The graphics of families no recording plots are painted statically by their calling plotter.

## Open
Lag: built, see "Pace" (2026-11-04).
Hardware, CSpect. Speed on a board. Evidence record docs/records, doccheck, selftest stamp: not done. Colour route for a human painter: RECOLOUR, sheets/128/.

## Lessons
- [local: import pin] An approved build made before the 2026-11-04 defaults rebuilds only with the record's pin (alt ROM fill rom3); the unpinned rebuild differs in bank 47 and the stub.
- [backlog C2 #45] The clone's nextboot edits (raster counter, 128K paging) were needed only by this build's check: a wrapper in the engine (boot_check) keeps nextboot as it was for every other game.
- [local: stale profile field] colour_inputs came from the 48K engine and never matched the 128K build; nothing used recolour until the record's guard ran it.
- [local: 128K BASIC snapshot] A file stopped in 128 BASIC can be stepped to its USR with a key held; the .nex starts there and the 39 bytes go in SIT1. Check PC, the stack and PROG before believing "needs ROM".
- [local: colour by cell] Colour from the cell under a sprite is clash moved to the sprite layer. Two-plot figures show it first. Check by layer before trusting a clash report's cause.
- [local: a menu key doing two things] 3 selects keyboard and toggles Wally's colour; test bots pressing it hid his colour for a whole session of PNGs. Read the flag.
- [local: graphics changed in place] Compare in-play graphics with the snapshot before painting: frame 0 differs from its snapshot bytes, the spear carrier mirrors in place; a census by plot found both.
- [local: test snapshots with a tail] A state saved in play has a room in the buffer, so a tail placed there draws a line on screen. Test builds only.

## Techniques
Techniques: `optimise.pattern-cache`, `verify.update-locked-pace` (docs/records/three_weeks.json)

## Friction
- reuse: [local: rebuild, boot model and records are today's shared code; boot_check wraps nextboot.check]
- retries: [local: the recolour guard failed on a stale colour_inputs; refreshed in the profile]
- environment: [local: full verify ~45 min detached (setsid); a selftest's stamp hashes the tree at its start, so no edits while it runs]
- hand-rolled: [local: per-commit engines.py and views written by a scratch script so each commit holds one game]
- scratch: [none: scratch build and negative scripts dropped; the negatives are in auto now]

## Technique use
- optimise.pattern-cache: helped: patterns built once from the game's bytes, keyed on a hash, survive in-place changes.
- verify.update-locked-pace: helped: input and captures by game update made the +0.15% measurable.

## Stage log
- 2026-11-04: imported into the repo (refactor phase 7): rebuild = the published v1.0, record pinned, full verify stamped. 0 user rounds.
- 2026-11-03 night: go-behind by whole items after the owner's play (split plants); 37 items, 16 rooms. 1 user round.
- 2026-11-03 evening: outline margin (88d3f7a) checked and packaged; go-behind scenery in 14 rooms, survey of all 37. 0 user rounds.
- 2026-11-03: rebuilt on the 128K release in one session, reusing the 48K engine's method, verifier and hook logic. 0 user rounds.
