# Finders Keepers (Mastertronic, 1985; 48K, Magic Knight 1) - engine `finders_keepers`

## Facts
- Snapshot: Finders Keepers (1985)(Mastertronic)[Magic Knight 1].z80 (TOSEC), in game at the menu (8 = play), IM 1.
- One plotter 0x9A05 for the five figures (0 the Knight, 1-4 the room's creatures; the enemy loop at 0x75C7 plots
  5 - B). Table 43632, 8 bytes: x, y, frame, ., dx, dy, colour, mask. A call XORs the old image (entry frame at the
  entry place) with the new one (frame 41328 at 41329, 41330), then writes the entry back (0x9CD0). Frame f is
  16 x 16 at 43696 + 32 f (the plotter walks it backwards from 43727 + 32 f); frame 0 is blank, so a first draw and
  an erase are the same call.
- Attribute painter 0x9CD9 (called at 0x9A3E): cells = (attr AND mask) OR (colour AND NOT mask), skipped where the
  room map at 43197 is set. The Knight 0x47/0xB8, creatures 0x0n/0xF8; the spinning axe and the dragons sometimes
  0x28/0x00 or 0x00/0x00 (whole cells: black on cyan, blacked out).
- Room set-up 0x7A26 (8 callers) copies the room's four entries; 0x88F7 zeroes every frame before a full-screen
  window (0x7818); room number 41656; 0x703F starts a life in that room. Strength 41530 (72), hit routine 0x8579.
- Readers of the screen and attributes: the plotter's own XOR, LDIR fills, the painter: the game never reads figure
  pixels or colours back.

## Decisions (defaults; whole-cell figures kept as drawn)
Every figure with its own ink becomes sprite n over its own pixels in its ink (BRIGHT from the entry, or from the
cell when the mask keeps it); the painter is skipped for it. A figure whose mask is 0 or keeps the ink stays as the
game draws and paints it. Rooms, panel, text stay on the ULA.

## Results (2026-11-21)
Recordings (machine-played, the toolkit recorder): fk_s1/2/3 (exploring, seeds 1-3, 12,000+ frames each) and
fk_rooms (rooms 0-22, 600 frames each, room poked, entered at 0x703F with the Knight's frame 0 as the game's own
callers do). Verify IDENTICAL on all four (52,127 frames, 16.3M sprite pixels); unit tests 6,912 pass; negatives 8/8.
Tang board: loads with automap on and 124 leftover sprites, plays. OverSpec from the .nxc menu: plays.
Verifier limits, counted: a segment snapshot taken inside a plot, or in a transition, leaves that figure unchecked
until the next room set-up.

## Next session
Record + stamp (selftest), PR with the other toolkit branches, reference files to specnext.
