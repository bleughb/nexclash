"""Winter Sports, Biathlon (event 5): the 28 MHz draw (winter_sports_pace). GPL-3.0-or-later. Notes: games/winter_sports_biathlon.md.

Each update (about 11 frames in the original) calls two drawing routines in a row from the main loop: 0x81E8 (`DI`, set-up, the 152,000-pixel-byte block copy 0x80FD at
78,000 T, `EI`, `RET`) at 0x8270 and the attribute copy 0x8202 at 0x8273. Both become wrappers (winter_sports_common.draw_wrapper): the first halts once to the frame
interrupt and runs 28 MHz; the second only runs 28 MHz. The wrappers sit in 0xACAE-0xAD0D, a 5,206-byte zero run of the tape block that stays zero through the whole flow;
the mode byte ("Original pace") at 0xAD0E. The race starts when SPACE is pressed on the ready screen (the loop at 0x89B1 polls port 0x7FFE bit 0), then the skier is driven by
alternate presses of the two ski keys (O and P in the test script)."""
from .winter_sports_pace import PaceEvent, Site

SITES = [Site(0x8270, 0x81E8, halts=1), Site(0x8273, 0x8202, halts=0, mark=False)]
_ALT = [(2400 + i * 14, 2410 + i * 14, 'O' if i % 2 == 0 else 'P') for i in range(110)]
_PRE = [(1600, 1630, 'K'), (1700, 1730, 'Q'), (1770, 1800, 'A'), (1840, 1870, 'O'), (1910, 1940, 'P'), (2000, 2060, 'S'), (2300, 2330, 'SPACE')]
_E = PaceEvent(__name__, 5, SITES, wrap_at=0xACAE, var_at=0xAD0E, menu_key='8', keys=_ALT, frames=1500, pre_frames=2400, prefix=_PRE)
INDEX, BANKS = _E.INDEX, _E.BANKS
patch_event, disable_code, tests = _E.patch_event, _E.disable_code, _E.tests
