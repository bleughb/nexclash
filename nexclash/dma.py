"""Strict functional model of the synchronous DMA subset used by the shared hooks.

No arbitration, interrupts, timing, Layer 2 XY, burst or port $0B emulation. Unsupported
commands fail instead of silently granting verification. Physical RAM is a caller-supplied
byte array; virtual reads/writes use callbacks (the engine must supply real MMU semantics).
Independent implementation from the register descriptions in zxnDDMA_guide.txt, not its examples.

`python -m nexclash.dma [--no-blitter | --cpu-only]` assembles and checks the selected policy.
Default policy is blitter preferred, with runtime core/ownership gating and fallback.
"""
import argparse
import collections


class DMAError(ValueError):
    pass


class DMA:
    def __init__(self, read, write, out, *, blitter=False, physical=None, stall=None):
        self.read, self.write, self.out = read, write, out
        self.blitter, self.physical, self.stall = blitter, physical, stall
        self.stats = collections.Counter()
        self.a = self.b = self.length = 0
        self.wr1 = self.wr2 = self.wr4 = 0
        self.pending = []
        self.reset()

    def reset(self):
        # C3 retains base addresses/WR0..4, but clears extensions and timing.
        self.flags = self.ahi = self.bhi = 0
        self.width = self.rows = self.astride = self.bstride = 0
        self.transparent = self.fill = 0
        self.loaded = False

    def _set(self, key, value):
        if isinstance(key, tuple):
            name, shift = key
            old = getattr(self, name)
            setattr(self, name, (old & ~(255 << shift)) | value << shift)
        else:
            setattr(self, key, value)

    def feed(self, value):
        self.stats['program bytes'] += 1
        if self.pending:
            self._set(self.pending.pop(0), value)
            return
        if value == 0x83:
            return
        if value == 0xC3:
            self.reset()
        elif value == 0xCF:
            self.loaded = True
        elif value == 0x87:
            self.execute()
        elif value == 0x82:
            pass                         # stop at end (auto restart unsupported)
        elif value in (0xD7, 0xDB, 0xDF, 0xE3, 0xE7, 0xEB, 0xEF, 0xF3, 0xF7):
            if not self.blitter:
                raise DMAError('extended DMA command on a core without blitter')
            names = {0xD7: 'ahi', 0xDB: 'bhi', 0xDF: 'flags', 0xE3: 'width',
                     0xE7: 'rows', 0xEB: 'astride', 0xEF: 'bstride',
                     0xF3: 'transparent', 0xF7: 'fill'}
            name = names[value]
            self.pending = [(name, 0), (name, 8)] if value in (0xE3, 0xE7, 0xEB, 0xEF) else [name]
        elif value in (0x7D, 0x1D):
            self.pending = [('a', 0), ('a', 8)]
            if value == 0x7D:
                self.pending += [('length', 0), ('length', 8)]
        elif value in (0x14, 0x24):
            self.wr1 = value
        elif value in (0x10, 0x28):
            self.wr2 = value
        elif value == 0xAD:
            self.wr4 = value
            self.pending = [('b', 0), ('b', 8)]
        else:
            raise DMAError('unsupported DMA command %02X' % value)

    def execute(self):
        if not self.loaded:
            raise DMAError('enable without load')
        if self.flags & ~15:
            raise DMAError('Layer 2 XY/hidden/unknown flags not modelled')
        if self.wr1 not in (0x14, 0x24) or self.wr2 not in (0x10, 0x28) or self.wr4 != 0xAD:
            raise DMAError('unsupported port or transfer mode')
        physical = bool(self.flags & 1)
        if physical and self.physical is None:
            raise DMAError('physical RAM not supplied')
        if self.wr2 == 0x28 and self.flags:
            raise DMAError('extended I/O combinations not modelled')
        mask = 0x3FFFFF if physical else 0xFFFF
        a = ((self.ahi << 16 if physical else 0) | self.a) & mask
        b = ((self.bhi << 16 if physical else 0) | self.b) & mask
        width = max(1, self.width if self.flags & 2 else self.length)
        rows = max(1, self.rows) if self.flags & 2 else 1
        # Functional safety limit, not a hardware limit; bound accidental huge jobs in tests.
        if width * rows > 4 * 1024 * 1024:
            raise DMAError('model job exceeds 4 MiB')
        transferred = 0
        for row in range(rows):
            src = (a + row * self.astride) & mask
            dst = (b + row * self.bstride) & mask
            for col in range(width):
                sa = (src + (col if self.wr1 == 0x14 else 0)) & mask
                da = (dst + (col if self.wr2 == 0x10 else 0)) & mask
                if self.flags & 8:
                    value = self.fill
                else:
                    value = self._read(sa, physical)
                    self.stats['reads'] += 1
                transferred += 1
                if self.flags & 4 and value == self.transparent:
                    self.stats['skips'] += 1
                    continue
                if self.wr2 == 0x28:
                    self.out(da, value)
                elif physical:
                    self._physical_check(da)
                    self.physical[da] = value
                else:
                    self.write(da, value)
                self.stats['writes'] += 1
        self.stats['jobs'] += 1
        self.stats['bytes visited'] += transferred
        self.loaded = False
        if self.stall:
            self.stall(transferred)       # explicitly injected elapsed time, never inferred CPU T

    def _physical_check(self, addr):
        if not 0 <= addr < len(self.physical):
            raise DMAError('address outside installed physical RAM')

    def _read(self, addr, physical):
        if physical:
            self._physical_check(addr)
            return self.physical[addr]
        return self.read(addr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument('--no-blitter', action='store_true', help='ordinary DMA/CPU only; no DDMA commands')
    policy.add_argument('--cpu-only', action='store_true', help='disable ordinary DMA as well as the blitter')
    args = parser.parse_args()
    from .dma_check import check_policy
    define = 'HLIB_CPU_ONLY' if args.cpu_only else 'HLIB_NO_BLITTER' if args.no_blitter else None
    check_policy(define, verbose=True)


if __name__ == '__main__':
    main()
