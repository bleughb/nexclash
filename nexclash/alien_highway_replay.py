"""Replay the original IN stream on OverSpec's Next core and check both sides of each video boundary."""
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from zipfile import ZipFile
from types import SimpleNamespace
from unittest.mock import patch as replace

from skoolkit import rzxplay
from skoolkit.traceutils import disassemble

from nexclash import alien_highway as ah, rzx, z80tonex as zt

FRAME = struct.Struct('<II12H4BI')


def export_recording(recording, reference, folder, limit):
    segments = rzx.read_segments(str(recording))
    if len(segments) != 1:
        raise ValueError('Expected a single continuous Alien Highway recording')
    _, data, _ = segments[0]
    total = min(limit or len(data.frames), len(data.frames))
    ctx = rzxplay.RZXContext(None)
    ctx.total_frames = total
    original_read = rzxplay.RZXTracer.read_port
    with (folder/'reads').open('wb') as inputs, (folder/'frames').open('wb') as frames:
        def read(tracer, registers, port):
            value = original_read(tracer, registers, port)
            inputs.write(struct.pack('<HB', port, value))
            return value

        def draw(screen, index, border):
            r = ctx.simulator.registers
            if r[26]:
                raise ValueError('An interrupt-enabled recording needs interrupt replay')
            ram = bytearray(ctx.simulator.memory[0x4000:])
            for address, old, _ in reference.sites:
                offset = address - 0x4000
                ram[offset:offset + len(old)] = bytes(len(old))
            offset = reference.tail_addr - 0x4000
            ram[offset:offset + reference.tail_size] = bytes(reference.tail_size)
            words = [r[i]*256 + r[i+1] for i in (0, 2, 4, 6, 8, 10, 16, 18, 20, 22)]
            state = (inputs.tell()//3, r[24], r[12], *words, r[14], r[15], r[26], r[27], zlib.crc32(ram))
            frames.write(FRAME.pack(data.frames[index].fetch_counter, *state))
            # SkoolKit skips the trailing zero-fetch record. Test the unchanged display at that boundary too.
            if index+2 == total and not data.frames[index+1].fetch_counter:
                frames.write(FRAME.pack(0, *state))
            return True

        ctx.screen = SimpleNamespace(draw=draw)
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=total, force=False)
        with replace.object(rzxplay.RZXTracer, 'read_port', read):
            for block in rzxplay.parse_rzx(str(recording)):
                rzxplay.process_block(block.obj, opts, 0, ctx)
        if frames.tell() != total*FRAME.size or ctx.frame_count != total:
            raise ValueError('Missing RZX frame checkpoints')
    return total


def compile_probe(folder, renderer, snapshot, archive):
    # Pin executable test input before extracting or compiling it, including in standalone runs.
    if hashlib.sha256(archive.read_bytes()).hexdigest() != 'f50f04f0323e9c7e9be49bf4dce530438bcd90179c9be4a1f862c1917dc18f51':
        raise ValueError('Unexpected OverSpec classic source archive')
    classic = folder/'classic'
    with ZipFile(archive) as bundle:
        bundle.extractall(classic)
    source = (classic/'nx.c').read_text()
    # The three observers do not modify the core. Only the game receives recorded port data.
    for original, observed in (
        ('static uint8_t zm_in(uint16_t p) {',
         'static uint8_t read_game(uint16_t,uint8_t);\nstatic uint8_t zm_in(uint16_t p) {'),
        ('return traceRead(0, v);', 'return read_game(p,traceRead(0,v));'),
        ('static void zm_out(uint16_t p, uint8_t v) {',
         'static void game_out(uint16_t,uint8_t);\nstatic void zm_out(uint16_t p,uint8_t v) { game_out(p,v);'),
        ('#include "z80.inc"', 'static uint8_t game_read(uint16_t,uint8_t);\n#include "observed_z80.inc"'),
        ('static void instructionRuns(int d) {',
         'static void pre_step(void);\nstatic void instructionRuns(int d) { pre_step();'),
        ('static void compose(int y320) {',
         'static void compare_beam(int,int,int);\nstatic void compose(int y320) {'),
        ('  composeLayers(vc, y320);', '  composeLayers(vc, y320); compare_beam(y320,composeLeft,composeRight);'),
    ):
        if source.count(original) != 1:
            raise ValueError('OverSpec observer point changed: '+original)
        source = source.replace(original, observed)
    cpu = (classic/'z80.inc').read_text()
    old = 'Z80_CPU_SEES(x, 1); return zm_read(x);'
    if cpu.count(old) != 1:
        raise ValueError('OverSpec data-read observer point changed')
    (folder/'observed_z80.inc').write_text(cpu.replace(old, 'Z80_CPU_SEES(x, 1); return game_read(x,zm_read(x));'))
    (folder/'observed.c').write_text(source)
    memory = bytearray(16384) + snapshot.banks[5] + snapshot.banks[2] + snapshot.banks[0]
    sites = []
    for address, old, _ in renderer.sites:
        pc = address
        fetches = 0
        while pc < address + len(old):
            fetches += 1 + (memory[pc] in (0xCB, 0xDD, 0xED, 0xFD))
            pc += disassemble(memory, pc)[1]
        if pc != address + len(old):
            raise ValueError('Partial instruction at guarded site')
        sites.append(f'{{{address},{len(old)},{fetches}}},')
    (folder/'exclude.inc').write_text(f'#define TAIL_OFFSET {renderer.tail_addr - 0x4000}\n#define TAIL_LENGTH {renderer.tail_size}\n')
    (folder/'sites.inc').write_text('\n'.join(sites))
    shutil.copyfile(Path(__file__).with_suffix('.c'), folder/'probe.c')
    subprocess.run(['cc', '-O2', '-ffp-contract=off', '-iquote', str(classic.resolve()),
                    'probe.c', '-o', 'probe', '-lm', '-lz', '-lcrypto'], cwd=folder, check=True)


def run(source, program, recording, limit=None):
    with tempfile.TemporaryDirectory(prefix='alien_replay_') as temp:
        folder = Path(temp)
        original = folder/'original.nex'
        renderer = ah.Patch()
        _, (_, _, tail, _) = ah.build_plain(source, original)
        renderer.tail_size = len(tail)
        original.write_bytes(zt.automap_off(original.read_bytes()))
        compile_probe(folder, renderer, zt.Z80Snapshot(str(source)), Path(recording).with_name('overspec-classic.zip'))
        total = export_recording(recording, renderer, folder, limit)
        # Keep all game state and boot code identical. Disable just the copy-entry hook for the negative.
        late = folder/'late.nex'
        hide = int(ah.load_profile()['hooks']['syms']['copy_hide'], 16) - 0x2000
        if bytes(renderer.page[hide:hide+4]) != bytes.fromhex('ed911500'):
            raise ValueError('Expected the copy-entry sprite disable')
        renderer.page[hide:hide+4] = bytes(4)
        zt.convert(str(source), str(late), patch=renderer, quiet=True)
        late.write_bytes(zt.automap_off(late.read_bytes()))
        results = {}
        for name, nex, mode in [('original', original, 2), ('fixed', program, 0), ('late', late, 1)]:
            cmd = [str(folder/'probe'), str(nex), 'reads', 'frames', str(mode), 'paired']
            job = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=1800)
            print(name, job.stdout, job.stderr, flush=True)
            if job.returncode:
                raise ValueError(f'{name} replay failed with exit {job.returncode}')
            results[name] = dict(token.split('=') for line in job.stdout.splitlines()[-3:] for token in line.split())
            if int(results[name]['recorded']) != total:
                raise ValueError(f'{name} replay did not reach every recorded frame')
        plain_ticks = int(results['original']['elapsed_ticks'])
        delta = 100*(int(results['fixed']['elapsed_ticks'])/plain_ticks-1)
        print(f'Elapsed time change {delta:+.3f}%', flush=True)
        if abs(delta) > 2:
            raise ValueError(f'Whole-run elapsed time changed by {delta:+.3f}%')
        return results


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(),
        int(sys.argv[4]) if len(sys.argv)>4 else None)
