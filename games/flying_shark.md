# Flying Shark (Graftgold / Firebird, 1987, 48K)

## Next session
Stage: 3 (review build, not played). Hardware: untested. Review build v1.0 for the owner, not published; not yet wired into `auto`, `engines.py` or a record: that comes when it goes upstream after he has played it.
Inputs: Flying Shark (1987)(Firebird).z80, MD5 c545645a8688f24428492937125fbfcd, a 48K loader snapshot at PAUSE 0.
Build: `flying_shark.build(z80, nex)`. Checks: run from the private review folder (runs/flying_shark/release-20261108/work: v1.py, neg.py, beam.py, final.sh); nothing here needs them to build.
Pending: the owner's play; hardware checklist; whether he wants the outline at all, and Enhanced (mock-up only).

## Facts
- No 128K release in the archive: every Flying Shark dump is 48K with beeper sound. The target's header says 48K + Interface 1; no Interface 1 use.
- The snapshot stops in ROM at the loader's PAUSE 0 with the game packed (9E86: word zero run, word literal run). Sites go in the packed stream's literal bytes (`stream_map`), so the game unpacks with its hooks in place. Tail at 7000, in a 16,005-byte zero run the unpack writes over.
- Everything runs in the 25 Hz handler (A0C4), interrupts off: 88,900 T of blit (C772, a whole play area from cell pointers, contended) among 130,000 to 175,000 T. Over two frames, the next interrupt waits for a third: the game's pace is that step, 2 or 3 frames an update.
- Figures are plotted into copies of the cells they touch, by threaded steps (table A000), with pointers replaced: C84C rebuilds the list, AC8D plots, the next update's C772 shows them.
- The plot pass beeps as it goes (OUT FE per actor): it must stay at the caller's clock.
- The play area is monochrome by level; attributes change only for flashes. No colour clash to fix.
- The screen shows lines E - 24, up to 183 + the fine scroll (9C00).

## Decision
Owner's standard: where the play area is monochrome, keep the look, claim no clash fix; figures lost against scenery may get the standard outline. They are lost here. So: the ULA bitmap and attributes untouched, a white one-pixel ring on a double-buffered Layer 2, none on 8-line plots (bullets).
- Layer 2, not sprites: 8 to 20 plots an update of up to 26 x 18 pixels, each shape in several shifts, would churn the pattern memory.
- The ring comes from each plot's own mask and data, by its step's flip rules. The two-stage plots (a first stage with a second to come) are one figure: the second gives the ring.
- Each graphic's ring is a pixel list made once and kept in Next pages (RAM only). 50,000 T at 28 MHz for a list against about 7,000 T a figure once made; the first cell-by-cell version lost 3-frame updates in busy scenes (+12.6% busy third, +41.7% worst stretch).
- No punching: a ring stays over a figure drawn later. Rare, small, and it cost the time above.

## Known issues
- Ground guns and buildings are part of the map: no ring.
- A ring stays over a figure drawn later where two overlap.
- With list pages full (46 pages, not reached in any run) new shapes would go without a ring.

## Evidence
See the review run's NOTES.md (runs/flying_shark/release-20261108): pace, replay with R, negatives, soak, flicker, beam audit, loader. JNext 1.1.104 and simulator only; nothing has run on a Next.

## Hardware checklist
Nothing has run on a Next. To check: the flip below the play area and the blit at 28 MHz (JNext's so far); that updates keep their 2 and 3 frame beat; the beeper; the real loader; 1MB Next.

## Technique use
- patch.pace-limiter: used: the blit runs whole at 28 MHz in a window of its original time.
- patch.preserve-r: used: R compared at every hook and in the ABI cases.
- patch.restore-speed: used: the caller's clock restored after every hook; a negative catches it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the whole alt ROM; veneers clear of the ROM the BASIC loader runs.
- patch.display-atomic-switch: used: the Layer 2 flip happens below the play area, checked by the beam audit.
- verify.update-locked-pace: used: lockstep pace runs on an immunity fixture.

## Lessons
- [local: packed snapshot] A loader snapshot holding the game packed takes its sites through a map of the stream's literal bytes; the .nxc's banks stay close to the .z80's, where a build from a state after the unpack would not fit the site table.
- [local: archive POKEs] One entry of the archive's .pok is an address in the packed snapshot (54462, lives), the rest are live addresses that the unpack overwrites: tested on the real game, translated through the stream map.
- [local: pace step] When the handler overruns two frames the update takes three: a small time difference near the line moves whole updates, so the blit's window has to be right to within a few hundred T.
- [local: no sim timing] The simulator's T is not JNext's (140,000 against 131,000 T a handler here): the toolkit's frame length needed 72,000 T to give the 2-frame beat, and death paths starved; POKE tests moved to JNext.
- [local: pixel lists] Cached per-graphic pixel lists beat recomputing rings by a factor of 7 at 28 MHz, and clearing by replaying the list beats a rectangle.

## Friction
- reuse: [none: the shared pace and hook libraries were enough]
- retries: [local: draw speed] Three versions of the draw before the busy scenes held pace; the pace tool found it.
- environment: [none: the pilot venv was enough; other agents' load only made some runs slower]
- hand-rolled: [local: review scripts] Pace, soak and loader runs were driven by scripts in the review run, not the toolkit.
- scratch: [local: review run] Its work folder stays in private evidence.

## Stage log
- 2026-11-08 Stage 3: review build, outline on Layer 2, proofs; not yet played by the owner.
