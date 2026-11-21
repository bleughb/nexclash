"""R-Type start-up showpiece (owner request 2026-11-17): the technical specification screen, upscaled
and shown on the Next at 640x256 after the original.

    py -3 -m nexclash.r_type_showpiece SOURCE.png ORIGINAL.png [--preview OUT.png]

SOURCE is any image (an AI upscale, or by default the original 256x192 screen in showpiece/, upscaled
here: Scale2x twice for clean diagonals, then Lanczos to 640x240, the full width, centred in 256 lines).
Layer 2 640x256 has 16 colours per pixel; the Copper gives each band of BAND lines its own 16 colours
(8-bit RRRGGGBB), Floyd-Steinberg dithered within the band. Layer 2 has two palettes: the
Copper fills the hidden one during the band above and switches with one write in the line's horizontal
blank, so band edges are clean.

Output (build(): extra banks): the picture in Layer 2 screen A (banks 48-52, column-major, two pixels a
byte, left pixel high) and the Copper list (bank 28, 2048 bytes, HALT-padded), uploaded and started by
glide.asm reveal_on during the start-up hold (l2scroll.asm spec_hold).
"""
import sys
from pathlib import Path
from PIL import Image

# Set by r_type.Patch: SOURCE = the owner's neon-glow 320x256 picture of the specification screen (a side input beside
# the snapshot, checked by MD5: game art, never in this repo); ORIGINAL = the original 256x192 specification screen,
# the transition's start (the snapshot's own screen, r_type_intro.spec_image).
SOURCE = None
ORIGINAL = None
W, H, BAND = 640, 256, 8
LEAD = -1                               # measured in CSpect: WAIT line n, h 40 shows from row n + 32
TOP = 40                                # rows 0-39 (the top border and the first lines) share one
                                        # palette loaded at the frame start: the Copper restarts at
                                        # vertical blank after the border's lines 280-311 have passed
L2_BANK0, COPPER_BANK = 48, 28
TRANSP = 0xE3


def scale2x(im):
    """EPX / Scale2x: doubles without blur, smoothing diagonal steps."""
    w, h = im.size
    src = im.load()
    out = Image.new('RGB', (w * 2, h * 2))
    o = out.load()
    for y in range(h):
        for x in range(w):
            p = src[x, y]
            a = src[x, y - 1] if y > 0 else p
            b = src[x + 1, y] if x < w - 1 else p
            c = src[x - 1, y] if x > 0 else p
            d = src[x, y + 1] if y < h - 1 else p
            e0 = a if (c == a and c != d and a != b) else p
            e1 = b if (a == b and a != c and b != d) else p
            e2 = c if (d == c and d != b and c != a) else p
            e3 = d if (b == d and b != a and d != c) else p
            o[2 * x, 2 * y] = e0
            o[2 * x + 1, 2 * y] = e1
            o[2 * x, 2 * y + 1] = e2
            o[2 * x + 1, 2 * y + 1] = e3
    return out


def upscale(path):
    im = Image.open(path).convert('RGB')
    if im.size == (256, 192):
        im = scale2x(scale2x(im))
    # uniform x1.25 of the 4:3 picture: the full width (320 display = 640 half pixels) by 240 lines,
    # centred in the 256 (Layer 2 pixels are half as wide as they are tall in this mode)
    out = Image.new('RGB', (W, H))
    out.paste(im.resize((W, 240), Image.LANCZOS), (0, (H - 240) // 2))
    return out


def rgb332(c):
    """(r, g, b) 0-255 -> (r3, g3, b2) and the Next's 8-bit palette byte RRRGGGBB (NR 0x41: one write a
    colour; the 9-bit NR 0x44 pairs did not survive Copper writes)."""
    r, g = (min(7, (v * 7 + 127) // 255) for v in c[:2])
    b = min(3, (c[2] * 3 + 127) // 255)
    v = (r << 5) | (g << 2) | b
    if v == TRANSP:                        # Layer 2's transparent colour: nudge green
        g = g + 1 if g < 7 else g - 1
        v = (r << 5) | (g << 2) | b
    return (r, g, b), v


def bands():
    """(first row, end row) of each palette band."""
    return [(0, TOP)] + [(r, min(H, r + BAND)) for r in range(TOP, H, BAND)]


def convert(img):
    """-> (pixel indices [H][W], [palette per band: 16 x (hi, lo)])."""
    idx = [[0] * W for _ in range(H)]
    pals = []
    for b0, b1 in bands():
        band = img.crop((0, b0, W, b1))
        q = band.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        raw = (q.getpalette() or [])[:48]
        raw += [0] * (48 - len(raw))
        cols = [rgb332(tuple(raw[3 * i:3 * i + 3])) for i in range(16)]
        pal = Image.new('P', (1, 1))
        flat = []
        for (r, g, b), _ in cols:
            flat += [r * 255 // 7, g * 255 // 7, b * 255 // 3]
        pal.putpalette(flat + [0] * (768 - len(flat)))
        q2 = band.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG)
        px = q2.load()
        for y in range(band.height):
            for x in range(W):
                idx[b0 + y][x] = px[x, y]
        pals.append([c[1] for c in cols])
    return idx, pals


def layer2_banks(idx):
    """640x256x4, column-major: byte column c (0-319), row r -> page c//32, offset (c%32)*256 + r."""
    data = bytearray(81920)
    for c in range(320):
        base = (c // 32) * 8192 + (c % 32) * 256
        for r in range(H):
            data[base + r] = (idx[r][2 * c] << 4) | idx[r][2 * c + 1]
    return {L2_BANK0 + n: bytes(data[n * 16384:(n + 1) * 16384]) for n in range(5)}


def copper(pals):
    """Copper list (big-endian 16-bit instructions). NR 0x43: bits 6-4 palette being written
    (001 Layer 2 first, 101 second), bit 2 the Layer 2 palette shown."""
    prog = []
    edit = (0x10, 0x50)

    def move(reg, val):
        prog.append((reg << 8) | val)

    def load(p, shown):
        move(0x43, edit[p] | (shown << 2))
        move(0x40, 0)
        for v in pals_p[p]:
            move(0x41, v)
    pals_p = {}
    pals_p[0] = pals[0]
    load(0, 0)                              # band 0, from the frame's start (vertical blank)
    starts = [b0 for b0, _ in bands()]
    for b in range(1, len(pals)):
        p, shown = b % 2, (b - 1) % 2
        pals_p[p] = pals[b]
        load(p, shown)                      # the hidden palette, while the band above is drawn
        line = starts[b] - 32 - 1 - LEAD    # the line above this band (Copper line 0 = picture top)
        prog.append(0x8000 | (40 << 9) | line)  # its horizontal blank (h 40 = x 320)
        move(0x43, edit[p] | (p << 2))      # show it
    # below the picture: the top band's palette for the next frame's border lines (the restart at
    # vertical blank comes after them)
    p = len(pals) % 2
    pals_p[p] = pals[0]
    load(p, (len(pals) - 1) % 2)
    prog.append(0x8000 | (40 << 9) | (H - 32))  # past the last band (line 224)
    move(0x43, edit[p] | (p << 2))
    move(0x43, 0x10 | (p << 2))             # the next frame's prologue writes the first palette
    prog.append(0xFFFF)                     # HALT (mode 11 restarts at vertical blank)
    assert len(prog) <= 1024, len(prog)
    out = bytearray()
    for i in prog:
        out += bytes([i >> 8, i & 255])
    out += bytes([0xFF]) * (2048 - len(out))
    return bytes(out), len(prog)


NEON_DOWN = 11                     # owner 2026-11-17: picture rows 1-232 -> 12-243, black 12 above, 12 below


def indexed_320(path):
    """A 320x256 paletted image (owner's own conversion): shown as it is in Layer 2 320x256 x 256 colours.
    -> ({bank: data}, palette bytes (256 x hi, lo: 9-bit)) or None if the image is not one."""
    im = Image.open(path)
    if im.size != (320, 256) or im.mode != 'P':
        return None
    pal = im.getpalette()[:768]
    pal += [0] * (768 - len(pal))
    out = bytearray()
    for i in range(256):
        r, g, b = (min(7, (v * 7 + 127) // 255) for v in pal[3 * i:3 * i + 3])
        hi = (r << 5) | (g << 2) | (b >> 1)
        if hi == TRANSP:                   # Layer 2's transparent colour: nudge green
            g = g + 1 if g < 7 else g - 1
            hi = (r << 5) | (g << 2) | (b >> 1)
        out += bytes([hi, b & 1])
    px = im.load()
    data = bytearray(81920)                # column-major: column x, row y -> x * 256 + y
    blank = px[0, 0]
    for x in range(320):
        for y in range(256):
            sy = y - NEON_DOWN
            data[x * 256 + y] = px[x, sy] if 0 <= sy < 256 else blank
    return {L2_BANK0 + n: bytes(data[n * 16384:(n + 1) * 16384]) for n in range(5)}, bytes(out)


ORIG_BANK0 = 58                    # the original screen as a Layer 2 image (the transition starts from it)


def original_banks(source, pal):
    """The original 256x192 screen at its place in 320x256 (32, 32), in the same 8-bit Layer 2 as the
    picture, for the pixelate / depixelate transition (glide.asm transition). Its colours go into
    palette entries the picture does not use. -> ({bank: data}, palette bytes)."""
    pic = Image.open(source)
    used = {c for _, c in pic.getcolors(1024)}
    free = [i for i in range(255, -1, -1) if i not in used]
    orig = (ORIGINAL if isinstance(ORIGINAL, Image.Image) else Image.open(ORIGINAL)).convert('RGB')
    cols = {}
    pal = bytearray(pal)
    for c in sorted(set(orig.getdata())) + [(0, 0, 0)]:
        if c in cols:
            continue
        i = free.pop(0)
        r, g, b = (min(7, (v * 7 + 127) // 255) for v in c)
        hi = (r << 5) | (g << 2) | (b >> 1)
        if hi == TRANSP:
            g = g + 1 if g < 7 else g - 1
            hi = (r << 5) | (g << 2) | (b >> 1)
        pal[2 * i:2 * i + 2] = bytes([hi, b & 1])
        cols[c] = i
    black = cols[(0, 0, 0)]
    data = bytearray([black]) * 81920
    px = orig.load()
    for x in range(256):
        for y in range(192):
            data[(x + 32) * 256 + y + 32] = cols[px[x, y]]
    return {ORIG_BANK0 + n: bytes(data[n * 16384:(n + 1) * 16384]) for n in range(5)}, bytes(pal)


def build(source=None):
    """-> ({bank: data}, info). The glide page payload (bank COPPER_BANK) starts with a mode byte:
    0 = Copper list (640x256, bands), 1 = 9-bit palette (320x256 x 256 colours)."""
    ix = indexed_320(source or SOURCE)
    if ix:
        banks, pal = ix
        ob, pal = original_banks(source or SOURCE, pal)
        banks.update(ob)
        banks[COPPER_BANK] = bytes([1]) + pal + bytes(16383 - len(pal))
        return banks, dict(mode='320x256x256', palette=256, original_banks=sorted(ob))
    img = upscale(source or SOURCE)
    idx, pals = convert(img)
    banks = layer2_banks(idx)
    cop, n = copper(pals)
    banks[COPPER_BANK] = bytes([0]) + cop + bytes(16383 - len(cop))
    return banks, dict(bands=len(pals), copper_instructions=n)


def preview(source=None):
    """What the Next shows: the indices through each band's 9-bit palette."""
    img = upscale(source or SOURCE)
    idx, pals = convert(img)
    out = Image.new('RGB', (W, H))
    o = out.load()
    for y in range(H):
        pal = pals[next(i for i, (b0, b1) in enumerate(bands()) if b0 <= y < b1)]
        for x in range(W):
            v = pal[idx[y][x]]
            r, g, b = v >> 5, (v >> 2) & 7, v & 3
            o[x, y] = (r * 255 // 7, g * 255 // 7, b * 255 // 3)
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--preview' in argv:
        i = argv.index('--preview')
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith('--')]
    src = args[0] if args else None
    if len(args) > 1:
        ORIGINAL = args[1]
    if '--preview' in sys.argv:
        p = sys.argv[sys.argv.index('--preview') + 1]
        preview(src).resize((1280, 1024), Image.NEAREST).save(p)
        print('preview', p)
    banks, info = build(src)
    print(info)
