"""Winter Sports, Speed Skating (event 3): the 28 MHz draw with the original's cadence (winter_sports_pace). GPL-3.0-or-later. Notes: games/winter_sports_speed_skating.md.

The main loop (0x841E DI ... 0x848F EI ... JP NZ,0x841E at 0x84F1; about 8.8 frames per update in the original) draws the two skaters' panes with one block-copy
routine, 0x8BFE (78,600 T per call), from 0x84C3 with interrupts on (the loop's DI region ends at 0x848F). The call becomes the wrapper of
winter_sports_common.draw_wrapper with one halt (the logic is most of the 9.1 frames of an update; one halt gives 9 +- 1). The wrapper sits in 0xC390-0xC3BF, a 163-byte zero
run of the tape block that stays zero through the whole flow; the mode byte ("Original pace") at 0xC3C0. The race starts when SPACE is pressed on the ready screen
(the loop at 0x8415 polls port 0x7FFE bit 0), then the skaters are driven by alternate key presses."""
from .winter_sports_pace import PaceEvent, Site

HALTS = 1
SITES = [Site(0x84C3, 0x8BFE, halts=HALTS)]
_ALT = [(2400 + i * 12, 2408 + i * 12, 'Q' if i % 2 == 0 else 'A') for i in range(120)]
_PRE = [(1500, 1530, '1'), (1600, 1630, 'K'), (1700, 1730, 'Q'), (1770, 1800, 'A'), (1840, 1870, 'O'), (1910, 1940, 'P'), (2000, 2030, '3'),
        (2100, 2160, 'S'), (2300, 2330, 'SPACE')]
_E = PaceEvent(__name__, 3, SITES, wrap_at=0xC390, var_at=0xC3C0, menu_key='6', keys=_ALT, frames=1500, pre_frames=2400, prefix=_PRE)
INDEX, BANKS = _E.INDEX, _E.BANKS
patch_event, disable_code, tests = _E.patch_event, _E.disable_code, _E.tests
