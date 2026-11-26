"""Winter Sports, Ice Hockey (event 1): the 28 MHz draw with an even cadence (winter_sports_pace). GPL-3.0-or-later. Notes: games/winter_sports_ice_hockey.md.

The rink is redrawn in full by one routine, 0x7809 (a scrolled copy of the rink through a back buffer, 423,000 T = 6 frames per call at 3.5 MHz), from two places in
the main loop: 0x7FC1 (every update) and 0x8063. The loop is free-running (about 9.7 frames per update in the original), so each call becomes the wrapper
of winter_sports_common.draw_wrapper with N halts: the drawing runs at 28 MHz (0.75 frame) right after the frame interrupt and the halts bring the update interval back to the
original's mean (N chosen by measurement, winter_sports_pace tests: mean within 8 %). The wrappers sit in 0xF42A-0xF4F3, a 202-byte zero run of the tape block that
stays zero through the whole flow; the mode byte ("Original pace") at 0xF48A."""
from .winter_sports_pace import PaceEvent, Site

HALTS = 5
SITES = [Site(0x7FC1, 0x7809, halts=HALTS), Site(0x8063, 0x7809, halts=HALTS)]
_E = PaceEvent(__name__, 1, SITES, wrap_at=0xF42A, var_at=0xF48A, menu_key='4',
               keys=[(2300, 4000, 'Q'), (2700, 2760, 'O'), (3000, 3100, 'P')], frames=1700, pre_frames=2290)
INDEX, BANKS = _E.INDEX, _E.BANKS
patch_event, disable_code, tests = _E.patch_event, _E.disable_code, _E.tests
