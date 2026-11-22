"""Winter Sports, Bobsled (event 4): the tear-free fast draw (winter_sports_pace). GPL-3.0-or-later. Notes: games/winter_sports_bobsled.md.

The pane is copied to the screen by one row-blit routine, 0x87E6 (B rows of C bytes, HL = the buffer, A = the first screen row, through the game's row-address
table 0xF590; 28,400 T per call), from three places: 0x7A44 inside `DI / CALL / EI` (the run: one call per update), 0x8446 and 0x8554 (the other phases).
The game paces itself (the update interval runs from 8 frames at a standstill to 2 at speed, by its own delay loops), so no even cadence: each call becomes the
wrapper of winter_sports_common.draw_wrapper (halt to the frame interrupt, 28 MHz copy, 3.5 MHz back). The wrappers sit in 0xC390-0xC41F, a 163-byte zero run of the tape
block that stays zero through the whole flow (menu, options, run, game over: freecheck over 3,300 frames; the zero runs at 0x9E3D-0xABFF DO get written
when the event starts), the mode byte ("Original pace") at 0xC414."""
from .winter_sports_pace import PaceEvent, Site

SITES = [Site(0x7A43, 0x87E6, di=True), Site(0x8446, 0x87E6), Site(0x8554, 0x87E6)]
_E = PaceEvent(__name__, 4, SITES, wrap_at=0xC390, var_at=0xC414, menu_key='7',
               keys=[(2300, 4000, 'Q'), (2700, 2760, 'O'), (3000, 3100, 'P')], frames=1700, pre_frames=2290)
INDEX, BANKS = _E.INDEX, _E.BANKS
patch_event, disable_code, tests = _E.patch_event, _E.disable_code, _E.tests
