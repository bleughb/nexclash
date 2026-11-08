"""The master palette: the Next's standard 256 colours, the one set every colour sheet picks from
(docs/COLOURS.md "PALETTE STANDARD").

Index = RRRGGGBB, the colour the Next shows for that index after a reset (the default palette, and
what NextReg 0x41 writes for any byte). The Next shows 9-bit colour (RGB333); an 8-bit entry's third
blue bit is B1 OR B0, as coloursheet.palette_rgb models. So the master palette is the 256 of the 512
9-bit colours whose blue level is 0, 3, 5 or 7. A 9-bit value written with NextReg 0x44 (two bytes:
RRRGGGBB, then blue's low bit) or a colour given as RGB can be any of the 512.

Forms a palette entry can take (engines use all of them):
  'next8'   int 0-255, RRRGGGBB (PALETTE lists, asm `pal: db ...`): always a master colour
  'next9'   int 0-511, RRRGGGBBB
  'pair'    (RRRGGGBB, low blue bit): NextReg 0x44's two bytes
  'rgb333'  (r, g, b) each 0-7
  'rgb332'  (r, g, b) r, g 0-7, b 0-3 (an 8-bit byte split up): always a master colour
  'rgb888'  (r, g, b) each 0-255; levels n * 255 / 7, rounded down (coloursheet) or to nearest (some
            engines) - both read back to the same level

This module only describes colours; no engine output depends on it.
"""

FORMS = ('next8', 'next9', 'pair', 'rgb333', 'rgb332', 'rgb888')
MASTER_BLUE = (0, 3, 5, 7)          # the 3-bit blue levels an 8-bit entry can show


def _blue3(b2):
    return (b2 << 1) | (1 if b2 else 0)


def level888(n):
    """3-bit level -> 8-bit channel, as coloursheet.palette_rgb (n * 255 // 7)."""
    return n * 255 // 7


MASTER_RGB333 = tuple((i >> 5 & 7, i >> 2 & 7, _blue3(i & 3)) for i in range(256))
MASTER_NEXT9 = tuple(r << 6 | g << 3 | b for r, g, b in MASTER_RGB333)
MASTER_RGB888 = tuple(tuple(level888(v) for v in c) for c in MASTER_RGB333)
_INDEX9 = {v: i for i, v in enumerate(MASTER_NEXT9)}


def _infer(colour):
    if isinstance(colour, int):
        return 'next8'
    if len(colour) == 2:
        return 'pair'
    return 'rgb888' if max(colour) > 7 else 'rgb333'


def rgb333(colour, form=None):
    """Any form -> the (r, g, b) 0-7 the Next shows. Without `form`: an int is 'next8' (pass 'next9'
    for a 9-bit int), a pair is 'pair', a triple with a channel above 7 is 'rgb888', else 'rgb333'."""
    form = form or _infer(colour)
    if form == 'next8':
        if not 0 <= colour <= 255:
            raise ValueError('next8 colour out of range: %r' % (colour,))
        return MASTER_RGB333[colour]
    if form == 'next9':
        if not 0 <= colour <= 511:
            raise ValueError('next9 colour out of range: %r' % (colour,))
        return (colour >> 6 & 7, colour >> 3 & 7, colour & 7)
    if form == 'pair':
        v, lo = colour
        return (v >> 5 & 7, v >> 2 & 7, (v & 3) << 1 | (lo & 1))
    r, g, b = colour
    if form == 'rgb333':
        return (r, g, b)
    if form == 'rgb332':
        return (r, g, _blue3(b))
    if form == 'rgb888':
        return tuple(min(7, max(0, (v * 7 + 127) // 255)) for v in (r, g, b))
    raise ValueError('unknown colour form %r (one of %s)' % (form, ', '.join(FORMS)))


def is_master(colour, form=None):
    """True if the colour, as the Next shows it, is one of the standard 256."""
    return rgb333(colour, form)[2] in MASTER_BLUE


def master_index(colour, form=None):
    """The master index (RRRGGGBB) of a master colour, None if it is not one."""
    r, g, b = rgb333(colour, form)
    return _INDEX9.get(r << 6 | g << 3 | b)


def nearest(colour, form=None):
    """-> the master index (RRRGGGBB) nearest to the colour (squared RGB distance; an RGB888 colour is
    measured as given, every other form at its shown 9-bit level). A master colour returns itself."""
    form = form or _infer(colour)
    if form == 'rgb888':
        c = tuple(colour)
    else:
        c = tuple(level888(v) for v in rgb333(colour, form))
    return min(range(256), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, MASTER_RGB888[i])))


def describe(index):
    """'0xE3 (7,0,7)' - a master index and its RGB333, for reports."""
    return '0x%02X (%d,%d,%d)' % ((index,) + MASTER_RGB333[index])


def selfcheck():
    """-> list of failures (empty = OK)."""
    from . import coloursheet
    bad = []
    if coloursheet.palette_rgb(range(256)) != list(MASTER_RGB888):
        bad.append('MASTER_RGB888 differs from coloursheet.palette_rgb')
    if len(set(MASTER_NEXT9)) != 256 or sum(map(is_master, range(512), ['next9'] * 512)) != 256:
        bad.append('master palette is not 256 distinct 9-bit colours')
    cases = [((0xE3, 'next8'), True), ((0x1C7, 'next9'), True), ((0x1C6, 'next9'), False),
             (((0x04, 1), 'pair'), False), (((0x04, 0), 'pair'), True), (((0x8D, 0), 'pair'), False),
             (((0x8D, 1), 'pair'), True), (((7, 7, 3), 'rgb332'), True), (((0, 0, 4), 'rgb333'), False),
             (((36, 109, 219), 'rgb888'), False), (((36, 109, 255), 'rgb888'), True),
             (((0, 0, 205), 'rgb888'), False), (((0, 0, 154), 'rgb888'), False)]
    for (c, f), want in cases:
        if is_master(c, f) != want:
            bad.append('is_master(%r, %r) != %r' % (c, f, want))
    for i in range(256):
        if nearest(i) != i or master_index(MASTER_RGB888[i]) != i:
            bad.append('master colour %d does not map to itself' % i)
            break
    if nearest((0x04, 1), 'pair') != 0x04 or nearest(0x1C6, 'next9') != 0xE2:
        bad.append('nearest master of an off-standard 9-bit colour')
    return bad
