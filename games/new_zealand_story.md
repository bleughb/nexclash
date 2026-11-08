# The New Zealand Story (Ocean, 1989, 128K) - colour v1.3, built from its tapes (engine new_zealand_story)

## Next session
Stage: 5 (imported; rebuild byte-exact)    State: engine + record on main's tape-set inputs (nexclash/tapeset.py); the
four published v1.3 builds (v1.2 + the v2.10 start-up fix) rebuild byte for byte from either tape set; no RZX
verifier in the engine (the proof is the run folder's replay suite, below).
Start with: "Open" - the replay proof as this engine's verify().

## Inputs (the first tape-set game)
- Start state = the record's snapshot: the 128K game loaded from Side A in an emulator, world 1 in memory, 500 frames
  into the title (port 7FFD bank 0, SP 0xFFFC); md5 737d576c. It is what `auto` detects (profile signature) and what
  the stub starts. The worlds the game loads later are not in it.
- Tapes = `inputs.tapes`, two alternative sets, each in order: Side A .tap (d5f47d90) or Side A .tzx (b0711e0d), then
  Side B .tzx (f1c1ee16; world block 37, 'M@', is on Side B only). The same releases the published .nxc accepts.
- Build: `python nexclash.py auto new_zealand_story.z80 --no-record --tape SIDE_A.tap --tape SIDE_B.tzx`. The engine
  checks the tapes against the profile's tape_sets (wrong order, unknown file, none given: refused with what it wants)
  and finds the 37 world blocks by content (header flag 0xAA + sequence, the data block after it), so the .tap and
  the .tzx (different block numbers) give the same bytes.

## Design (the published build, folded into one engine)
- Stage 1, multiload from RAM: the 37 raw world blocks in banks 12-22 (largest first, none across an 8K page),
  headers + directory + loader (asm/new_zealand_story_loader.asm) in bank 11; a 12-byte stub over the game's LD-BYTES
  entry (bank 1 0x11EA, copied to 0x43AF) maps the loader page and returns as a good load would.
- Colour (nexclash/new_zealand_story_paint.py): each level's tilemap from its own map and char set, coloured by
  collision type per world; every figure a painted 4-bit sprite program (rules: body / second colour / ink / outline,
  items solid, mouths filled); hooks in alt ROM image 1 0x2000-0x3FFF (asm/new_zealand_story_hooks.asm) with the 1.1
  speed pass (drawing at 28 MHz, a PAL-line cap before the player update). Toggle "Smooth scrolling".
- Backdrops (v1.2, nexclash/new_zealand_story_backdrops.py, asm/new_zealand_story_backdrop.asm at alt ROM 0x3300):
  Layer 2 320x256 in banks 42-46 behind the sky, one tile set per world varied per stage; tiles in
  assets/new_zealand_story/backdrops (original art by Jon Attree; colour data and tile maps only).
- Nothing of the game is stored: graphics, maps and frames come from the tapes and the start state at build time.
- Kept as published: alt ROM image 1 filled as v1.2 did (NextZXOS's ROM3 + hooks) + v1.3's v2.10 fix-ups: the 11-byte
  ROM3 copy at 0x902C becomes JP 0x9D3B + 8 zero bytes; at 0x9D3B (stub page offset 0x1D3B, its free tail below the
  stub's stack) the copy + z80tonex.rom3_fixup_code (all 11 sites) + JP 0x9037, 197 bytes (_altrom_fill_v210: the
  v2.10 fix's patch_nex layout, so every other stub byte stays at its v1.2 address); the start-up tail in the dead stack below SP in bank 0
  (setup maps page 1 at MMU7 for the copy; the tail writes 7FFD before 1FFD). Both local to the engine; the z80tonex
  functions it wraps are restored after its convert().
- Hooks are assembled at build time (pinned sjasmplus; SETOF / DIR / layout tables come from the tapes), so no hook
  hex in the profile and no asm2profile check (as herbert).

## Results (2026-11-07, emulator and simulator only)
- Rebuild, both tape sets (selftest --game new_zealand_story): sprites 342c8397e811e7e1732db1a469d6e5c5, smooth
  cf5cadc53cbcb22b7e0994e767da0e10, backdrops 679d8c14c0d046b435e581e8cea6bf4a, smooth_backdrops
  f74c3b34a4a1a036c0619815fbc0b389 = the published v1.3 bare builds (nxc.py --bare: default, Smooth scrolling,
  Backdrops, both; 2026-11-07). They differ from v1.2's (70174ecb / 7d9898e8 / d6ccac8f / 891397ef) only in bank 10:
  the 196 stub bytes of the v2.10 fix-up.
- Against the published .nxc with its nxc.py: all 4 toggle combinations x 16 trainer subsets x both targets (128
  outputs) identical between the published patch and one repacked from these four builds with the v1.2 pack steps; the
  four bare builds equal the engine's; the menu .nex with Backdrops on is 805e17c8716897796dec0988c47f8f4e from both.
- Inherited evidence (the run folder, same bytes): v1.1 52 normalized replays / 141,000 frames IDENTICAL, 467 figure
  cases per option, negatives detected; v1.2 34 lockstep runs / 51,000 frames, game state identical, Layer 2 equal to
  the model at 28,780 interrupts, negatives (scroll +1, wrong level, opaque sky) detected; JNext pace, flicker,
  15-minute soak. Hardware: none for 1.1 / 1.2 (1.0 played by Dean Woodyatt).

## Hardware checklist
Menu .nex: Backdrops on and off reach play; worlds 1-5 backdrops line up with the scenery while scrolling (Smooth on
and off); a new life redraws the backdrop; title music and sound unchanged.

## Open
- Verifier: the replay suite (JSON input logs on the run's Next simulator) is not in the engine; verify() /
  unit_tests() say so. Port it, or record RZX for a contract verifier. Colour sheets / recolour: not provided yet.
- Start state from the tapes: only its MD5 is checked; a check that the tapes' bytes sit where it has them is open.
- .nxc from `auto`: not made for tape sets yet (BRIEFING C2 #46); the published one was made with nxc.py make --also.
- Reference files: the start state and both tape sets go in specnext/reference/new_zealand_story/ (record paths).

## Lessons
- [doc docs/ENGINE_CONTRACT.md §Module names] A game whose build reads its tapes: snapshot = the emulator start
  state, tapes = inputs.tapes alternative sets in order; `auto --tape`; every set must rebuild the same outputs.
- [tool nexclash.tapeset] Tape reading (.tap / .tzx data blocks as the .nxc format counts them) and set matching are
  shared; an engine finds its blocks by content: the .tap and .tzx of one side number their blocks differently.
- [backlog C2 #46] `auto` makes no .nxc for a tape-set build (nxcout skips it); nxc.py make --also does it by hand.
- [deferred Open: reconsider when the replay harness is ported or RZX are recorded] NZS's proof is a JSON-input
  replay suite outside the contract; until then the record is rebuild-only and auto's Result says BUILT, never PASSED.
- [doc docs/LEARNINGS.md §2.4 Recordings (Fuse / RZX)] Importing a build made on an older main: rebuild on main first
  (a shared stub piece had moved: 436 bytes); the engine's wrapper of the start-up tail takes *args and is restored.
- [local: this game's own stub layout] v1.3's v2.10 fix-up was first made by the v2.10 fix's patch_nex on the four v1.2 builds; the engine now
  emits the same layout (_altrom_fill_v210), so the published bytes come from main's build, not a post-build patch.
- [deferred Open: reconsider when a second tape game is imported] Nothing checks the start state came from the tapes
  (the .nxc TAP1 rule: every 16+-byte run the tapes hold, in place); one more game makes it a shared check.

## Technique use
- patch.whole-altrom-image: no help: the published builds keep the ROM3 fill (+ v1.3's v2.10 fix-ups, local layout)

## Friction
- reuse: [tool nexclash.tapeset] the tape reader and set matcher are shared, written once for every tape game
- retries: [doc docs/LEARNINGS.md §2.4 Recordings (Fuse / RZX)] one TypeError: the run's tail wrapper on main's build_tail
- environment: [none: no workaround needed]
- hand-rolled: [backlog C2 #46] the published-.nxc comparison ran the host nxc.py by hand (repack + 128 combinations)
- scratch: [none: the comparison script needs the host nxc.py and the .pok outside the repo; dropped, result above]
