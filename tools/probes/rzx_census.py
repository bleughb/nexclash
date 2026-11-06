#!/usr/bin/env python3
"""Probe: how often, and from which frame on, a recording reaches given addresses (C simulator).

    python tools/probes/rzx_census.py GAME.rzx --pc 0x6357,0x61D8 [--stop N] [--hl] [--json]

Invocation: the RZX (its own embedded snapshot is the start state) and a comma-separated list of
  instruction addresses. --hl adds, per address, a census of HL at that instruction (the classic
  "which object / which screen region" question), bucketed as screen / attributes / other.
Output: per address: count, first frame, last frame (+ HL buckets); --json prints one JSON object.
Speed: SkoolKit's C simulator through rzxplay's trace hook, ~400 frames/s with a hook (a 90K-frame
  recording in ~4 min) - the Python simulator commands (`scan`, `survey`) take ~1 h for the same.
Limits: instruction fetches only (no memory reads / writes: use `nexclash.py scan --writers`);
  --sample-frames 0,100 --memory 0x8000:0x8000 --json optionally captures registers and address-space
  bytes BEFORE the first hit per requested PC/frame; --sample-limit N retains up to N hits.
  Frames without a hit produce no sample. Sample order is execution order, not PC order.
  This is a point capture, not a write trace; banked memory is the currently mapped view.
  frames are rzxplay's frame counter (context.frame_count, from 0); a recording that desyncs stops with the frame reported;
  autosave snapshots inside the RZX are not stripped (strip first: nexclash.rzx strip).
Origin: Cauldron 2026-10-27 (first frame of each attribute hook, plot geometries, PEEK targets);
  Inferno 2026-11-05 added bounded point captures; dispositions in the games' "Lessons".
Smoke test: `python selftest.py --tools` runs it on Chuckie Egg (frames counted by the ROM
  interrupt entry 0x0038 must match the frames replayed); sampled PCs/frames and code bytes checked.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def census(rzx_path, pcs, stop=None, hl=False, sample_frames=(), memory=(), sample_limit=1):
    """-> {'frames': n, 'desync': None or message, 'pcs': {pc: {'count', 'first', 'last'[, 'hl']}}}"""
    import skoolkit.rzxplay as rp
    from types import SimpleNamespace
    from skoolkit import SkoolKitError
    from skoolkit.snapshot import Snapshot
    from nexclash.rzx import parse_rzx, InputRecording
    blocks = parse_rzx(rzx_path)
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    for b in blocks:
        if isinstance(b.obj, InputRecording):
            ctx.total_frames += len(b.obj.frames)
    if stop:
        ctx.total_frames = min(stop, ctx.total_frames)

    class Sink:
        def write(self, s):
            pass
    ctx.tracefile = Sink()
    want = frozenset(pcs)
    out = {pc: {'count': 0, 'first': None, 'last': None} for pc in pcs}
    hls = {pc: collections.Counter() for pc in pcs}
    sample_frames = frozenset(sample_frames)
    samples, sampled = [], collections.Counter()

    def hook(tf, context, fc, pc):
        if pc in want:
            o = out[pc]
            o['count'] += 1
            f = context.frame_count       # fc is rzxplay's fetch counter, not the frame
            if o['first'] is None:
                o['first'] = f
            o['last'] = f
            if f in sample_frames and sampled[pc, f] < sample_limit:
                sim = context.simulator
                samples.append({'pc': pc, 'frame': f, 'registers': list(sim.registers),
                                'memory': {str(lo): list(sim.memory[lo:lo + size])
                                           for lo, size in memory}})
                sampled[pc, f] += 1
            if hl:
                r = context.simulator.registers
                v = r[6] << 8 | r[7]
                hls[pc]['screen' if 0x4000 <= v < 0x5800 else 'attributes' if 0x5800 <= v < 0x5B00 else 'other'] += 1
    old = rp.trace_exec
    rp.trace_exec = hook
    err = None
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop or 0, force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            if ctx.stop:
                break
    except SkoolKitError as e:
        err = str(e)
    finally:
        rp.trace_exec = old
    if hl:
        for pc in pcs:
            out[pc]['hl'] = dict(hls[pc])
    result = {'frames': ctx.frame_count, 'desync': err, 'pcs': out}
    if sample_frames:
        result['samples'] = samples
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog='rzx_census.py', description=__doc__.split('\n')[0])
    ap.add_argument('rzx')
    ap.add_argument('--pc', required=True, help='comma-separated addresses (0x.. or decimal)')
    ap.add_argument('--stop', type=int, help='stop after N frames')
    ap.add_argument('--hl', action='store_true', help='HL buckets per address')
    ap.add_argument('--sample-frames', default='', help='zero-based frames: first hit per PC captures registers')
    ap.add_argument('--memory', action='append', default=[], help='capture ADDR:SIZE at sampled hits (repeatable; JSON only)')
    ap.add_argument('--sample-limit', type=int, default=1, help='maximum hits captured per PC/frame (default 1)')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    pcs = [int(x, 0) for x in a.pc.split(',') if x]
    frames = [int(x, 0) for x in a.sample_frames.split(',') if x]
    memory = [tuple(int(x, 0) for x in span.split(':')) for span in a.memory]
    if any(len(span) != 2 or not 0 <= span[0] < 65536 or not 0 < span[1] <= 65536 - span[0]
           for span in memory):
        ap.error('--memory requires ADDR:SIZE within the 64K address space')
    if (frames or memory) and not a.json:
        ap.error('sample capture requires --json')
    if memory and not frames:
        ap.error('--memory requires --sample-frames')
    if a.sample_limit < 1:
        ap.error('--sample-limit must be positive')
    r = census(a.rzx, pcs, a.stop, a.hl, frames, memory, a.sample_limit)
    if a.json:
        r['pcs'] = {'0x%04X' % k: v for k, v in r['pcs'].items()}
        print(json.dumps(r))
        return 0
    print('frames %d%s' % (r['frames'], '' if not r['desync'] else '  DESYNC: %s' % r['desync']))
    for pc, o in r['pcs'].items():
        print('0x%04X  count %8d  first %s  last %s%s' % (pc, o['count'], o['first'], o['last'],
                                                         '  HL %s' % o['hl'] if 'hl' in o else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
