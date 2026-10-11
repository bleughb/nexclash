"""Rainbow Islands object catalogue: every object the game draws into a back-buffer cell (opaque
60839 codes, masked 60965 codes) and every map tile drawn under them, from one or more recordings.

    python -m nexclash.rainbow_objects rainbow.z80 rec.rzx [rec2.rzx ...] -o objects.png

Writes objects.png (per object: the game's 8x8 graphic, and the tile the build shows - border and
class from the profile - in yellow on sky blue; then the map tiles seen under objects) and
objects.json: an "objects" section to edit and paste into the profile (rainbow_islands.json), with
every code seen listed with its current settings and how often / from which frame it was seen.
Settings per code: "group": "rainbow" (behind the others, the cell's ink) or "item"; "ula": true
(leave the cell as the game draws it); "border": false; "ink": 0-7 + "bright": true (fixed colour).
"background": {"tile": tile} shows another map tile under objects (e.g. a later island's map).
A recording from a new island shows its objects; nothing else needs changing for codes that look
right with the defaults.
"""
import argparse
import collections
import json
import os
import sys

from . import rainbow as rb


def collect(rzx, stop=None):
    """{('O'|'M', code): [count, first frame, 8 gfx rows]}, {tile: [count under objects, rows, colour]}."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG = Memory.__getitem__
    objs, tiles, st = {}, {}, {'f': 0}

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            peek = lambda a: MG(mem, a)

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in (60839, 60965) and (mem.o7ffd & 7) == 0 and rb.cell_index(R[4], R[5]) is not None:
                        a = R[0]
                        kind = 'O' if pc == 60839 else 'M'
                        if kind == 'O' or 1 <= a <= 14:
                            k = (kind, a)
                            if k not in objs:
                                objs[k] = [0, st['f'], bytes(rb.obj_rows(peek, kind, a))]
                            objs[k][0] += 1
                        if kind == 'O':
                            t = peek(R[18] * 256 + R[19])
                            if t not in tiles:
                                tiles[t] = [0, bytes(rb.tile_row(peek, t, j) for j in range(8)),
                                            peek(0xF200 | t | 128) & 127]
                            tiles[t][0] += 1
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    _nf = rzxplay.RZXTracer.next_frame

    def nf(self):
        st['f'] += 1
        return _nf(self)
    rzxplay.RZXTracer.next_frame = nf
    rzxplay.Simulator, rzxplay.CSimulator = S, None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0']
    if stop:
        args += ['--stop', str(stop)]
    try:
        rzxplay.main(args + [rzx])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame = _nf
        rzxplay.Simulator = Simulator
    return objs, tiles


def settings(cls):
    """Class byte (OCLASS / MCLASS) -> profile settings dict."""
    o = {'group': 'rainbow' if cls & 1 else 'item'}
    if cls & 2:
        o['ula'] = True
    if cls & 4:
        o['border'] = False
    if cls >> 4:
        n = cls >> 4
        o['ink'], o['bright'] = (0, False) if n == 1 else ((n - 2) % 7 + 1, n >= 9)
    return o


SPECCY = [(0, 0, 0), (0, 0, 0xD7), (0xD7, 0, 0), (0xD7, 0, 0xD7), (0, 0xD7, 0), (0, 0xD7, 0xD7), (0xD7, 0xD7, 0),
          (0xD7, 0xD7, 0xD7)]
BRIGHT = [(0, 0, 0), (0, 0, 0xFF), (0xFF, 0, 0), (0xFF, 0, 0xFF), (0, 0xFF, 0), (0, 0xFF, 0xFF), (0xFF, 0xFF, 0),
          (0xFF, 0xFF, 0xFF)]


def index_rgb(i):
    if i == 1:
        return (0, 0, 0)
    return (BRIGHT if i >= 9 else SPECCY)[(i - 2) % 7 + 1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('z80')
    ap.add_argument('rzx', nargs='+')
    ap.add_argument('-o', default='objects.png')
    ap.add_argument('--stop', type=int)
    a = ap.parse_args(argv)
    from PIL import Image, ImageDraw
    objs, tiles = {}, {}
    for r in a.rzx:
        o, t = collect(r, a.stop)
        for k, v in o.items():
            objs.setdefault(k, [0, v[1], v[2]])[0] += v[0]
        for k, v in t.items():
            tiles.setdefault(k, [0, v[1], v[2]])[0] += v[0]
    prof = rb.load_profile()
    ocls, mcls, bg = rb.object_tables(prof.get('objects', {}))
    page27 = bytearray(8192)
    page27[rb.OCLASS - 0x2000:rb.OCLASS - 0x2000 + 256] = ocls
    page27[rb.MCLASS - 0x2000:rb.MCLASS - 0x2000 + 16] = mcls
    S, CW, CH = 4, 8 * 4 * 2 + 70, 8 * 4 + 22
    keys = sorted(objs)
    cols = 8
    rows_o = (len(keys) + cols - 1) // cols
    tkeys = sorted(tiles)
    rows_t = (len(tkeys) + 16 - 1) // 16
    W = cols * CW + 8
    H = 30 + rows_o * CH + 30 + rows_t * (8 * S + 20) + 8
    im = Image.new('RGB', (W, H), (40, 40, 40))
    d = ImageDraw.Draw(im)
    d.text((6, 6), 'Objects (O = opaque 60839, M = masked 60965): game graphic | tile shown (yellow on sky). '
           'R = rainbow group, U = left as drawn', fill=(255, 255, 255))
    sky = (0, 0, 0xFF)
    info = {'opaque': {}, 'masked': {}, 'background': {}}
    for n, k in enumerate(keys):
        kind, code = k
        cnt, first, rows = objs[k]
        x0, y0 = 4 + (n % cols) * CW, 30 + (n // cols) * CH
        for j in range(8):
            for x in range(8):
                on = (rows[j] >> (7 - x)) & 1
                d.rectangle((x0 + x * S, y0 + j * S, x0 + x * S + S - 1, y0 + j * S + S - 1),
                            fill=(255, 255, 255) if on else (0, 0, 0))
        cls = page27[(rb.OCLASS if kind == 'O' else rb.MCLASS) - 0x2000 + code]
        tile = rb.obj_compose(lambda ad: _gfx(kind, code, rows, ad), page27, [(kind, code)], 14, 14)
        x1 = x0 + 8 * S + 4
        for j in range(8):
            for x in range(8):
                b = tile[4 * j + x // 2]
                v = (b >> 4) if x % 2 == 0 else (b & 15)
                d.rectangle((x1 + x * S, y0 + j * S, x1 + x * S + S - 1, y0 + j * S + S - 1),
                            fill=sky if v == 0 else index_rgb(v))
        d.text((x1 + 8 * S + 3, y0), '%s%d%s%s' % (kind, code, ' R' if cls & 1 else '', ' U' if cls & 2 else ''),
               fill=(255, 255, 0))
        d.text((x1 + 8 * S + 3, y0 + 12), 'x%d' % cnt, fill=(180, 180, 180))
        e = settings(cls)
        e['_seen'] = '%d draws, first at frame %d' % (cnt, first)
        info['opaque' if kind == 'O' else 'masked'][str(code)] = e
    y = 30 + rows_o * CH + 6
    d.text((6, y), 'Map tiles drawn under opaque objects (tile number, colour); background override: '
           '"background": {"tile": tile}', fill=(255, 255, 255))
    y += 20
    for n, t in enumerate(tkeys):
        cnt, rows, colour = tiles[t]
        x0, y0 = 4 + (n % 16) * (8 * S + 16), y + (n // 16) * (8 * S + 20)
        ink = (BRIGHT if colour & 64 else SPECCY)[colour & 7]
        pap = (BRIGHT if colour & 64 else SPECCY)[(colour >> 3) & 7]
        for j in range(8):
            for x in range(8):
                d.rectangle((x0 + x * S, y0 + j * S, x0 + x * S + S - 1, y0 + j * S + S - 1),
                            fill=ink if (rows[j] >> (7 - x)) & 1 else pap)
        d.text((x0, y0 + 8 * S + 2), '%d' % t, fill=(200, 200, 200))
        if bg[t] != t:
            info['background'][str(t)] = bg[t]
    info['_doc'] = prof.get('objects', {}).get('_doc', '')
    im.save(a.o)
    json.dump({'objects': info}, open(os.path.splitext(a.o)[0] + '.json', 'w'), indent=1)
    print('%d objects, %d map tiles under objects -> %s' % (len(keys), len(tkeys), a.o))


def _gfx(kind, code, rows, ad):
    """Memory view for obj_rows: the object's rows at its own graphics address."""
    if kind == 'O':
        base = 0xF700 + 8 * (code - 1)
        return rows[ad - base] if 0 <= ad - base < 8 else 0
    base = 0xF600 + ((code - 1) * 16 & 255)
    o = ad - base
    return rows[o >> 1] if 0 <= o < 16 and o & 1 else 0


if __name__ == '__main__':
    sys.exit(main())
