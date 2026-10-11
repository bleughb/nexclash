"""Rainbow Islands frame catalogue: every figure the list walker draws in a recording, grouped by
graphics page (high byte of the stream address = the key of the per-class colour hook).

    python -m nexclash.rainbow_catalogue rainbow.z80 rec.rzx [rec2.rzx ...] -o catalogue.png

Writes catalogue.png (one row per graphics page: up to 4 composites, each = all pieces of that page
drawn in one render at their screen positions, ink white / outline black on grey) and
catalogue.json (per page: distinct pieces, renders seen, stream address range, runtime-buffer flag).
Dean picks a colour per page -> class_colours JSON {"pages": {"D6": 1}, "palettes": {"1": {"ink":
"#FF0000"}}} -> nexclash.py auto ... --class-colours file.json. Pages 0x95-0x98 are the runtime
graphics buffer: several objects over time, a page colour there colours all of them.
"""
import argparse
import collections
import json
import os
import sys

from . import rainbow as rb


def collect(rzx, stop=None):
    """[(render_no, ix, cy, stream, sp, de)] for every cacheable piece in one recording."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    L = {int(k): v['len'] for k, v in rb.load_profile()['plotters'].items()}
    seq, st = [], {'r': 0}

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(memory, registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc == 58851:
                        st['r'] += 1
                    elif pc == 59539:
                        ix = R[8] * 256 + R[9]
                        if ix in L:
                            cy, sp = R[17] & 1, R[12]
                            seq.append((st['r'], ix, cy, bytes(mem[a] for a in range(sp, sp + L[ix][cy])),
                                        sp, R[4] * 256 + R[5]))
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])
    rzxplay.Simulator, rzxplay.CSimulator = S, None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0']
    if stop:
        args += ['--stop', str(stop)]
    try:
        rzxplay.main(args + [rzx])
    except SystemExit:
        pass
    return seq


def piece_pixels(base, ix, cy, stream, de):
    """Run the original plotter twice (screen 00 / FF) -> {(x, y): 1 ink | 2 outline}."""
    from skoolkit.simulator import Simulator
    res = []
    for fill in (0x00, 0xFF):
        m = bytearray(base)
        m[0x4000:0x5800] = bytes([fill]) * 0x1800
        m[0x8000:0x8000 + len(stream)] = stream
        sim = Simulator(m, {'PC': ix, 'SP': 0x8000, 'D': de >> 8, 'E': de & 255, 'H': 245, 'L': 0})
        sim.registers[17] = cy
        rb._run(sim, (59543,), 5000)
        res.append(m)
    g, mg = res
    px = {}
    for a in range(0x4000, 0x5800):
        if g[a] == 0 and mg[a] == 0xFF:
            continue
        y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
        for k in range(8):
            gb, mb = (g[a] >> (7 - k)) & 1, (mg[a] >> (7 - k)) & 1
            if gb:
                px[((a & 31) * 8 + k, y)] = 1
            elif not mb:
                px[((a & 31) * 8 + k, y)] = 2
    return px


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('z80')
    ap.add_argument('rzx', nargs='+')
    ap.add_argument('-o', default='catalogue.png')
    ap.add_argument('--stop', type=int)
    a = ap.parse_args(argv)
    from PIL import Image, ImageDraw
    from skoolkit.snapshot import Snapshot
    base = bytearray(rb.mem64(Snapshot.get(a.z80)))
    seq = []
    for i, r in enumerate(a.rzx):
        seq += [(i * 10 ** 7 + s[0],) + s[1:] for s in collect(r, a.stop)]
    renders = collections.defaultdict(list)
    for s in seq:
        renders[s[0]].append(s)
    cache = {}

    def pix(s):
        k = (s[1], s[2], s[3], s[5])
        if k not in cache:
            cache[k] = piece_pixels(base, s[1], s[2], s[3], s[5])
        return cache[k]
    groups = collections.defaultdict(list)      # page set -> [figure pixels]
    shown = collections.defaultdict(set)
    stats = collections.defaultdict(lambda: {'pieces': set(), 'renders': 0, 'lo': 0xFFFF, 'hi': 0})
    for rno in sorted(renders):
        figs = []                                # one figure = pieces whose boxes touch
        for s in renders[rno]:
            px = pix(s)
            if not px:
                continue
            box = (min(p[0] for p in px), min(p[1] for p in px), max(p[0] for p in px), max(p[1] for p in px))
            nf = [box, dict(px), {(s[1], s[2], s[3])}, {s[4] >> 8}, [s[4]]]
            for f in [f for f in figs if box[0] <= f[0][2] + 1 and f[0][0] <= box[2] + 1 and
                      box[1] <= f[0][3] + 1 and f[0][1] <= box[3] + 1]:
                figs.remove(f)
                nf[0] = (min(nf[0][0], f[0][0]), min(nf[0][1], f[0][1]),
                         max(nf[0][2], f[0][2]), max(nf[0][3], f[0][3]))
                nf[1].update(f[1])
                nf[2] |= f[2]
                nf[3] |= f[3]
                nf[4] += f[4]
            figs.append(nf)
        for box, px, sig, pgs, sps in figs:
            key = tuple(sorted(pgs))
            st = stats[key]
            st['renders'] += 1
            st['pieces'] |= sig
            st['lo'], st['hi'] = min([st['lo']] + sps), max([st['hi']] + sps)
            if sig <= shown[key] or len(groups[key]) >= 12:
                continue
            shown[key] |= sig
            groups[key].append(px)
    info = {}
    rows = []
    for key in sorted(groups):
        name = '+'.join('%02X' % p for p in key)
        st = stats[key]
        info[name] = {'distinct_pieces': len(st['pieces']), 'figure_sightings': st['renders'],
                      'stream_range': ['0x%04X' % st['lo'], '0x%04X' % st['hi']],
                      'runtime_buffer': any(0x95 <= p <= 0x98 for p in key)}
        rows.append((name, groups[key]))
    S, PAD, LAB = 3, 6, 110
    imgs = []
    for pg, comps in rows:
        cells = []
        for px in comps:
            xs, ys = [p[0] for p in px], [p[1] for p in px]
            x0, y0 = min(xs), min(ys)
            w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
            im = Image.new('RGB', (w * S, h * S), (110, 110, 110))
            d = ImageDraw.Draw(im)
            for (x, y), v in px.items():
                c = (255, 255, 255) if v == 1 else (0, 0, 0)
                d.rectangle([(x - x0) * S, (y - y0) * S, (x - x0) * S + S - 1, (y - y0) * S + S - 1], fill=c)
            cells.append(im)
        W = LAB + sum(c.width + PAD for c in cells)
        H = max([c.height for c in cells] + [30]) + PAD
        row = Image.new('RGB', (W, H), (40, 40, 40))
        ImageDraw.Draw(row).text((4, 4), 'pages %s\n%d pieces%s' % (
            pg.replace('+', '\n+'), info[pg]['distinct_pieces'], '\nruntime buf' if info[pg]['runtime_buffer'] else ''),
            fill=(255, 255, 0))
        x = LAB
        for c in cells:
            row.paste(c, (x, PAD // 2))
            x += c.width + PAD
        imgs.append(row)
    W, H = max(i.width for i in imgs), sum(i.height for i in imgs)
    sheet = Image.new('RGB', (W, H), (40, 40, 40))
    y = 0
    for i in imgs:
        sheet.paste(i, (0, y))
        y += i.height
    sheet.save(a.o)
    json.dump(info, open(os.path.splitext(a.o)[0] + '.json', 'w'), indent=1)
    print('%d pieces, %d pages -> %s' % (len(seq), len(rows), a.o))


if __name__ == '__main__':
    sys.exit(main())
