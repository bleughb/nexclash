# Everyone's a Wally (Mikro-Gen) - engine `wally`

48K game in a 128K snapshot. Code: nexclash/wally.py, asm/wally_hooks.asm,
docs/profiles/everyones_a_wally.json (regenerate the hook hex after any .asm edit).
Reference: reference/wally.z80 (World of Spectrum snapshot) + wally.rzx (Dean's wallyrzx.rzx;
to be uploaded).

    python nexclash.py auto wally.z80 --rzx wallyrzx.rzx

| Output | MD5 | Status |
|---|---|---|
| wally.nex (plain, tail 0x6B00) | 2e615b3e7ae995e6d6a6ed9e3f586d4d | boot sim OK |
| wally_sprites.nex (altrom stubs + RAM page 26) | f7605489c3af55b8e8c6a580c1c26150 | RZX IDENTICAL, unit tests PASS; BOOTS AND RUNS on hardware 2026-09-29 (detailed checklist not reported) |

## Dean's decisions
- Every character a sprite. Plotter A (five gang members, 2 sprites each) and B (masked 16x16
  objects/enemies) -> sprites; C (OR-only) stays on the ULA.
- Colours: A = own attribute ink; B = 61329 colour if painted, else ink of the attr-buffer cell
  under its centre; outline black; palette offset = ink + 8*bright.

## Next resources
RAM page 26 at slot 0 during hooks (code 0x0100, SPRTAB 0x1800, NIBTAB 0x1A00, PALMAP 0x1C00),
alt ROM stubs 0x386E (95 bytes), patterns double-buffered (0-31 / 32-63), clip Y 64-191, tail
0x6B00. Commit at 47637 (after the pixel copy).

## Game facts
- wally.z80 (World of Spectrum): 128K snapshot, 7FFD=0x10 (ROM1, bank 0), PC 46319 = control menu
  (keys 1-3 select input, 4 starts). Never writes 7FFD, beeper only, never reads the ROM.
- Render (47574): restore back buffer 0x6B00-0x7AFF (lines 64-191, 32 bytes/row, row y at
  0x6300+y*32) and attr buffer 0xFC00-0xFDFF (cell at 0xFB00+(y&248)*4+x/8) by LDI, plot, then
  47611 copies pixels via row table 33400 (unrolled LDI 47653), 47637 copies attrs. ~1 render per
  2.8 frames. 0x5B00-0x7AFF is write-first from the menu (printer buffer is used).
- Plotter A 45286 (callers 47597, 61487, 61887): IY = 48231..48235 (5 descriptors, stride 1:
  +0 frame 0-7, +5 x, +10 y, +15 room, +30 attr, +35/+40 gfx base); 16x32, 128 bytes/frame
  (mask L, mask R, gfx L, gfx R per row); self-mods 45353/45381 (x&7+1), 45449 (x&7), 45435 (x/8);
  paints (IY+30) into 2-3 x 4-5 attr cells. gfx rebuilt by the mirror routine 33251 (table 0x7B00).
- Plotter B 43168 (21 callers): A = frame, gfx 33656+A*32, 16 rows x 4 bytes, pos (43064/43065);
  self-mods 43232/43260, 61359 (x/8). PUSH AF on the game stack; no DI.
- Plotter C 43069 (15 callers): DI first, OR-only 16x16 (2 bytes/row), same gfx block.
- 61329 (5 callers): paints the last B/C plot's cells with (62063); 58153 = box collision.
- RZX ranges: A x 0-240 y 64-160; B x 0-240 y 64-168; max per render 5 A + 3 B + 4 C.
- Interrupts off at every hook site in the RZX. Tail 0x6B00 (back buffer, write-first).

## Verification (detail: docs/VERIFICATION.md)
wallyrzx.rzx (11 autosave snapshots stripped): 15,225 frames, A 4,299 / B 1,058 plots converted,
3,938 commits, max 12 sprites, 1,913,362 sprite pixels - IDENTICAL. Unit tests: 2,664 plot cases,
3 commit cases, negative control detected 12/12.

## Known differences / open
- Sprites always in front of C objects and ULA scenery (the original draws by call order).
- B colour for unpainted objects is an approximation (the original mixes cell inks).
- Outline black even on non-black paper.
- Character switching not recorded (all five descriptors were still exercised).

## Hardware checklist
1. Menu: keys 1-3 select input, 4 starts; beeper sound unchanged.
2. Gang member: two sprites, own ink colour, black outline, animates, no clash.
3. Masked objects/enemies as sprites; OR-only objects still on the ULA.
4. Room changes / screen edges: no stale or torn sprites; nothing drawn above line 64.
5. Faults: Fuse "Record from snapshot" on wally.z80, autosave off, send the RZX.
