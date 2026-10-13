"""`nexclash.py preview GAME.z80 --rzx R [--every N | --at F,F,...] [--plot ADDR ...] [--buffer
ADDR:STRIDE:LINES] -o sheet.png` - what the game draws, for the design round with the user
(PLAYBOOK 3b) and for finding which routine draws which figure.

Renders the ULA screen at the chosen frames (a contact sheet). With --plot (routine entry
addresses, repeatable): every call is followed from its entry until it returns (SP back above the
entry SP) and the bytes it writes are attributed to (entry, caller) - the caller is the first word
on the stack that follows a CALL instruction. Those bytes are coloured per group, on the screen
or, with --buffer, on a linear back buffer (ADDR = first byte, STRIDE = bytes per line, LINES)
drawn next to each screen. Prints the groups: calls, bytes written, x/y ranges of the writes.

The true pixels of a masked figure (ink / opaque / transparent) need the plot run twice on a
cleared and a filled buffer - engine-specific (midres.truth); this command shows the bytes drawn.
Game-independent; extend freely (keep existing report lines; add new ones) and run
`python selftest.py --tools`.
"""
import collections
from .simrun import run

CALLOPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
PAL = [(0, 0, 0), (0, 0, 192), (192, 0, 0), (192, 0, 192), (0, 192, 0), (0, 192, 192), (192, 192, 0), (192, 192, 192)]
GROUP_COL = [(255, 0, 0), (0, 255, 0), (0, 128, 255), (255, 0, 255), (255, 160, 0), (0, 255, 255), (255, 255, 0),
             (160, 80, 255), (255, 128, 128), (128, 255, 128), (128, 128, 255), (200, 200, 0)]


def screen_xy(a):
    """ULA pixel address -> (column 0-31, line 0-191)."""
    o = a - 0x4000
    return o & 31, ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


class Preview:
    def __init__(self, frames, plots, buffer):
        self.want = set(frames)
        self.plots = set(plots or ())
        self.buffer = buffer                        # (addr, stride, lines) or None
        self.sim = None
        self.frame = 0
        self.stack = []                             # open calls: (entry, caller, sp)
        self.drawn = {}                             # address -> group of the plot that wrote it last
        self.groups = collections.OrderedDict()     # (entry, caller) -> stats
        self.shots = []

    def on_sim(self, sim):
        self.sim = sim

    def _caller(self, sp):
        m = self.sim.memory
        for i in range(8):                          # the return address, or (JP-entered) a deeper one
            w = m[(sp + 2 * i) & 0xFFFF] | m[(sp + 2 * i + 1) & 0xFFFF] << 8
            if w >= 3 and m[w - 3] in CALLOPS:
                return w
        return None

    def before(self, pc):
        R = self.sim.registers
        while self.stack and R[12] > self.stack[-1][2]:
            self.stack.pop()
        if pc in self.plots:
            sp = R[12]
            key = (pc, self._caller(sp))
            g = self.groups.setdefault(key, {'calls': 0, 'bytes': 0, 'x': [999, -1], 'y': [999, -1]})
            g['calls'] += 1
            self.stack.append((pc, key, sp))

    def on_write(self, a, v, pc, mem):
        if not self.stack:
            self.drawn.pop(a, None)                 # overwritten by something else (scenery, a clear)
            return
        key = self.stack[-1][1]
        g = self.groups[key]
        if self.buffer and self.buffer[0] <= a < self.buffer[0] + self.buffer[1] * self.buffer[2]:
            y, x = divmod(a - self.buffer[0], self.buffer[1])
        elif 0x4000 <= a < 0x5800:
            x, y = screen_xy(a)
        else:
            return
        g['bytes'] += 1
        g['x'] = [min(g['x'][0], x * 8), max(g['x'][1], x * 8 + 7)]
        g['y'] = [min(g['y'][0], y), max(g['y'][1], y)]
        self.drawn[a] = list(self.groups).index(key)

    def on_frame(self, n):
        self.frame = n
        if n in self.want:
            m = self.sim.memory
            buf = None
            if self.buffer:
                a, st, ln = self.buffer
                buf = bytes(m[a + i] for i in range(st * ln))
            self.shots.append((n, bytes(m[0x4000 + i] for i in range(6912)), buf, dict(self.drawn)))


def _screen_img(scr, drawn):
    from PIL import Image
    im = Image.new('RGB', (256, 192))
    px = im.load()
    for y in range(192):
        base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        for cx in range(32):
            v, at = scr[base + cx], scr[0x1800 + (y >> 3) * 32 + cx]
            ink, paper = PAL[at & 7], PAL[(at >> 3) & 7]
            g = drawn.get(0x4000 + base + cx)
            for i in range(8):
                on = v & (0x80 >> i)
                if g is None:
                    c = ink if on else paper
                else:
                    gc = GROUP_COL[g % len(GROUP_COL)]
                    c = gc if on else tuple(k // 4 for k in gc)
                px[cx * 8 + i, y] = c
    return im


def _buffer_img(buf, buffer, drawn):
    from PIL import Image
    a0, st, ln = buffer
    im = Image.new('RGB', (st * 8, ln))
    px = im.load()
    for y in range(ln):
        for cx in range(st):
            v = buf[y * st + cx]
            g = drawn.get(a0 + y * st + cx)
            for i in range(8):
                on = v & (0x80 >> i)
                if g is None:
                    c = (170, 170, 170) if on else (40, 40, 40)
                else:
                    gc = GROUP_COL[g % len(GROUP_COL)]
                    c = gc if on else tuple(k // 4 for k in gc)
                px[cx * 8 + i, y] = c
    return im


def preview(z80, rzx=None, out='preview.png', at=None, every=None, plots=None, buffer=None, frames=None,
            keys=None, stop=None):
    """-> (report text, result dict). Writes the contact sheet to `out` (PNG)."""
    from PIL import Image
    want = list(at or [])
    if not want:
        n = stop or frames or 500
        step = every or max(1, n // 8)
        want = list(range(step, n + 1, step))[:24]
    stop = stop or (max(want) + 1 if rzx else None)
    pv = Preview(want, plots, buffer)
    nfr = run(z80, rzx, pv, frames=frames or max(want) + 1, keys=keys, stop=stop)
    tiles = []
    for n, scr, buf, drawn in pv.shots:
        im = _screen_img(scr, drawn)
        if buf is not None:
            b = _buffer_img(buf, buffer, drawn)
            row = Image.new('RGB', (256 + 8 + b.width, max(192, b.height)), (30, 30, 30))
            row.paste(im, (0, 0))
            row.paste(b, (264, 0))
            im = row
        tiles.append(im)
    lines = ['Source    : %s, %d frames; shots at %s' % (', '.join(rzx) if rzx else 'free run', nfr,
                                                         ', '.join(str(s[0]) for s in pv.shots) or 'none')]
    if tiles:
        cols = 2 if tiles[0].width > 300 else 4
        w, h = tiles[0].width, max(t.height for t in tiles)
        sheet = Image.new('RGB', (cols * (w + 4), ((len(tiles) + cols - 1) // cols) * (h + 4)), (20, 20, 20))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
        sheet.save(out)
        lines.append('Sheet     : %s (%d x %d)' % (out, sheet.width, sheet.height))
    for k, ((entry, caller), g) in enumerate(pv.groups.items()):
        lines.append('Group %-3d : plot %d (0x%04X) from %s: %d calls, %d bytes drawn, x %s, y %s (colour %s)' % (
            k, entry, entry, '%d (0x%04X)' % (caller, caller) if caller is not None else '?', g['calls'], g['bytes'],
            '%d-%d' % tuple(g['x']) if g['bytes'] else '-', '%d-%d' % tuple(g['y']) if g['bytes'] else '-',
            GROUP_COL[k % len(GROUP_COL)]))
    return '\n'.join(lines), {'shots': [s[0] for s in pv.shots], 'groups': {k: dict(v) for k, v in pv.groups.items()}}
