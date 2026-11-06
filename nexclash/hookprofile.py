"""Optional instruction-cost breakdown for Ikari's existing verified hook path.

python -m nexclash.hookprofile --ikari --rzx /path/ik_2pw.rzx --frames 1200 --output profile.json
Runs the existing differential verifier with observational instrumentation; no game output changes.
Counts upload port instructions separately from generation, lookup and cache work. T/clock is a
simulator estimate, excludes contention and DMA stalls, and is not measured hardware elapsed time.
"""
import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path

from . import hooklib


class InstructionCosts:
    def __init__(self, ranges, entries=()):
        self.ranges, self.entries = ranges, dict(entries)
        self.ns = None
        self.raw = collections.Counter()
        self.equivalent = collections.Counter()
        self.calls = collections.Counter()
        self.frame = collections.Counter()
        self.frames = []
        self.upload_bytes = 0

    def before(self, sim):
        r, m = sim.registers, sim.memory
        pc = r[24]
        self.t0 = r[25]
        self.factor = (1, 2, 4, 8)[self.ns.nr[7] & 3]
        self.category = next((name for lo, hi, name in self.ranges if lo <= pc < hi), None)
        if pc in self.entries:
            self.calls[self.entries[pc]] += 1
        # Ikari uses OUT (C),A for pattern bytes, not block I/O.
        if self.category and m[pc] == 0xED and m[pc + 1] == 0x79 and r[3] == 0x5B:
            self.category = 'pattern port instructions'
            self.upload_bytes += 1

    def after(self, sim):
        if self.category:
            dt = sim.registers[25] - self.t0
            self.raw[self.category] += dt
            self.equivalent[self.category] += dt / self.factor
            self.frame[self.category] += dt / self.factor

    def end_frame(self):
        self.frames.append(dict(self.frame))
        self.frame.clear()

    def report(self):
        keys = sorted(self.equivalent)
        return {'units': 'simulated 3.5MHz-equivalent T; no contention or DMA timing',
                'sync_intervals': len(self.frames), 'calls': dict(self.calls),
                'pattern_bytes': self.upload_bytes,
                'raw_cpu_t': dict(self.raw), 'equivalent_t': dict(self.equivalent),
                'per_sync': {k: {'median': statistics.median(f.get(k, 0) for f in self.frames),
                                  'max': max(f.get(k, 0) for f in self.frames),
                                  'mean': sum(f.get(k, 0) for f in self.frames) / len(self.frames)}
                             for k in keys} if self.frames else {}}


def ikari_profiler(patch):
    # Assemble only to obtain all labels; do not regenerate a pinned profile or build a game.
    _, sy = hooklib.assemble(str(Path(hooklib.ROOT) / 'asm/ikari_warriors_hooks.asm'))
    assert sy['upload'] == patch.syms['upload'] and sy['uploadn'] == patch.syms['uploadn']
    # The active colour/seam extension follows rom_end. Keep it separate from the original colour routine.
    ranges = [(sy['find'], sy['upload'], 'cache search'),
              (sy['upload'], sy['colour'], 'pixel generation and upload setup'),
              (sy['colour'], sy['rom_end'], 'colour lookup'),
              (sy['rom_end'], patch.regblock, 'colour and seam extension'),
              (0x2400, sy['find'], 'other hooks')]
    return InstructionCosts(ranges, ((sy[n], n) for n in ('find', 'upload', 'uploadn', 'colour')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ikari', action='store_true', required=True)
    parser.add_argument('--rzx', required=True)
    parser.add_argument('--frames', type=int, default=1200)
    parser.add_argument('--mode', choices=('default', 'enhanced'), default='default')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error('--frames must be positive')
    from . import ikari_warriors as ik
    patch = ik.set_patch(args.mode)
    profiler = ikari_profiler(patch)
    patterns = ik.default_patterns(args.rzx, stop=args.frames)
    counters, checks, failures = ik.set_check(patch, args.rzx, patterns, args.mode,
                                             stop=args.frames, profiler=profiler)
    result = profiler.report()
    result.update(recording=Path(args.rzx).name,
                  recording_md5=hashlib.md5(Path(args.rzx).read_bytes()).hexdigest(),
                  hook_sha256=hashlib.sha256(patch.rom_code).hexdigest(), mode=args.mode,
                  requested_frames=args.frames, verify_counters=dict(counters),
                  picture_checks=dict(checks), failures=failures)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print('Profile: %s; %d sync intervals; %d pattern bytes; differential failures: %s' %
          (args.output, result['sync_intervals'], result['pattern_bytes'], result['failures']))
    if not result['sync_intervals'] or result['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
