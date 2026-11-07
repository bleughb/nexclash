"""The New Zealand Story colour build, "Backdrops" toggle (v1.2): pack the five worlds' original backdrop tile sets
(assets/new_zealand_story/backdrops: Jon Attree's own art, not the game's) into the free pages of the 1 MB build, and the
pixel model the replay proof compares Layer 2 with. Engine: nexclash/new_zealand_story.py.

Pages (all zero in v1.1, in banks the .nex already has): 45, 67, 81, 83.
  page 81 offset 0x0000: directory: level table, 21 x 4 (world 1-5, stage 0-3, base_y lo, hi)
          offset 0x0100: palettes, 5 worlds x 4 stages x 16 x 2 bytes (9-bit: RRRGGGBB, 0000000B)
          offset 0x1F00: run-time state (backdrop.asm)
  each world's tile page, at its header address H (in the 0x6000 window, MMU3):
     H+0  type (0 texture, 1 horizon), cx, cy, ns, nb, ng, cx/2, ns*16 (lo; < 256)
     H+8  sx[4]  H+12 sy[4]  H+16 stagger[4]  H+20 tiles address (word)  H+22 unit map address (word)
     H+24 nb*16 (word)  H+26 (ns*16) (word)  H+28..31 run-time (current stage values)
     unit map cx*cy bytes (tile numbers), tiles n x 128 bytes, column-major 4bpp: byte col*8 + row/2,
     high nibble = even row.
Pixel model (backdrop_index): exactly what asm/new_zealand_story_backdrop.asm draws.
"""
import json
import os

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'new_zealand_story', 'backdrops')
NAMES = ['1-1', '1-2', '1-3', '1-4', '2-1', '2-2', '2-3', '2-4', '3-1', '3-2', '3-3', '3-4',
         '4-1', '4-2', '4-3', '4-4a', '4-4b', '5-1', '5-2', '5-3', '5-4']
LEVEL_WS = {i: (int(n[0]), (min(int(n[2]), 4) - 1)) for i, n in enumerate(NAMES)}   # 4-4a / 4-4b: stage 4
DIRPG = 81
PAGES = [45, 67, 81, 83]
PLACE = {3: 45, 2: 67, 4: 81, 1: 83, 5: 83}       # world -> tile page
STATE_OFF = 0x1F00


def load(world):
    return json.load(open(os.path.join(ART, 'w%d.json' % world)))


def unit_of(meta):
    """The unit map (rows x cx) the stage maps are made of, and the per-stage parameters."""
    cx, cyu = meta['unit_cells']
    st = meta['stages']
    m1 = st[0]['map']
    if meta.get('layout') == 'horizon':
        unit = [row[:cx] for row in m1]
        sx = [s['map_shift_cells'] for s in st]
        for s, k in zip(st, sx):     # stage maps are the unit shifted by sx columns
            assert all(s['map'][r][c] == unit[r][(c + k) % cx] for r in range(len(unit)) for c in range(cx))
        return unit, dict(sx=sx, sy=[0] * 4, stg=[0] * 4)
    unit = [row[:cx] for row in m1[:cyu]]
    # make_backdrops.stage_maps: grid, staggered, shifted (cx//3, cy//2), staggered+shifted ((2cx)//3, cy//3)
    sx = [0, 0, cx // 3, (2 * cx) // 3]; sy = [0, 0, cyu // 2, cyu // 3]; stg = [0, 1, 0, 1]
    if cx < 2:
        sy[1] = cyu // 2; stg[1] = 0
    return unit, dict(sx=sx, sy=sy, stg=stg)


def tile_bytes(rows_hex):
    t = [[int(ch, 16) for ch in r] for r in rows_hex]   # [row][col]
    out = bytearray(128)
    for c in range(16):
        for r in range(0, 16, 2):
            out[c * 8 + r // 2] = (t[r][c] << 4) | t[r + 1][c]
    return bytes(out)


def layout():
    """Directory at page 81: palettes 0x0100-0x037F, level table 0x0380-0x03D3; world 4's data from 0x0400."""
    global PLACE
    pages = {p: bytearray(8192) for p in PAGES}
    used = {p: 0 for p in PAGES}; used[DIRPG] = 0x0400
    worlds = {}
    floors = json.load(open(os.path.join(ART, 'floors.json')))['base_y']
    d = pages[DIRPG]
    for w in range(1, 6):
        meta = load(w)
        unit, prm = unit_of(meta)
        cy, cx = len(unit), len(unit[0])
        hz = meta.get('layout') == 'horizon'
        ns, nb, ng = (meta['rows']['sky'], meta['rows']['band'], meta['rows']['ground']) if hz else (0, 0, 0)
        tiles = [tile_bytes(t) for t in meta['tiles']]
        pg = PLACE[w]; H = used[pg]
        hdr = bytearray(32)
        hdr[0:8] = bytes([1 if hz else 0, cx, cy, ns, nb, ng, cx // 2, (ns * 16) & 255])
        hdr[8:12] = bytes(prm['sx']); hdr[12:16] = bytes(prm['sy']); hdr[16:20] = bytes(prm['stg'])
        umap = H + 32; toff = umap + cx * cy
        hdr[20:22] = (0x6000 + toff).to_bytes(2, 'little'); hdr[22:24] = (0x6000 + umap).to_bytes(2, 'little')
        hdr[24:26] = (nb * 16).to_bytes(2, 'little'); hdr[26:28] = (ns * 16).to_bytes(2, 'little')
        end = toff + 128 * len(tiles)
        lim = STATE_OFF      # every page keeps 0x1F00-0x1FFF free: the hooks' stack zone, scratch and state
        assert end <= lim, ('page full', w, pg, hex(end))
        p = pages[pg]
        p[H:H + 32] = hdr; p[umap:umap + cx * cy] = bytes(int(v) for row in unit for v in row)
        for i, t in enumerate(tiles):
            p[toff + 128 * i:toff + 128 * i + 128] = t
        used[pg] = end
        worlds[w] = dict(page=pg, hdr=0x6000 + H, type=int(hz), cx=cx, cy=cy, ns=ns, nb=nb, ng=ng, unit=unit,
                         prm=prm, ntiles=len(tiles), tiles=[list(t) for t in tiles],
                         pals=[s['palette_9bit'] for s in meta['stages']], used=end)
        for s in range(4):
            pal = meta['stages'][s]['palette_9bit']
            o = 0x100 + ((w - 1) * 4 + s) * 32
            for i in range(16):
                v = pal[i] if i < len(pal) else 0
                d[o + 2 * i] = v >> 1; d[o + 2 * i + 1] = v & 1
    for i, n in enumerate(NAMES):
        w, s = LEVEL_WS[i]
        b = floors[n]
        o = 0x380 + 4 * i
        d[o:o + 4] = bytes([w, s, b & 255, b >> 8])
    info = dict(worlds=worlds, used={p: used[p] for p in PAGES}, levels={i: LEVEL_WS[i] + (floors[n],) for i, n in enumerate(NAMES)})
    return {p: bytes(b) for p, b in pages.items()}, info


# ------------------------------------------------------------ the model
def backdrop_index(info, level, wx, wy):
    """Palette index 0-15 of the backdrop at world pixel (wx, wy) of level (A402 value)."""
    w, s, base = info['levels'][level]
    W = info['worlds'][w]
    cx, cy = W['cx'], W['cy']
    C, tx = wx >> 4, wx & 15
    if W['type'] == 0:
        R, py = wy >> 4, wy & 15
        off = W['cx'] // 2 if (W['prm']['stg'][s] and (R // cy) & 1) else 0
        ur = (R + W['prm']['sy'][s]) % cy
        uc = (C + off + W['prm']['sx'][s]) % cx
    else:
        ns, nb, ng = W['ns'], W['nb'], W['ng']
        rel = wy - base
        if rel >= 0:
            ur = ns + nb + ((rel >> 4) % ng); py = rel & 15
        elif rel >= -nb * 16:
            k = rel + nb * 16; ur = ns + (k >> 4); py = k & 15
        else:
            k = (rel + nb * 16) % (ns * 16); ur = k >> 4; py = k & 15
        uc = (C + W['prm']['sx'][s]) % cx
    t = W['unit'][ur][uc]
    b = W['tiles'][t][tx * 8 + (py >> 1)]
    return (b >> 4) if (py & 1) == 0 else (b & 15)


def layout_inc(info, smooth_k):
    """bd_layout.inc for asm/new_zealand_story_backdrop.asm: per-world tile page and header address, the smooth-detect offset."""
    W = info['worlds']
    s = ['; written by nexclash/new_zealand_story_backdrops.py', 'BD_SMOOTH_K EQU %d' % smooth_k,
         'bd_wpage: db ' + ','.join(str(W[w]['page']) for w in range(1, 6)),
         'bd_whdr:  dw ' + ','.join('0x%04X' % W[w]['hdr'] for w in range(1, 6))]
    return '\n'.join(s) + '\n'
