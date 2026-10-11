"""Sprite frames -> 4-bit Next patterns (from the Treasure Island Dizzy builder)."""

FRAME_TABLE = FRAME_BASE = 0
NUM_FRAMES = 39


def read_frames(peek):
    """Return a list of (height, {(x, y): 'T'|'K'|'W'}) for the 39 frames."""
    frames = []
    for n in range(NUM_FRAMES):
        off = peek(FRAME_TABLE + 2 * n) | peek(FRAME_TABLE + 2 * n + 1) << 8
        a = FRAME_BASE + off
        h = peek(a)
        if not 1 <= h <= 32:
            raise ValueError('frame %d has height %d - not the expected game data' % (n, h))
        px = {}
        for r in range(h):
            for bx in range(3):
                mk = peek(a + 2 + r * 6 + bx * 2)
                gf = peek(a + 3 + r * 6 + bx * 2)
                for bit in range(8):
                    m = (mk >> (7 - bit)) & 1
                    g = (gf >> (7 - bit)) & 1
                    if m and g:
                        raise ValueError('frame %d uses inverted pixels (not supported)' % n)
                    px[(bx * 8 + bit, r)] = 'T' if m else ('W' if g else 'K')
        frames.append((h, px))
    return frames


COLOUR = {'T': 0, 'K': 1, 'W': 2}      # sprite palette indices (set in setup.asm)
QUADS = [(0, 0), (16, 0), (16, 16), (0, 16)]   # TL, TR, BR, BL (order used by hooks.asm)


def build_patterns(frames):
    """Frames are bottom-aligned in a 32x32 box. Returns (pattern bytes, table)."""
    patterns = []
    index = {}
    table = bytearray()
    for h, px in frames:
        top = 32 - h
        for qx, qy in QUADS:
            pix = []
            for y in range(16):
                for x in range(16):
                    pix.append(COLOUR[px.get((qx + x, qy + y - top), 'T')])
            if not any(pix):
                table += b'\x00\x00'
                continue
            key = bytes(pix)
            if key not in index:
                index[key] = len(patterns)
                patterns.append(bytes((pix[i] << 4) | pix[i + 1] for i in range(0, 256, 2)))
            p = index[key]
            table += bytes([0xC0 | (p >> 1), 0x80 | ((p & 1) << 6)])  # visible+ext, 4-bit
    if len(patterns) > 128:
        raise ValueError('%d patterns needed, only 128 fit' % len(patterns))
    return b''.join(patterns), bytes(table), len(patterns)




def patterns_for(peek, frame_table, frame_base):
    global FRAME_TABLE, FRAME_BASE
    FRAME_TABLE, FRAME_BASE = frame_table, frame_base
    return build_patterns(read_frames(peek))
