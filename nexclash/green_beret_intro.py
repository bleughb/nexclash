"""Build the Enhanced intro tilemap from the snapshot's scenery tiles and a hand-painted colour mask."""

# Konami arcade intro, native RGB samples. Index 15 is the hardware clear nibble.
COLOURS = (
    (0, 0, 0), (71, 0, 0), (151, 0, 0), (184, 0, 0),
    (71, 71, 82), (151, 151, 173), (222, 222, 255),
    (0, 0, 82), (0, 184, 255), (222, 151, 0), (222, 222, 173),
    (255, 255, 255), (71, 104, 0), (184, 184, 173), (222, 71, 0),
)
RESCUE = (71, 184, 173)
CLEAR = (255, 0, 219)  # NR 0x14's reset RGB332 value E3 (RGB333 1C6)

# x within the 16-pixel figure and swatches for that span. Rows start at y=139.
# Lower-case swatches colour an interior of the game's solid black trousers.
# All other ink, including the outside contour, stays black.
PAINT = (
    (8, '5'), (8, '6'), (8, '5'), (8, '6'), (7, '456'),
    (8, '7'), (7, 'h8h'), (7, '99A'), (7, 'bbb'),
    (6, '5A9A5'), (5, 'BB9A9BB'), (4, 'ABBBBBBBA'),
    (4, 'A5BBBBB5A'), (4, '95BBBBB59'), (5, '9BBBBB9'),
    (6, '55555'), (7, 'DDD'),
    (6, 'cdcdd'), (6, 'ddccd'), (5, 'cddccdc'), (5, 'dd...dc'),
    (5, 'cd...dc'), (5, 'd.....d'), (6, 'cd.cd'), (6, 'cdddc'),
    (7, 'ddd'), (7, 'DDD'), (6, 'dd.dd'), (5, '77...77'),
)


def rgb333(rgb):
    r, g, b = ((value * 7 + 127) // 255 for value in rgb)
    return r << 6 | g << 3 | b


def palettes():
    """Tile palette followed by 16 ULA inks and 16 papers, in NR 0x44 write order."""
    black = COLOURS[0]
    inks = [black] * 16
    inks[0] = inks[8] = CLEAR
    inks[2] = inks[6] = RESCUE
    inks[9:16] = [COLOURS[14]] * 7
    papers = [black] * 16
    papers[2] = papers[10] = CLEAR
    return bytes(v for rgb in (*COLOURS, *inks, *papers)
                 for v in (rgb333(rgb) >> 1, rgb333(rgb) & 1))


def tile(peek, column=None, row=0):
    """One 4bpp tile. Column None is plain wall, 0..1 are the prisoner's two columns."""
    addr = 0x77A0 if column is None else 0x77F0 + 16 * row + 8 * column
    pixels = []
    for y in range(8):
        ink = peek(addr + y)
        for x in range(8):
            dark = ink & (128 >> x)
            # Stagger the highlight with the original eight-pixel brick courses.
            along = (x - (3 if y < 4 else 7) - 1) % 8
            shade = 3 if y % 4 == 1 and along < 3 else 2 if y % 4 < 3 and along < 6 else 1
            if column == 1:
                shade = max(1, shade - 1)
            colour = 0 if dark else shade
            line = row * 8 + y - 3
            if column is not None and line >= 0:
                start, swatches = PAINT[line]
                i = column * 8 + x - start
                if 0 <= i < len(swatches):
                    ch = swatches[i]
                    if ch != '.' and (not dark or ch.islower()):
                        colour = 7 if ch == 'h' else int(ch, 16)
            pixels.append(colour)
    return bytes(a << 4 | b for a, b in zip(pixels[::2], pixels[1::2]))


def tile_data(peek):
    # Physical tile coordinates include the Next's 32-pixel border on either side.
    grid = bytearray(40 * 32)
    shapes = [bytes(32), bytes([0xEE]) * 32, tile(peek)]
    for y in range(4):
        for x in range(2):
            shapes.append(tile(peek, x, y))
    for row in range(13, 21):
        for col in range(2, 30):
            index = 2
            if row >= 17 and 6 <= col < 26 and (col - 6) % 6 < 2:
                index = 3 + 2 * (row - 17) + (col - 6) % 6
            grid[(row + 4) * 40 + col + 4] = index
    # Bright black is shared by the mortar and one stage-name animation phase.
    # Its transparent ink shows orange here. The game's black paper still masks each glyph.
    grid[13 * 40 + 14:13 * 40 + 26] = bytes([1]) * 12
    return bytes(grid) + b''.join(shapes)
