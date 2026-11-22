"""Winter Sports Downhill: auto-paint the 256 x 128 panorama (1 bit = the game's ink) into an RGB332 picture."""
import sys
from collections import deque

W_, H_ = 256, 128
SKY, CLOUD, PEAK, RIDGE, FOREST, SLOPE, HAZE = range(7)


def bits(pano_bytes):
    return [[(pano_bytes[y * 32 + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(W_)] for y in range(H_)]


def components(P, val, conn=4):
    seen = [[False] * W_ for _ in range(H_)]
    comps = []
    for y in range(H_):
        for x in range(W_):
            if P[y][x] == val and not seen[y][x]:
                q = deque([(x, y)]); seen[y][x] = True; pts = []
                while q:
                    cx, cy = q.popleft(); pts.append((cx, cy))
                    nb = ((1, 0), (-1, 0), (0, 1), (0, -1)) if conn == 4 else ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
                    for dx, dy in nb:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= ny < H_ and 0 <= nx < W_ and P[ny][nx] == val and not seen[ny][nx]:
                            seen[ny][nx] = True; q.append((nx, ny))
                comps.append(pts)
    return comps


def classify(P):
    """-> L[y][x] class. Rows < 24 are the game's cyan-ink band (sky); the rest: ink = green (forest / ridge lines)."""
    L = [[-1] * W_ for _ in range(H_)]
    for pts in components(P, 1, 4):
        for x, y in pts:
            pass
    ones = components(P, 1, 4)
    zeros = components(P, 0, 4)
    for pts in ones:
        sky = all(y < 24 for x, y in pts)
        big = len(pts) >= 300
        for x, y in pts:
            if y < 24:
                L[y][x] = SKY
            else:
                L[y][x] = FOREST if big else RIDGE
    for pts in zeros:
        touches_bottom = any(y == H_ - 1 for x, y in pts)
        inside_sky = all(y < 24 for x, y in pts)
        for x, y in pts:
            if touches_bottom:
                L[y][x] = SLOPE
            elif inside_sky and len(pts) < 400:
                L[y][x] = CLOUD
            else:
                L[y][x] = PEAK
    # distant haze: the game dithers the far tree line (about half the pixels set over a wide patch): one mid tone
    def dens(cx, cy, r=3):
        n = t = 0
        for yy in range(max(24, cy - r), min(H_, cy + r + 1)):
            for xx in range(cx - r, cx + r + 1):
                n += P[yy][xx % W_]; t += 1
        return n / t if t else 0
    for y in range(24, 56):
        for x in range(W_):
            if L[y][x] in (FOREST, RIDGE, PEAK, SLOPE) and all(0.3 <= dens(x + dx, y) <= 0.7 for dx in (-6, 0, 6)):
                L[y][x] = HAZE
    return L


BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def rgb332_d(r, g, b, x, y):
    d = (BAYER[y & 3][x & 3] + 0.5) / 16 - 0.5
    rq = max(0, min(7, int(r / 255 * 7 + 0.5 + d)))
    gq = max(0, min(7, int(g / 255 * 7 + 0.5 + d)))
    bq = max(0, min(3, int(b / 255 * 3 + 0.5 + d)))
    v = rq << 5 | gq << 2 | bq
    return 0xE2 if v == 0xE3 else v


def rgb332(r, g, b):
    v = ((r * 7 + 127) // 255) << 5 | ((g * 7 + 127) // 255) << 2 | ((b * 3 + 127) // 255)
    return 0xE2 if v == 0xE3 else v      # 0xE3 is the transparent colour


def clamp(v):
    return max(0, min(255, int(v)))


def paint(L, P):
    """-> [[rgb332 byte]] 128 rows x 256."""
    out = [[0] * W_ for _ in range(H_)]
    # peak extent per column to shade snow caps: distance below the top of the mountain body
    top = [min([y for y in range(H_) if L[y][x] == PEAK] or [H_]) for x in range(W_)]
    for y in range(H_):
        for x in range(W_):
            c = L[y][x]
            if c == SKY:       # deep blue at the top to pale cyan at the horizon
                t = y / 23.0
                col = (40 + 60 * t, 120 + 100 * t, 215 + 30 * t)
            elif c == CLOUD:
                col = (250, 250, 255)
            elif c == PEAK:   # snow white at the summit, blue-grey rock lower down, light from the left (x parity ripple)
                d = y - top[x]
                t = min(1.0, d / 26.0)
                col = (245 - 85 * t, 247 - 70 * t, 255 - 40 * t)
            elif c == RIDGE:
                col = (70, 95, 120)
            elif c == FOREST:  # two dark greens, a fixed checker dither, lighter toward the horizon
                t = max(0.0, 1 - (y - 24) / 70.0)
                dark = ((x * 7 + y * 13) % 5 < 2)
                col = (20 + 25 * t, (95 if dark else 125) + 35 * t, 30 + 20 * t)
            elif c == HAZE:
                col = (70, 130, 120)
            else:              # slope: white snow, a cool shade deeper down the screen
                t = max(0.0, (y - 60) / 67.0)
                col = (250 - 28 * t, 252 - 20 * t, 255 - 8 * t)
            out[y][x] = rgb332_d(clamp(col[0]), clamp(col[1]), clamp(col[2]), x, y)
    return out


def to_image(pix, path, scale=3):
    from PIL import Image
    im = Image.new('RGB', (W_, H_))
    px = im.load()
    for y in range(H_):
        for x in range(W_):
            v = pix[y][x]
            px[x, y] = (((v >> 5) & 7) * 255 // 7, ((v >> 2) & 7) * 255 // 7, (v & 3) * 255 // 3)
    im.resize((W_ * scale, H_ * scale), Image.NEAREST).save(path)
