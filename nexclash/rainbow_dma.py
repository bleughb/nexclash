"""Experimental Rainbow Islands sky game build, v0.1 (pinned releases unchanged).

python -m nexclash.rainbow_dma build --snapshot ../specnext/reference/rainbow_islands/rainbow.z80 --out DIR
python -m nexclash.rainbow_dma build --snapshot SNAP --out DIR --no-blitter
python -m nexclash.rainbow_dma verify --rzx RECORDING --frames 2000 --report report.json

--dma-mbps supplies an assumed transfer rate for elapsed-stall sensitivity, NOT a measurement.
"""
import argparse
import collections
import statistics
import hashlib
import json
import math
import tempfile
from pathlib import Path

from . import rainbow_z80n_sky as game
from .dma import DMA, DMAError

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.1'
ORG = 0x5000
OLD_LOOP = bytes.fromhex('3e14014000edb0eb01100009eb3d20f2')


def profile():
    return json.loads((ROOT / 'docs/profiles/rainbow_dma.json').read_text())['hooks']


class RainbowDMA(game.RainbowPatch):
    """Use the existing sky/colour/cache engine; splice only tcommit's row-copy loop."""
    def __init__(self, policy=2, core=0x33, hwim2=0, mbps=4.0, diag=False):
        cls = game.load_profile().get("colours", {}).get("class_colours")
        super().__init__(game.Config(class_colours=cls, diag=diag), colours=game.load_colours(), sky=True)
        self.policy, self.core, self.hwim2, self.mbps = policy, core, hwim2, mbps
        self.dma_syms = {k: int(v, 16) for k, v in profile()['syms'].items()}
        h = profile()
        self.extension = bytearray.fromhex(h['extension'])
        self.extension[self.dma_syms['hlib_dma_policy'] - ORG] = policy
        # Fail closed if the pinned engine changes: exact loop, mapping and sample target.
        start = self.syms['tcommit'] - game.ROM_ORG
        at = self.rom_code.index(OLD_LOOP, start)
        assert self.rom_code[start:at].endswith(bytes.fromhex('ed91521ced91530e21004011e861'))
        rsafe = self.syms['rsafe'] - game.ROM_ORG
        assert self.rom_code[rsafe] == 0xCD
        assert int.from_bytes(self.rom_code[rsafe+1:rsafe+3], 'little') == self.dma_syms['LSAMP']
        self.loop_at = at
        self.commit_margin = 64  # conservative map budget, about 4.1 ms at 28 MHz
        rom = bytearray(self.rom_code)
        rom[at:at+len(OLD_LOOP)] = b'\xCD\x00\x50' + bytes(len(OLD_LOOP)-3)
        budget = rom.index(bytes.fromhex("214300"), rsafe)
        rom[budget+1:budget+3] = (327-self.commit_margin-game.RS_LINE).to_bytes(2, "little")
        self.rom_code = bytes(rom)
        pg = bytearray(self.page)
        pg[game.ROM_ORG-0x2000:game.ROM_ORG-0x2000+len(rom)] = rom
        self.page = bytes(pg)
        self.extra_banks[12] = self.page + self.fpage
        # Page 28 has no snapshot data; upper half was unused. Canvas page 29 stays zero.
        shadow = bytearray(16384)
        shadow[0x1000:0x1000+len(self.extension)] = self.extension
        self.extra_banks[14] = bytes(shadow)
        # Loader has returned and the original Spectrum game never owns DMA. Revoke any
        # inherited burst channel before the game starts; setup then sets its own registers.
        # Do not move setup or palette bytes: its assembled LD HL,pal operands and
        # exported symbols are absolute. Enter via a trampoline AFTER the palettes.
        setup_entry = self.setup_call
        self.setup_call = 0xD000 + len(self.stub_extra)
        self.stub_extra += bytes.fromhex('3e83d36bc3') + setup_entry.to_bytes(2, 'little')
        assert self.setup_call + 7 < 0xDFFE
        self.report = {}

    def prepare_unit_pages(self, pages):
        # Legacy object fixtures randomize the entire shadow page. Its upper half is
        # now an owned code allocation, so seed it exactly as the NEX loader does.
        if game.PAGE_SH in pages:
            pages[game.PAGE_SH][0x1000:0x1000+len(self.extension)] = self.extension

    def configure_nextstate(self, ns):
        ns.pages[game.PAGE_SH][0x1000:0x1000+len(self.extension)] = self.extension
        ns.nr.update({1: self.core, 0xC0: self.hwim2})
        ns.dma_mem = None
        ns.dma_ticks = 0
        ns.dma_jobs = []
        ns.hook_times = collections.defaultdict(list)
        ns.base_out = ns.out

        def elapsed(count):
            ticks = math.ceil(count * 28 / self.mbps) if self.mbps else 0
            ns.R[25] += ticks
            ns.dma_ticks += ticks

        def read(a):
            # This implementation uses virtual MMU addresses in ordinary RAM only.
            if ns.nr.get(0x52) != game.PAGE_SH or ns.nr.get(0x53) != game.PAGE_TM:
                raise DMAError('Rainbow DMA mappings differ from the entry contract')
            if not 0x4000 <= a < 0x4500:
                raise DMAError('Rainbow DMA source outside shadow rectangle')
            return ns.dma_mem[a]

        def write(a, value):
            if not 0x61E8 <= a < 0x6818:
                raise DMAError('Rainbow DMA destination outside tilemap')
            ns.dma_mem[a] = value

        ns.dma = DMA(read, write, lambda p, v: (_ for _ in ()).throw(DMAError('unexpected DMA I/O')),
                     blitter=0x33 <= self.core < 0xFF, stall=elapsed)

        def out(port, value):
            if port & 255 in (0x0B, 0x6B):
                if port & 255 == 0x0B:
                    raise DMAError('legacy DMA port is not allowed')
                if ns.nr.get(0xC0, 0) & 1 and value != 0x83:
                    raise DMAError('DMA programmed with hardware IM2 enabled')
                before = ns.dma.stats['jobs']
                ns.dma.feed(value)
                if ns.dma.stats['jobs'] != before:
                    ns.dma_jobs.append((ns.dma.flags, ns.dma.length, ns.dma.width, ns.dma.rows,
                                        ns.dma.astride, ns.dma.bstride))
            else:
                ns.base_out(port, value)

        def attach(sim):
            ns.dma_mem = sim.memory     # Rainbow PMem: actual per-hook mapped/overlay memory
            ns.decision_line = None
            entry, start, stalls = ns.R[24], ns.R[25], ns.dma_ticks
            def completed():
                ns.hook_times[entry].append((ns.R[25]-start, ns.dma_ticks-stalls))
            sim.rainbow_hook_completed = completed
            original_load = sim.opcodes[0x3A]
            def load_absolute():
                if ns.R[24] == self.syms['tcommit']:
                    ns.decision_line = ns.last_line  # rsafe decision, before our extra samples
                original_load()
            sim.opcodes[0x3A] = load_absolute
        ns.out, ns.attach_machine = out, attach

    def finish_verify(self, ns, counters, frames):
        for k, v in ns.dma.stats.items():
            counters['DMA ' + k] = v
        counters['DMA assumed stall T'] = ns.dma_ticks
        self.report = {'version': VERSION, 'policy': self.policy, 'core': self.core,
                       'hardware_im2': self.hwim2, 'assumed_dma_MBps': self.mbps,
                       'timing_scope': 'simulator CPU T plus injected transfer stalls; no contention or hardware measurement',
                       'counters': dict(counters), 'frame_profile_columns':
                       ['recording_frame', 'elapsed_T', 'original_T', 'pieces_extra_T', 'render_start_extra_T',
                        'band_extra_T', 'cell_extra_T', 'render_end_extra_T', 'render_end_start_T'],
                       'frame_profile': frames,
                       'complete_hooks': {str(pc): {'calls': len(values),
                           'elapsed_T_median': statistics.median(v[0] for v in values),
                           'elapsed_T_mean': sum(v[0] for v in values)/len(values),
                           'elapsed_T_p95': sorted(v[0] for v in values)[int((len(values)-1)*.95)],
                           'elapsed_T_max': max(v[0] for v in values),
                           'assumed_stall_T_total': sum(v[1] for v in values)}
                           for pc, values in ns.hook_times.items()}}


def verify(patch, recording, frames=None):
    from . import rzx
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    original = Path(recording)
    snapshots = sum(isinstance(b.obj, Snapshot) for b in parse_rzx(str(original)))
    expected_frames = sum(len(segment[1].frames) for segment in rzx.read_segments(str(original)))
    # As the sky engine's auto command does: keep one initial state, not Fuse autosave resets.
    with tempfile.TemporaryDirectory(prefix='rainbow-dma-replay-') as temp:
        replay = original
        if snapshots > 1:
            replay = Path(temp) / original.name
            rzx.strip(str(original), str(replay))
        counters, errors = game.verify(patch, str(replay), stop=frames,
                                       progress=lambda n, c: print('Replay frame', n, flush=True))
    failures = {k: v for k, v in counters.items() if k.endswith('!')}
    if counters['frames'] < min(frames or expected_frames, expected_frames):
        failures['recording ended before requested coverage!'] = 1
    if patch.policy and not patch.hwim2 and 0x30 <= patch.core < 0xFF and counters['commits checked']:
        if not counters['DMA jobs']:
            failures['DMA path never executed!'] = 1
    patch.report.update(recording=Path(recording).name,
                        recording_md5=hashlib.md5(Path(recording).read_bytes()).hexdigest(),
                        coverage='partial' if frames else 'complete supplied recording',
                        autosave_snapshots_removed=max(0, snapshots-1), recording_input_frames=expected_frames,
                        failures=failures, errors=errors)
    print('Verify:', Path(recording).name, counters['frames'], 'frames,', counters['commits checked'],
          'commits,', counters['DMA jobs'], 'DMA jobs;', 'FAIL' if failures else 'PASS', flush=True)
    return failures


def build(snapshot, out, policy=2, diag=False):
    from . import z80tonex as zt
    snapshot, out = Path(snapshot), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    label = ('cpu_only', 'no_blitter', 'blitter')[policy]
    path = out / ('rainbow_sky_dma_v01_' + label + ('_diag' if diag else '') + '.nex')
    patch = RainbowDMA(policy, diag=diag)
    previous_fill = zt.ALTROM_FILL
    try:
        zt.ALTROM_FILL = "rom3"       # reproduce the sky record's pinned loader contract
        zt.convert(str(snapshot), str(path), quiet=True, patch=patch)
        faults = game.boot_check(str(path), str(snapshot), patch)
    finally:
        zt.ALTROM_FILL = previous_fill
    if faults:
        raise RuntimeError('game boot check: ' + repr(faults))
    screen = snapshot.with_name(game.LOAD_SCREEN)
    if not screen.is_file():
        raise FileNotFoundError('sky loading screen required: ' + str(screen))
    data, faults = game.loading_nex(path.read_bytes(), screen.read_bytes())
    if faults:
        raise RuntimeError('loading screen: ' + repr(faults))
    # Exercise the delivered loading-screen wrapper too, through to the game PC.
    from . import nextboot
    stop_pc = zt.Z80Snapshot(str(snapshot)).pc
    before = nextboot.boot(str(path), stop_pc)
    path.write_bytes(data)
    after = nextboot.boot(str(path), stop_pc)
    expected_palette = patch.cfg.palette() + patch.cfg.tile_palette()
    if bytes(value for reg, value in after['nrlog'] if reg == 0x41) != expected_palette:
        raise RuntimeError('startup palette upload differs from the sky game')
    if after['bad'] or any(before['R'][i] != after['R'][i] for i in range(29) if i != 25) or \
            any(before['mem'][a] != after['mem'][a] for a in range(65536)) or after['nr'].get(0xC0) != 0:
        raise RuntimeError('loading-screen wrapper changed the game entry state')
    result = {'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
              'md5': hashlib.md5(data).hexdigest(), 'bytes': len(data), 'policy': label,
              'experimental_version': VERSION, 'sky': True, 'boot_check': 'PASS, including loading-screen wrapper and pulse-mode entry'}
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('build', 'verify', 'check'):
        p = sub.add_parser(name)
        policy = p.add_mutually_exclusive_group()
        policy.add_argument('--no-blitter', action='store_true', help='real game: ordinary DMA with CPU fallback')
        policy.add_argument('--cpu-only', action='store_true', help='real game: original LDIR rectangle')
        if name == 'build':
            p.add_argument('--snapshot', required=True)
            p.add_argument('--out', required=True)
            p.add_argument('--diagnostic', action='store_true')
        elif name == 'verify':
            p.add_argument('--rzx', required=True)
            p.add_argument('--frames', type=int)
            p.add_argument('--report', required=True)
            p.add_argument('--core', type=lambda s: int(s, 0), default=0x33)
            p.add_argument('--hardware-im2', action='store_true')
            p.add_argument('--dma-mbps', type=float, default=4.0)
    args = parser.parse_args()
    policy = 0 if args.cpu_only else 1 if args.no_blitter else 2
    if args.command == 'build':
        build(args.snapshot, args.out, policy, args.diagnostic)
    elif args.command == 'verify':
        if args.dma_mbps <= 0:
            parser.error('--dma-mbps must be positive')
        patch = RainbowDMA(policy, args.core, int(args.hardware_im2), args.dma_mbps)
        failures = verify(patch, args.rzx, args.frames)
        Path(args.report).write_text(json.dumps(patch.report, indent=2) + '\n')
        raise SystemExit(bool(failures))
    else:
        from .rainbow_dma_check import selfcheck
        selfcheck()


if __name__ == '__main__':
    main()
