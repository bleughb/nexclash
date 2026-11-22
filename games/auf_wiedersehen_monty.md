# Auf Wiedersehen Monty (Gremlin Graphics, 1987, 128K) - new engine

## Next session
Stage 3 (prove + deliver) done 2026-11-22; Stage 4 (hardware + colour rounds) next. First release = clash fix (figures as sprites in the game's own
colours, the attribute paint off) + checked cheats. Inputs (local, not in the repo): rzxarchive aufmonty.rzx
(321,820 frames, a whole playthrough), its snapshot extracted as the verification start; the release targets TOSEC
"Auf Wiedersehen Monty (1987)(Gremlin Graphics Software)[128K].z80" (same code; differences are game state).
Survey: 803dad54 scratchpad aufmonty/survey/. Release: jattree/nxc patch 1.0 (sprite build MD5 6b2c8cd6f621d4f8126fb2e159424607),
  pushed when the owner's quick test passes. Open: an evidence record once the reference files are staged.

## Observed engine (static reading + scan)
- Update routine 41407 (0xA1BF): saves sysvars, EI / HALT / DI, AY music (bank 6), then at 41523 CALL 41645, then
  the cell renderer (41526..): every cell whose map entry (23997 + cell) changed is drawn from its 8-byte graphic.
- Figure loop 41645 (0xA2AD): five records at 42030, 13 bytes (+0 x, +1 y, +2 colour, +3/4 composite pointer, +5/6
  shift entry, +7 frame, +9 bit 7 = drawn as stored, clear = mirrored). Record 0 is Monty (colour 07); an unused
  record shows frame 223 (blank). For each: a 3 x 3 block of composite cells at 33285 + 72 i (column-major, 24
  bytes a column): background cells copied (LDI x 8), the cell map entry set to the composite's code (65 + ...),
  then the 16 x 16 image (0x6000 + frame * 32, top row first) ORed in, shifted to x & 7 (41829 ladder / 41886),
  mirrored through 0xFE00 (bit reverse), masked through 0xFF00 so figure pixels next to scenery ink stay off.
- The clash: 41725 LD (DE),A paints a cell's attribute with the record's colour when the room map (23420 + cell) is
  0 (empty). Nothing restores it but the next room draw.
- Composite cells are read only by the renderer, the drawers' own read-modify-write and the background copy (scan
  0x8205-0x836C, 15,000 frames): no game logic reads figure pixels.
- Clear screen 34894 (pixels 0, attributes 71), callers 33937 / 40850; room draw loop 42871.. (CALL 42940 per row).

## Design (standing default: figures as sprites in the game's own colours, colour paint off)
- Overlay: every pixel write stays; sprite i (one 16 x 16 4-bit) for record i at (x + 32, y + 32), ink = colour & 7
  (+8 BRIGHT), X-mirrored when +9 bit 7 is clear, pattern from the frame image (blank frames show nothing).
- Sites: 41523 CALL 41645 -> CALL e_fig (the loop, then the five sprites); 41725 -> NOP; 34894 LD HL,16384 -> JP
  e_cls and 42878 CALL 42940 -> CALL e_room (hide the five). Set-up: palette, all 128 sprites hidden, the
  snapshot's printer buffer put back (the game reads 0x5B00 before writing it; NEXLOAD overwrote it).
- Start-up tail chosen from the snapshot's state (tail_for): the TOSEC release was taken inside the figure loop at
  figure 2, so the tail goes in figures 3-4's composite cells (0x82DD), copied afresh before anything reads them
  (built vs original: 0 RAM bytes differ after the first loop); the recording's start uses 0x5C7C (write-first).
  The converter's own choice (below SP) landed in composite cells the renderer reads: this renderer uses SP as a
  data pointer.
- Known difference: the sprite shows the whole figure; the game kept figure pixels next to scenery ink off.

## Verification (nexclash/auf_wiedersehen_monty.py)
- An event at every hook: original and patched code from the same state to the call's return (every register but R,
  all RAM but the dead stack); at the figure hook the patched loop must write no attribute.
- Each sprite against its record (expected()); independent truth: every bit the game's drawer ORs into a figure's
  composite cells, placed on the screen from the record, must be ink in that figure's sprite.
- Full recording, 321,815 frames (a whole playthrough), 3,511 s: IDENTICAL. 155,935 figure loops, 571 room draws, 2
  screen clears; 61,119,000 figure pixels covered; 5,840,496 sprite pixels the game kept off next to scenery (the
  known difference); 86,594 attribute bytes not painted. Unit cases 63 ok; 7 broken builds caught (row low, ink
  lost, mirror never set, figure hook silent, clear screen and room draw leave sprites, painter on).
- Pace: figure hook 27,300 T at 28 MHz per update (~3,400 T at 3.5 MHz, about 2.4% of a two-frame update at most).
- Board (Tang, dirty sprites + automap on): the release build loads, menu, plays into the first room, no stray sprites.

## Cheats (archive .pok, each checked against the 128K release's code)
Infinite lives 41139 LD (HL),A -> NOP (the lives store); Harmless aliens 42160 -> RET (the alien test's first
byte); No crushers 47715 -> RET; Harmless water 37002 LD A,7 -> LD A,0; Tickets not required 38896 RET Z -> NOP (the
.pok says 48K version; the same code sits there in the 128K release).

## Lessons
- [local: tail per snapshot] a release snapshot taken mid-routine needs its own tail proof: name the free bytes
  from that state's code (here: composite cells not yet rebuilt) and prove them by RAM equality after the routine.
- [local: tail placement] converter's free-space guess put the 128K tail in the composite cells; the ROM path check
  (reads before writes) caught it: name the tail from `scan` write-first ranges for any game with cell buffers.
- [local: 128K printer buffer] keep_printer_buffer is 48K only; a 128K game that reads 0x5B00 gets it back in its
  set-up (Silkworm / Eagle's Nest pattern).

## Technique use
- detect.gameplay-screen-readers: helped: `scan --writers` on the composite cells showed only the renderer, the
  drawers and the background copy read them, so the overlay keeps every pixel write.
- detect.graphics-record-layout: used: the five 13-byte figure records (position, colour, frame, mirror bit).
- patch.xor-overlay-keep-ula: used: an OR-drawn figure works the same way; the sprite is a superset of its pixels.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the alt ROM image, hooks at 0x386E (the game pages ROM 1 only).
- patch.restore-speed: used: 28 MHz inside each hook, back to 3.5 MHz on the way out.
