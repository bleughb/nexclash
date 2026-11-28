"""Compare the assembled CPC sprite writes to a separately decoded owner disk.

python -m nexclash.gryzor_cpc_verify DISK ENHANCED.nex RECORDING.rzx [--quick N]
"""
import argparse
import collections
from functools import lru_cache
from pathlib import Path
from struct import unpack_from
import sys

from . import gryzor as g, gryzor_cpc as cpc, recolour, z80n
from skoolkit.simulator import Simulator
from skoolkit.simutils import PC, SP


def disk_section(disk):
    # Standard 40-track DSK. The literal region starts on track 8, payload
    # byte 3258. Join physical sectors, independently of the NEX copy runs.
    assert disk.startswith(b'MV - CPCEMU') and disk[48:50] == bytes((40, 1))
    tracks = []
    for i in range(40):
        t = disk[256+4864*i:256+4864*(i+1)]
        assert t[:10] == b'Track-Info' and t[21] == 9
        tracks.append(t[256:])
    start = 8*4608+3258
    return bytes(0x483a) + b''.join(tracks)[start:start+0x74a5-0x483a]


def decode(section, pose):
    pixels = {}
    for ptr in pose.lists:
        while section[ptr] != 0x80:
            dx, dy, pid = unpack_from('<bbB', section, ptr)
            ptr += 3
            dynamic = pid in (0xa1, 0x9e) and pose.exposure
            if dynamic:
                pid = {0xa1: 0xe4, 0x9e: 0xc8}[pid]
            width, height, src = unpack_from('<BBH', section, 0x4cc7+pid*4)
            if dynamic:
                src += (height-pose.exposure)*width
                height = pose.exposure
            for row in range(height):
                for col in range(2*width):
                    value = section[src+row*width+col//2]
                    pen = sum((value >> (bit-col%2) & 1) << n
                              for n, bit in enumerate((7, 3, 5, 1)))
                    if pen:
                        x, y = 4*dx+2*col, -dy-row
                        pixels[x, y] = pixels[x+1, y] = pen
    return pixels


class Model(g.NextState):
    def visible(self):
        return [i for i, attr in enumerate(self.attr) if attr[3] & 128]


def boot(banks):
    mem = bytearray(65536)
    mem[0xc000:] = banks[10]
    mem[0x4000:0x8000] = banks[21]
    ns, inks, mappings = Model(), [], []
    sim = Simulator(mem)
    def write(reg, value):
        if reg in (0x52, 0x53):
            mappings.append((reg, value))
        if reg == 0x44:
            inks.append(value)
        ns.nextreg(reg, value)
    z80n.install(sim, write)
    sim.set_tracer(ns)
    sim.registers[SP] = 0xfff0
    sim.registers[PC] = 0xd000
    assert g._run(sim, 0) and ns.slots[2] == 10 and ns.slots[3] == 11
    assert mappings == [(0x52, 42), (0x53, 43), (0x52, 10), (0x53, 11)]
    rgb = [(a << 1) | b for a, b in zip(inks[::2], inks[1::2])]
    assert rgb == [int(s, 8) for s in '004 774 777 000 444 040 470 044 077 440 007 047 744 740 400 700'.split()]
    return bytes(ns.pat), ns.uploads


def plot_key(pc, regs, mem):
    kind = g.ENTRIES[pc][4]
    gfx = regs[6]*256+regs[7]
    screen = regs[4]*256+regs[5]
    rows, skip = regs[2], 0
    if kind == 'b4':
        gfx, screen, rows = regs[8]*256+regs[9], gfx, 2
    if kind == 'clip':
        rows = mem[g.ROWS]
        skip = min(4, 8-regs[3].bit_length())
        screen = (screen & 0xff00) | ((screen+skip) & 255)
    y, col = g.scr_yx(screen)
    origin = ((col-skip)*8, y)
    w = g.ENTRIES[pc][3]
    key = gfx, g.shape_of(w, rows)
    if 0xc000 <= gfx < 0xdd00:
        mode, direction = mem[0xb405], mem[0xb400]
        if mode in (1, 5):
            stride = (mem[0xb406] & 7) + (0 if direction%2 else 8)
            part = 1 if w == 4 else 2 if mem[0xb3f5] else 2+(direction+1)//2
            if part == 1 and not mem[0xb3f5] and direction >= 3:
                stride += 16 if direction <= 4 else 48
            key = part*256+stride, 1
        if mode == 3:
            phase = {0xd800:0, 0xd890:1, 0xd920:2, 0xd9b0:3}.get(gfx, 0)
            if mem[0xb3e1] and phase == 3:
                phase = 4
            key = 0x600+phase+(8 if mem[0xb430] == 0xcb else 0), 1
    return key, origin


class FigureCheck:
    def __init__(self, disk, nex):
        self.banks = recolour.banks(nex)
        self.section = disk_section(disk)
        assert self.section[0x483a:] == self.banks[21][0x83a:0x34a5]
        self.patterns, self.uploaded = boot(self.banks)
        self.draws = cpc.mapping()

    def start(self, eng):
        eng.ns = Model()
        eng.ns.pat[:] = self.patterns

    @lru_cache(None)
    def expected(self, draw):
        return {(draw.x+(-1-x if draw.mirror else x), draw.y+y): pen
                for (x,y), pen in decode(self.section, draw.pose).items()}

    @lru_cache(None)
    def actual(self, sprites):
        pixels = {}
        for pattern, x, y, mirror in sprites:
            for k in range(256):
                byte = self.patterns[128*pattern+k//2]
                pen = byte & 15 if k%2 else byte >> 4
                if pen:
                    left = x+2*((15-k%16) if mirror else k%16)
                    pixels[left, y+k//16] = pixels[left+1, y+k//16] = pen
        return pixels

    def compare(self, eng, start, end, key, origin, stats, fail):
        if key not in self.draws:
            fail('unmapped Spectrum figure', key)
            return
        sprites = []
        for x,y,flags,pat,scale in eng.ns.attr[start:end]:
            if pat & 0xc0 != 0xc0 or scale & 0xbf != 0x88 or flags & 0xf6:
                fail('CPC sprite attributes', key, (x,y,flags,pat,scale))
            dx = ((x + (flags & 1)*256 - 32 - origin[0] + 256) % 512) - 256
            dy = ((y - 32 - origin[1] + 128) % 256) - 128
            sprites.append(((pat & 63)*2+(scale >> 6 & 1), dx, dy, bool(flags & 8)))
        if self.actual(tuple(sprites)) != self.expected(self.draws[key]):
            fail('CPC pose pixels or position', key, origin, sprites)
        stats['figure comparisons'] += 1
        stats['sprite attributes compared'] += len(sprites)

    def plot(self, eng, pc, regs, mem, first, stats, fail):
        last = eng.page[eng.patch.syms['nsp'] - 0x2000]
        self.compare(eng, first, last, *plot_key(pc, regs, mem), stats, fail)
        stats['most sprites'] = max(stats['most sprites'], last)

    def tick(self, eng, mem, stats, fail):
        first = 0
        for i in range(4):
            a = 0xb6f7+8*i
            y, x, img = unpack_from('<BBH', bytes(mem[a:a+4]))
            x = x-256 if x >= 128 else x
            phase = mem[0xb412+2*i]
            if x < -16 or img not in (0xe140, 0xdfc0):
                continue
            if img == 0xe140 and phase > 9:
                continue
            key = (0x700 + (phase if img == 0xe140 else 10), 1)
            num = 1 if img == 0xe140 else 2
            self.compare(eng, first, first+num, key, (x*2, y), stats, fail)
            first += num
            stats['wall draws'] += 1
        if first != eng.page[eng.patch.syms['nsp']-0x2000]:
            fail('wall sprite count', first)
        previous = eng.page[eng.patch.syms['shown']-0x2000]
        if eng.ns.visible() != list(range(max(previous, first))):
            fail('stale or missing sprite at tick', previous, first)
        stats['ticks checked'] += 1


def run(disk, nex, recording, stop=None, say=print):
    check = FigureCheck(disk, nex)
    patch = g.GryzorPatch()
    patch.pl = b''
    patch.page = check.banks[12][:8192]
    patch.store = {25:check.banks[12][8192:]}
    counts, examples, _ = g.verify(patch, str(recording), stop=stop, figure_check=check)
    say(f'{recording.name} boot bytes {check.uploaded} {dict(counts)} {dict(examples)}')
    return not any(k.endswith('!') for k in counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('disk', 'nex', 'recording'):
        parser.add_argument(arg, type=Path)
    parser.add_argument('--quick', type=int)
    args = parser.parse_args()
    sys.exit(not run(args.disk.read_bytes(), args.nex.read_bytes(), args.recording, args.quick))
