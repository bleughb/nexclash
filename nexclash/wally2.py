"""Everyone's a Wally, updated (Mikro-Gen; 48K code in a 128K snapshot) - engine 'wally2', record
everyones_a_wally_updated. A new game to the 2026-10-14 standard; the first version (engine 'wally',
nexclash/wally.py, record wally) is frozen and untouched. Additive module.

Phase A (this file so far): capture of every figure plot from the RZX, the colour sheets and the
preview frames - no patch yet. Game facts: games/everyones_a_wally_updated.md.

  Render: the game restores a clean back buffer (pixels 0x6B00-0x7AFF = screen lines 64-191, row y at
  0x6300 + y*32; attributes 0xFC00-0xFDFF, cell at 0xFB00 + (y & 248)*4 + x/8), its room logic plots
  the objects (B, C), the render (47574) plots the gang (A), then 47611 copies pixels (row table
  33400, unrolled LDI 47653) and 47637 the attributes. Interrupts are never on (isr: 0 accepted).
  A 45286  gang member, IY = descriptor 48231..48235 (+0 frame, +5 x, +10 y, +15 room, +30 attr,
           +35/+40 gfx base), 16x32 masked, rows of 4 bytes (mask L, mask R, gfx L, gfx R), frame
           data at base + frame*128; paints (IY+30) into 2-3 x 4-5 attribute cells.
  B 43168  masked 16x16 object, A = frame, data 33656 + A*32 (rows of 4 bytes as A), position
           (43064 x, 43065 y). 21 callers.
  C 43069  OR-only 16x16 object, A = frame, data 33656 + A*32 (rows of 2 bytes: gfx L, gfx R).
           15 callers.
  61329    paints the cells of the last B/C plot with (62063) (5 callers).
  33251    mirrors 35064-35255 (B frames 44-49) IN PLACE when 61511 toggles (61510) = 1: each byte
           pair (L, R) -> (rev R, rev L); colour keys are taken in the unmirrored orientation.
"""
import collections
import json
import os

A_PLOT, B_PLOT, C_PLOT, PAINT, COPY, COMMIT, MIRROR = 45286, 43168, 43069, 61329, 47611, 47637, 61511
RESTORE = 61090                 # clean store 0x5B00/0xFE00 -> back buffer: plots since the last commit are wiped
GFX = 33656
MIR_LO, MIR_HI, MIR_FLAG = 35064, 35256, 61510
POS = 43064
PAINT_COL = 62063
BUF, ATTRBUF = (0x6B00, 0x7B00), (0xFC00, 0xFE00)
A_CALLERS = (47597, 61487, 61887)
B_CALLERS = (60787, 60823, 61544, 61560, 61777, 62044, 62055, 62184, 62237, 62350, 62361, 62416, 62430,
             62514, 62664, 62752, 62795, 63041, 63171, 63280, 63708)
C_CALLERS = (61150, 62288, 62298, 62605, 62712, 62854, 62866, 62880, 62892, 63249, 63337, 63448, 63534,
             63904, 64050)
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
CBLACK = 8                          # palette index of black (0 is transparent)
GROUPS = ('Gang members', 'Masked objects', 'OR objects', 'From the code (not in the recording)')
GANG = ('desc 0', 'desc 1', 'desc 2', 'desc 3', 'desc 4')

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'everyones_a_wally_updated_colours.json')


def cidx(c, bright):
    return CBLACK if c == 0 else c + 8 * bright


def ink_of(attr):
    return cidx(attr & 7, (attr >> 6) & 1)


def rev(v):
    return int('{:08b}'.format(v)[::-1], 2)


def canonical(addr, data, mirrored):
    """Graphics bytes as plotted -> (bytes in the unmirrored orientation, drawn mirrored?). Only the
    in-place mirrored block (35064-35255) can be mirrored; pairs are aligned on 35064."""
    if not mirrored or not (MIR_LO <= addr < MIR_HI):
        return data, 0
    out = bytearray(data)
    for i in range(0, len(data) - 1, 2):
        out[i], out[i + 1] = rev(data[i + 1]), rev(data[i])
    return bytes(out), 1


def ckey(kind, addr):
    """Colour-map key: one graphics byte (M = masked plotters A/B, O = the OR plotter C)."""
    return '%s:%04X' % (kind, addr)


def rotl(v):
    return ((v << 1) | (v >> 7)) & 255


def entry_check(m, g):
    return m ^ rotl(g)


def static_frames(mem):
    """Frames the code passes to B / C as a constant: walk back from each CALL over instructions that
    keep A (61237 pushes and pops it) to an LD A,n. -> {('B'|'C', caller): frame}; callers whose
    frame comes from a table or a variable are left out (only a recording shows them)."""
    keep = {0x01, 0x11, 0x21, 0x22, 0x2A, 0xC5, 0xD5, 0xE5}       # LD rr,nn / LD (nn),HL / LD HL,(nn) / PUSH
    out = {}
    for kind, callers in (('B', B_CALLERS), ('C', C_CALLERS)):
        for c in callers:
            a, n = c, 0
            while n < 6:
                n += 1
                if mem[a - 2] == 0x3E:                              # LD A,n
                    out[(kind, c)] = mem[a - 1]
                    break
                if mem[a - 3] == 0xCD and mem[a - 2] | mem[a - 1] << 8 == 61237:
                    a -= 3
                    continue
                if mem[a - 3] in keep:
                    a -= 3
                    continue
                if mem[a - 4] == 0xDD and mem[a - 3] == 0x21:     # LD IX,nn
                    a -= 4
                    continue
                break
    return out


def plot_rows(kind):
    return (32, 4) if kind == 'A' else (16, 4) if kind == 'B' else (16, 2)


def sheet_part(d):
    """A plot -> a coloursheet part. Every bit of the graphics bytes (paint_clear): code 1 ink, 2 opaque
    non-ink (masked: mask 0, gfx 0 = the black outline), 0 clear (paintable as an outline)."""
    rows, bpr = plot_rows(d['k'])
    data = d['cdata']
    pixels, entries = [], {}
    masked = bpr == 4
    for r in range(rows):
        for half in (0, 1):
            j = r * bpr + (2 + half if masked else half)              # the gfx byte of this half-row
            m = data[r * bpr + half] if masked else 0xFF
            g = data[j]
            k = ckey('M' if masked else 'O', (d['gfx'] + j) & 0xFFFF)
            entries.setdefault(k, [entry_check(m if masked else 0, g), 1 if masked else 2])
            for b in range(8):
                bit = 0x80 >> b
                code = 1 if g & bit else (0 if m & bit else 2)
                c = half * 8 + b
                pixels.append((c, r, k, b, code, default_colour(d, r, c, code) if code else 0))
    return dict(id=(d['k'], d['gfx']), size=rows, w=16, h=rows, x=d['x'], y=d['y'], mir=d['mir'], vmir=0,
                group=d['group'], role=d.get('caller'), pixels=pixels, entries=entries)


def default_colour(d, r, c, code):
    """Proposed default (phase A, to confirm): gang member = its attribute ink; object = the 61329 paint
    if the game painted it, else the ink of the cell under the pixel (as the original shows it at that
    plot); opaque non-ink = black."""
    if code != 1:
        return CBLACK
    if d['k'] == 'A':
        return ink_of(d['attr'])
    if d.get('paint') is not None:
        return ink_of(d['paint'])
    at = d.get('attrs')
    if not at:
        return 7
    x = d['x'] + (15 - c if d['mir'] else c)
    y = d['y'] + r
    if not (64 <= y < 192):
        return 7
    return ink_of(at[((y - 64) >> 3) * 32 + ((x & 255) >> 3)])


class Capture:
    """simrun hooks: every A/B/C plot of a render (between commits), with the clean buffer at the
    render's first plot and the composed one at the commit (for the preview)."""

    def __init__(self, keep_screens=()):
        self.sim = None
        self.frame = 0
        self.cur = []
        self.clean = None
        self.renders = []               # dict(frame, copy, plots, clean, done)
        self.keep = set(keep_screens)   # render indexes to keep buffers of (all: None)
        self.copy = None
        self.calls = collections.Counter()
        self.dropped = 0

    def on_sim(self, sim):
        self.sim = sim

    def on_frame(self, n):
        self.frame = n

    def _bufs(self, g):
        return (bytes(g(BUF[0] + i) for i in range(BUF[1] - BUF[0])),
                bytes(g(ATTRBUF[0] + i) for i in range(ATTRBUF[1] - ATTRBUF[0])),
                bytes(g(0x4000 + i) for i in range(6912)))

    def before(self, pc):
        if pc not in (A_PLOT, B_PLOT, C_PLOT, PAINT, COPY, COMMIT, RESTORE):
            return
        if pc == RESTORE:                   # the buffer is rebuilt: earlier plots never reach the screen
            self.dropped += len(self.cur)
            self.cur, self.clean = [], None
            return
        R, m = self.sim.registers, self.sim.memory
        g = lambda a: m[a & 0xFFFF]
        ret = g(R[12]) | g(R[12] + 1) << 8
        want = self.keep is None or len(self.renders) in self.keep
        if pc in (A_PLOT, B_PLOT, C_PLOT) and not self.cur and want:
            self.clean = self._bufs(g)
        if pc == A_PLOT:
            iy = R[10] << 8 | R[11]
            base = g(iy + 35) | g(iy + 40) << 8
            gfx = (base + g(iy) * 128) & 0xFFFF
            data = bytes(g(gfx + i) for i in range(128))
            self.cur.append(dict(k='A', caller=ret - 3, gang=iy - 48231, frame=g(iy), x=g(iy + 5),
                                 y=g(iy + 10), attr=g(iy + 30), gfx=gfx, data=data, cdata=data, mir=0,
                                 group=GROUPS[0]))
            self.calls[('A', ret - 3)] += 1
        elif pc in (B_PLOT, C_PLOT):
            k = 'B' if pc == B_PLOT else 'C'
            gfx = (GFX + R[0] * 32) & 0xFFFF
            data = bytes(g(gfx + i) for i in range(64 if k == 'B' else 32))
            cd, mir = canonical(gfx, data, g(MIR_FLAG))
            at = bytes(g(ATTRBUF[0] + i) for i in range(512))
            self.cur.append(dict(k=k, caller=ret - 3, frame=R[0], x=g(POS), y=g(POS + 1), gfx=gfx, data=data,
                                 cdata=cd, mir=mir, attrs=at, paint=None,
                                 group=GROUPS[1] if k == 'B' else GROUPS[2]))
            self.calls[(k, ret - 3)] += 1
        elif pc == PAINT:
            if self.cur and self.cur[-1]['k'] in 'BC':
                self.cur[-1]['paint'] = g(PAINT_COL)
        elif pc == COPY:
            self.copy = ret - 3
        elif pc == COMMIT:
            want = self.keep is None or len(self.renders) in self.keep
            self.renders.append(dict(frame=self.frame, copy=self.copy, plots=self.cur,
                                     clean=self.clean if want else None, done=self._bufs(g) if want else None))
            self.cur, self.clean = [], None


def _mem(z80):
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    return bytearray(bytes(16384) + bytes(s.memory[16384:65536]))


def collect(cap, z80=None):
    """Capture -> coloursheet composites (+ the figures the code draws with a constant frame that the
    recording never drew)."""
    from . import coloursheet as cs
    col = cs.Collector(family=lambda p: None if p['id'][0] == 'A' else p['id'][0])
    for r in cap.renders:
        col.add_frame([sheet_part(d) for d in r['plots']])
    if z80:
        mem = _mem(z80)
        seen = {p['id'] for c in col.comps.values() for p in c['parts']}
        for (k, caller), fr in sorted(static_frames(mem).items()):
            gfx = (GFX + fr * 32) & 0xFFFF
            if (k, gfx) in seen:
                continue
            seen.add((k, gfx))
            n = 64 if k == 'B' else 32
            data = bytes(mem[gfx:gfx + n])
            p = sheet_part(dict(k=k, caller=caller, frame=fr, x=0, y=0, gfx=gfx, data=data, cdata=data, mir=0,
                                attrs=None, paint=None, group=GROUPS[3]))
            col.comps[('static', k, fr)] = dict(count=0, group=GROUPS[3], parts=[dict(p, dx=0, dy=0, dmir=0, vmir=0)])
            col.maxsize[p['id']] = p['size']
    return col.composites(list(GROUPS))


def capture(rzx, z80, stop=None, keep_screens=()):
    from . import simrun
    cap = Capture(keep_screens)
    simrun.run(z80, [rzx] if isinstance(rzx, str) else list(rzx), cap, stop=stop)
    return cap


def rgb16():
    from . import coloursheet as cs
    return cs.palette_rgb(PALETTE)


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def sheets(comps, prefix, colours=None):
    """<prefix>_PAINTING_SPRITES.png (every graphic once; + _layout.json, read back) and
    <prefix>_REFERENCE_ALL_SPRITES.png (every figure whole). Outlines paintable (paint_clear)."""
    from . import coloursheet as cs
    out = []
    for suffix, uniq in (('_PAINTING_SPRITES', True), ('_REFERENCE_ALL_SPRITES', False)):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16(), colours, unique=uniq,
                     paint_clear=True)
        out.append((png, n))
    return out


# ------------------------------------------------------------------------------------- preview

def _ula_rgb(attr, on):
    pal = rgb16()
    ink, paper, br = attr & 7, (attr >> 3) & 7, (attr >> 6) & 1
    c = ink if on else paper
    return pal[cidx(c, br)] if c else (0, 0, 0)


def _screen_img(bufs, img, ox):
    """ULA: lines 0-63 from the screen, 64-191 from the back buffer (+ attribute buffer)."""
    buf, attrs, scr = bufs
    for y in range(192):
        for xb in range(32):
            if y < 64:
                a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | xb
                v, at = scr[a], scr[6144 + (y >> 3) * 32 + xb]
            else:
                v, at = buf[(y - 64) * 32 + xb], attrs[((y - 64) >> 3) * 32 + xb]
            for b in range(8):
                img.putpixel((ox + xb * 8 + b, y), _ula_rgb(at, v & (0x80 >> b)))


def preview(cap, indexes, png, colours=None):
    """Per shot one row: the original | the planned build (clean scenery on the ULA, every figure as a
    sprite in plot order - later plots in front - in the proposed default colours or the map). 2x."""
    from PIL import Image
    pal = rgb16()
    cmap = colours or {}
    shots = [cap.renders[i] for i in indexes if cap.renders[i]['done'] and cap.renders[i]['clean']]
    img = Image.new('RGB', (256 * 2 + 8, 196 * len(shots)), (40, 40, 40))
    for n, r in enumerate(shots):
        sub = Image.new('RGB', (520, 192), (40, 40, 40))
        _screen_img(r['done'], sub, 0)
        _screen_img(r['clean'], sub, 264)
        clean_attrs = r['clean'][1]
        for d in r['plots']:
            d = dict(d, attrs=clean_attrs) if d['k'] != 'A' else d
            p = sheet_part(d)
            for c, rr, key, bit, code, dflt in p['pixels']:
                e = cmap.get(key)
                v = (e[2][bit] if e else 0) or dflt
                if not code and not v:
                    continue
                x = d['x'] + (15 - c if d['mir'] else c)
                y = d['y'] + rr
                if 0 <= x < 256 and 64 <= y < 192:
                    sub.putpixel((264 + x, y), pal[v])
        img.paste(sub, (0, 196 * n))
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(png)
    return len(shots)


def report(cap):
    """Plot counts per plotter and caller, coverage of the callers in the code."""
    lines = []
    for k, callers in (('A', A_CALLERS), ('B', B_CALLERS), ('C', C_CALLERS)):
        seen = {c for (kk, c) in cap.calls if kk == k}
        lines.append('%s: %d plots, %d of %d callers in the recording; not reached: %s' % (
            k, sum(n for (kk, _), n in cap.calls.items() if kk == k), len(seen & set(callers)), len(callers),
            ' '.join(str(c) for c in callers if c not in seen) or '-'))
    lines.append('plots wiped by a buffer restore before any commit (never shown): %d' % cap.dropped)
    return lines


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.wally2',
                                 description="Everyone's a Wally (updated): colour sheets and preview")
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='RZX -> the two sheets + layout JSON (game graphics: keep private)')
    p.add_argument('rzx', nargs='+')
    p.add_argument('--z80', required=True)
    p.add_argument('-o', '--output', default='everyones_a_wally_updated')
    p.add_argument('--preview', help='also write preview frames (PNG) at these renders, e.g. 100,800,2000')
    p.add_argument('--stop', type=int)
    a = ap.parse_args(argv)
    idx = [int(x) for x in a.preview.split(',')] if a.preview else []
    cap = capture(a.rzx, a.z80, a.stop, idx)
    for line in report(cap):
        print(line)
    comps = collect(cap, a.z80)
    for png, n in sheets(comps, a.output, load_colours()):
        print('%d figures -> %s' % (n, png))
    if idx:
        n = preview(cap, idx, a.output + '_preview.png', load_colours())
        print('%d shots -> %s_preview.png' % (n, a.output))


if __name__ == '__main__':
    _main()
