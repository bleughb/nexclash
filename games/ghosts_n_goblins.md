# Ghosts 'n Goblins (Elite, 1986, 48K) - engine gng, .nxc 1.6 (Jon Attree's .nxc work)

## Next session
Stage: 5 (published as .nxc 1.6 on jattree/nxc)    State: engine imported 2026-11-06; graphics read from the player's game.
Techniques: detect.gameplay-screen-readers

## In this repo (2026-11-06)
- Engine gng (nexclash/gng.py, gng_art.py, asm/gng_hooks.asm + gng_r_table.inc, profile ghosts_n_goblins; slot-1 RAM
  hook page over the alt ROM: patch.ram_slot1_after_alt). Builds: sprites 34c14267, enhanced 4a76d9bf; each = the
  published .nxc 1.6 --bare (default / Enhanced) apart from the NEX loading-screen block the packager adds.
- No game graphics are stored. docs/profiles/ghosts_n_goblins_graphics.json lists the 315 figure images by id
  (SHA-256 of kind + rows + bytes, 20 hex digits) and source: the snapshot at an address (230), a reference
  recording at a frame and address (c0, c2, c10: 66), or a slice of a parent image (19). gng_art.catalog() reads
  them from the player's game at build time and refuses any that does not hash to its id. auto reads the
  recordings beside the snapshot (or given with --rzx); without them, the reference folder as selftest finds it.
- The Enhanced map (ghosts_n_goblins_colours.json, the owner's painting) is keyed by image id and byte offset with
  its check values null; gng.fill_checks puts each image's own byte back at load. After importing a repainted
  sheet run gng.strip_checks on the map before committing.
- verify includes the 1.4+ checks the published build was proved with (nexclash/gng_verify.py, from the pilot's
  movement01/verify_smooth.py and ground01/verify.py): the Copper commit of full positions, intermediate positions,
  the carried item clipped at its zombie. Without them the base checker fails every tick on the Copper writes.
- RECOLOUR's guard runs on the Enhanced build (an empty map builds with the default palette, as recolour).
- The cheats (v1.5 / v1.6: invincibility, level 2 / 3 start, always the dagger, infinite time) are .nxc trainers
  from the archive's .pok; they live in the .nxc, not here.

## Lessons
- [local: a build that needs game images it cannot find in the snapshot can name where they appear instead]
  content ids plus snapshot / recording / parent sources made the catalogue byte-free with the same output.

## Friction
- reuse: [none: rzx.scan and the content ids already existed]
- retries: [none: every image was found in the first three recordings]
- environment: [none: the pilot venv and references as for the other imports]
- hand-rolled: [none: one catalogue converter, run once, not kept]
- scratch: [none: the converter stayed in the session scratchpad]

## Technique use
- detect.gameplay-screen-readers: helped (the plot loops' own reads are the only screen readers).

## Release notes (from the .nxc work)

v1.5 is v1.4 plus cheats. It is packaged and **not yet played by the owner**. All evidence is from the simulator and headless JNext (v2.09 card, read-only). Nothing ran on hardware, and nothing was pushed or published.

**For Jon to test:** `out/ghosts_n_goblins_v1.5-menu.nex`.

| File | MD5 | SHA-256 |
|---|---|---|
| `out/ghosts_n_goblins_v1.5.nxc` (98,783 bytes) | `2236916f8b5ed5607da3e17d416e2212` | `88f7fa900f64cd94e50d5485717bb3fb3924f1c26b2586f98e1fe6791a83d59b` |
| `out/ghosts_n_goblins_v1.5-menu.nex` | `e721a886090e86cb14dd4774eca0ec53` | `ba67b8b8dd11e0f70a3d8a09444839d62f6ffd3ba7c94095f25592224dc0753c` |
| `out/ghosts_n_goblins_v1.5.nfo` | — | `96b0ef480725fd5c96a38349294e3896506881b8045f43c8ccf4a8a8ae8dd2b5` |

The v1.4 files are unchanged; `package15.py` hashes them before and after. The v1.5 .nxc was made from the v1.4 .nxc by `import_pok`/`set_*`/`set_help`. Those calls keep the nonce and the encrypted blocks and change only the clear text blocks (TRN1, INF1, PRF1, HLP1). Version 1.5, credits as v1.4, tested "not yet played by the owner".

## Menu (8 lines)

1 Infinite lives · 2 Infinite time · 3 Invincibility · 4 Start at level 2 · 5 Start at level 3 · 6 Always the dagger · 7 Colour clash fix · 8 Enhanced colours. Every trainer is off by default, and each one has a help line.

## The game's structure (from the code)

`0xBFA7` is a section number, not a level. Its values:

- 0–3: map 1 (graveyard, town, water…)
- 4–7: map 2 (towers)
- 8–11: map 3 (caves)
- 12: the intro

So the Spectrum game has **three levels**. Each one has a mid-map checkpoint (2, 6, 10) and a boss section:

- 3: one boss.
- 7: two bosses.
- 11: two final bosses, then the princess.

Map-cell type `0x15` (handler `0xA46A`) sets the next section. A map start (section AND 3 = 0) resets the map position `0xBFA8`. A mid checkpoint adds to it.

The v1.4 "six level starts via fixtures" were section bytes, not levels:

- c6 dies at once (section 6 needs a map position).
- c2 and c10 start in the wrong place.

The v1.5 coverage text says this.

## Cheats

| Cheat | POKEs (decimal) | How it works |
|---|---|---|
| Infinite lives | 36057=182 | Unchanged from v1.4. `DEC (HL)` on lives becomes `OR (HL)`. |
| Infinite time | 38295=110, 38296=149 | **Changed from v1.4.** The time-out `JP Z,0x8CD6` at 0x9596 becomes `JP Z,0x956E` (an existing `RET`). In play the clock loops in its last minute: 0:00 is followed by 0:58. |
| Invincibility | 35118=24, 35119=45 | At 0x892E, `LD (IY+22),5` becomes `JR 0x895D` (the handler's own no-damage exit). Details below. |
| Start at level 2 | 33142=4, 25197=10 | Details below. |
| Start at level 3 | 33142=8, 25197=12 | Details below. |
| Always the dagger | 25182=2, 34633=58 | Details below. |

**Why Infinite time changed.** v1.4's POKE (38303=0) NOPs the `DEC` at 0x959F. The title screen uses the same routine to count down before it starts a game (49074 bit 5 set, then 0x9599 jumps to 0x8C9E), so with v1.4's Infinite time on **the game never starts**:

- Simulator: the title stayed up for 6,000 frames with 0 pressed repeatedly.
- JNext: 0 player updates in 2,000 frames.
- See `work/cheats15/JN_TIME_V14_TOP_V15_BOTTOM.png`.

The fix still lets the title's countdown run. In play, the time-out path just returns.

**Invincibility.** The collision code at 0x88D8 still does the following:

- Runs the box test.
- Sets the 80-update contact immunity (0xBFB3).
- Handles the key (type 88), which completes the level.
- Handles a zombie that has not emerged yet (type 76).

For any damaging contact it skips the hit. There is no armour strip (0x8940), no death flag (0x893E) and no knockback. That covers enemies, projectiles and bosses, because they all use this path. **Falling into water or a pit still kills.** That check is at 0x831B: Y≥141 jumps to the life-loss code. Removing it would leave Arthur falling off the map. With Infinite lives, a fall costs nothing and play restarts at the checkpoint. The time-out is covered by Infinite time.

**Start at level 2 / 3.** After the intro, 0x8170 normally runs `LD A,0` (operand 33142), stores it as the section, sets the new-stage flag and runs the game's own new-map start (0x8E4A), the same path the level-end key takes. The trainer changes:

- The `LD A,0` operand to 4 (level 2) or 8 (level 3).
- The new-game value of 0xBFE7 (operand 25197; it is read for enemy types 70/82) from 8 to 10 or 12.

0xBFE7 goes up by 2 at each map start, so it then equals a natural first-loop arrival (12 or 14).

What else to know:

- **Lives:** 9, the same as a normal start.
- **Mid checkpoints:** not offered. They need the accumulated map position, which a new game clears.
- **Both level trainers on:** level 3 wins, because the later trainer's bytes overwrite the earlier one's.
- **Game over:** a new game starts at the chosen level again.
- **After the ending:** the next loop also starts at the chosen level. This is not a softlock.

**Always the dagger.** The weapon is 0xBFB5: 0 torch, 1 lance, 2 dagger.

- New-game weapon (operand 25182): 1 becomes 2.
- The pickup's `LD (0xBFB5),A` becomes `LD A,(0xBFB5)`, with the same length and the same 13 T-states. Pickups are still collected and their redraw still runs, but the weapon stays.
- Starting with weapon 0 (torch) crashed the simulator, so it is not offered.

**Keep armour:** skipped, because Invincibility covers it.

**Final boss / ending.** Nothing in the code needs a particular weapon:

- A shot hit does `DEC (IX+13)` per hit for every weapon (0x8869).
- Killing boss types 84/70 counts down 0xBFD7. It starts at 2 in sections 7 and 11.
- In section 11 the last kill spawns the princess instead of a key.
- The ending fires at 0x9658 when the countdown is 0 and Arthur stands at the princess. This sets 0xBFD8 bit 5, then 0x8E43 jumps to 0x61B6 ("PRINCESS SAVED").

There is no shield or cross rule in this port. The cheats do not touch this path. Invincibility jumps after the key and princess checks, and the dagger hits like any weapon.

**Not proven: no run reached the ending.** The 15-minute JNext soak, with the dagger, reached a room with two red devils and the princess. That looks like the final-boss room, but the section byte was not logged there.

## Proof

**Host** (`host15-out.json`, on the shipped file):

- With the new cheats off, both sets are byte-identical to v1.4: Default `3593b326…` and Enhanced `67213e1b…`, the shipped v1.4 NEXes. With Infinite lives on, both sets also match v1.4.
- With Infinite time on, 3 bytes differ, as intended.
- Each cheat alone changes exactly its own bytes.
- All 64 trainer combinations × 2 sets apply.
- `apply_menu` of v1.4 still rebuilds `ef5b86f5…`.

**Lockstep replay, cheats off** (`proof-off-*.json`): 11 recordings, 53,063 frames per set, IDENTICAL. The counts are the same as v1.4's: 331,570 patterns, 139,028 object hooks, 24,209 Copper commits.

**Lockstep replay, cheats on** (`proof-*.json`): 9 cheat recordings, 43,030 frames per set, IDENTICAL, with every hook counted (126,195 object hooks, 19,446 Copper commits). The recordings:

- invincibility, 6,000 frames
- infinite time, 13,000 frames
- level 2, level 3
- level 1/2/3 look-ahead bots
- dagger
- all cheats, 6,000 frames

**Negatives:**

- `negative15.json`: the 34 v1.4 engine controls, replayed on the cheat recordings. **34 of 34 caught.**
- `neg15.json`: 5 new cheat controls (recording with the cheat bytes put back) are all caught. The 5 matching positive controls are identical.

**Simulator behaviour** (`simtest-*.log`). Invincibility over 6,000 frames:

| | Contacts | Armour lost | Deaths |
|---|---:|---:|---:|
| On | 7 | 0 | 0 |
| Off (same input) | 12 | 7 | 6 |

Infinite time and Invincibility together: 13,000 frames, the clock looped twice, no life lost.

**JNext** (`jn15*.json`; the counters count executions of the game's own code). Invincibility over 6,000 frames:

| | Hits absorbed | Armour strips | Deaths | Lives lost |
|---|---:|---:|---:|---:|
| On | 11 | 0 | 0 | 0 |
| Off | 12 | 6 | 6 | 6 |

The other JNext runs:

- **Levels:** level 2 (towers, Enhanced) and level 3 (caves) start cleanly with map, enemies and timer, and scroll past the first screen.
- **Dagger:** with the simulator's exact input, 1 pickup and the HUD stays the dagger in all 8 shots.
- **Menu:** the shipped menu .nex, keyed 3 and 5 on its menu, then ENTER, starts level 3 with 8 hits absorbed.
- **Soak:** all cheats except level 2, 45,000 frames (15 minutes):

| Hits absorbed | Armour strips | Deaths | Lives lost | Player updates | Pickups |
|---:|---:|---:|---:|---:|---:|
| 174 | 0 | 0 | 0 | 18,525 | 2 |

  Player updates rose in every 1,000-frame window, so there was no freeze.

**Flicker** (warn-only):

| Build | Scene | Out-of-step frames |
|---|---|---:|
| All-cheats v1.5 | level 3 scroll | 9 |
| Cheat-free v1.4 engine (c8 fixture) | level 3 | 4 |
| v1.4 | level 1 | 0 |

The cheat-free v1.4 engine shows the same warning in level 3, so it is a pre-existing engine/scene issue, not caused by the cheats. It has not been looked at before; it is in `jn/cheats15/flicker*/strip.png`.

**Pace:** with every cheat off the build is v1.4 byte for byte, and v1.4's pace measurements apply. The cheats add no code to any per-frame path:

- Invincibility skips work.
- The time fix changes a branch target on the once-per-time-out path.
- The dagger swaps a 13 T-state store for a 13 T-state load.
- The level POKEs are new-game values.

There was no new pace trial.

## PNGs viewed

All in `work/cheats15/` unless stated otherwise:

- `JN_INVINCIBILITY_HITS.png`: six contact frames plus two later frames; Arthur overlapping zombies in armour, lives 9.
- `JN_TIME_V14_TOP_V15_BOTTOM.png`
- `JN_LEVEL2_TOP_LEVEL3_BOTTOM.png` and `JN_LEVEL2_TOP_LEVEL3_BOTTOM_LATER.png`
- `JN_LEVEL3_WALK.png`
- `JN_DAGGER_HUD.png`
- `JN_MENU.png`
- `JN_SOAK.png`
- `sim-level2.png`, `sim-level3.png`
- `beam-level2*.png`, `beam-level3.png`
- `inv-walk.png`
- `jn/cheats15/flicker/strip.png`

## Open items

- **The nfo line.** The public tool `make_nfo.py` always writes "Cheats come from the archive's POKEs". `package15.py` replaced that one line in our .nfo, because only Infinite lives is from the archive. The tool needs a field for this; it was not edited here.
- **Level 3 out-of-step flicker.** The warning above, pre-existing in the engine.
- **Not covered:** the ending, mid-map checkpoint starts, joystick and hardware.
- **Doc cleanup.** The archive .pok's "forget all problems" entry does not match this dump. It writes `JP 0x60A3` (a re-encode-and-jump-to-0x8003 routine), so it was not used.

Scripts: `work/cheats15/{make15,package15,host15,simtest,beam,proof15,neg15,negative15,jn15,jn15b}.py`.

## v1.6 (6 November 2026): the water platform and the dagger cheat

Owner report on v1.5 in JNext: the moving platform over the level-1 water "glitches and seems to lack the detail".

- **What the platform is.** Not a figure and not a band-redraw tile: an object drawn straight onto the ULA by its own routine (0x9480, then 0x8EFA / 0x8F84 / 0x8FFB for the clipped edges). It uses four pre-shifted drawings, one per 2-pixel phase, at 0xC0B0, 0xC1B0, 0xC2B0 and 0xC3B0 (48 bytes each: 8 row pairs of edge, fill, edge). The engine does not touch it. In the original game it is a solid green block with drips: each row is one repeated fill byte, so there is no finer detail to restore.
- **The glitch.** Caused by v1.5's Always-the-dagger cheat. The weapon routine 0x67B9 pushes AF four times and pops it three times; outside the intro the fourth is popped at 0x6815 for the HUD icon, but in section 12 (the intro) `RET Z` at 0x67F9 returns through it. With weapon 1 that address is 0x3828 (a harmless ROM gadget, the known stray). With the cheat's new-game weapon 2 it is 0x6020 (A = 40*2+16, F = 0x20): `RST 38`, then `LD BC,8 / LDIR` copies 0xC288..0xC28F over 0xC1B0..0xC1B7, the phase-1 platform drawing, and runs the high-score swap at 0x6026. From then on, every fourth 2-pixel step of the platform showed a dashed top line and a stray dash. Without the cheat the drawings are never written.
- **Fix (trainer only).** Always the dagger now also NOPs the fourth `PUSH AF` (26572: 245 to 0) and replaces `POP AF; LD E,A` at 0x6815 with `LD E,$60` (26645: 241 to 30, 26646: 95 to 96), the value that pop always gave for the dagger. The stack is balanced, the intro returns normally and nothing is copied. Other cheats and the cheats-off build are unchanged (cheats off = v1.4 byte for byte).
