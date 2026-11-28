"""Compare the live multiload NEX with Ocean's loader running against the tape signal."""
import contextlib
import io
import multiprocessing
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from skoolkit import CSimulator
from skoolkit.loadtracer import LoadTracer
from skoolkit.simutils import from_snapshot
from skoolkit.snapshot import Snapshot
from skoolkit.tape import parse_tap

from . import nextboot, rzx, simpsons, z80n, z80tonex
from . import simpsons_single as single

# Each PC is the game's carry-clear instruction immediately before JP $8190.
# A restart uses the same loader with carry set.
ROUTE = ((2, 0xAC2E), (3, 0xBF93), (4, 0x7D77), (5, 0x8654), (1, 0x8190))
PLAYER = {0x5B03: 0x01, 0x5B04: 0x23, 0x5B05: 0x45, 0x5B09: 7}


def require(test, reason):
    if not test:
        raise ValueError(reason)


def tape_states(start, tape):
    """One 128K machine through the entire route. No snapshot swaps or ROM load traps."""
    sim = from_snapshot(CSimulator, Snapshot.get(str(start)))
    for address, value in PLAYER.items():
        sim.memory[address] = value
    states = {}
    for level, site in ROUTE:
        regs = sim.registers
        regs[24], regs[25], regs[26] = site, 0, 0
        if level == 1:
            regs[1] |= 1
        first = 9 + (level - 1) * 12
        blocks = parse_tap(tape, start=first, stop=first + 12).blocks
        for block in blocks:
            block.keys = None
        config = dict(accelerate_dec_a=0, accelerators=[], byte_fmt='02X', fast_load=False,
                      finish_tape=False, first_edge=0, in_min_addr=0x8000, list_accelerators=False,
                      pause=True, polarity=0, prefix='$', stop=0x8520, timeout=3_500_000_000,
                      tracefile=None, trace_line='', word_fmt='04X')
        tracer = LoadTracer(sim, blocks, config, None)
        sim.set_tracer(tracer, False, False)
        with contextlib.redirect_stdout(io.StringIO()):
            tracer.run(0, sim.memory.o7ffd, 0, [0] * 16, 0)
        require(regs[24] == 0x8520 and sim.memory.o7ffd == 0x10, f'original failed to load level {level}')
        states[level] = (list(regs), b''.join(sim.memory.banks))
    return states


class Machine:
    def __init__(self, nex, start):
        self.state = state = nextboot.boot(str(nex), Snapshot.get(str(start)).pc, nexload=True)
        self.mem = state['mem']
        self.sim = simpsons._rw()(self.mem, {})
        self.regs = self.sim.registers
        self.regs[:] = state['R'][:]
        self.palette = []
        self.sim.set_tracer(nextboot.NextPorts(state, self.nextreg))
        z80n.install(self.sim, self.nextreg)

    def nextreg(self, reg, value):
        self.state['nr'][reg] = value
        if 0x50 <= reg <= 0x57:
            self.state['mmu'][reg - 0x50] = value
        elif reg == 0x44:
            self.palette.append(value)

    def page(self, page):
        mmu = self.state['mmu']
        saved = mmu[6]
        try:
            mmu[6] = page
            return bytes(self.mem[a] for a in range(0xC000, 0xE000))
        finally:
            mmu[6] = saved

    def load(self, level, site, files):
        self.regs[24], self.regs[26] = site, 0
        if level == 1:
            self.regs[1] |= 1
        calls = 0
        for _ in range(500000):
            pc = self.regs[24]
            if pc == 0x8520:
                require(calls == 12, f'level {level}: {calls} block returns')
                return
            require(pc != 0x0562, 'load still enters tape ROM at $0562')
            if pc in (0x82AD, 0x82CE):  # immediately after each LD-BYTES call
                require(calls < 12, 'extra block read')
                header, payload = files[calls // 2]
                is_header = calls % 2 == 0
                require((pc == 0x82AD) == is_header, 'wrong block type')
                addr = 0x82E3 if is_header else int.from_bytes(header[13:15], 'little')
                expected = header if is_header else payload
                got = bytes(self.mem[a] for a in range(addr, addr + len(expected)))
                require(got == expected, f'wrong block bytes: level {level} read {calls + 1}')
                calls += 1
            self.sim.opcodes[self.mem[pc]]()
        raise ValueError(f'level {level} did not start, PC={self.regs[24]:04X}')


def installed(machine, pt):
    """Give the existing verifier the code, sprites, tables and ROM actually installed."""
    for addr, _, new in pt.sites:
        require(bytes(machine.mem[addr+i] for i in range(3)) == new, f'wrong hook site at {addr:04X}')
    rom0, rom1 = machine.state['alt']
    end = 0x2000 + len(pt.rom_code)
    require(rom0[0x2000:end] == rom1[0x2000:end] == pt.rom_code, 'wrong level hook code')
    pt.page = bytes(rom0[0x2000:])
    pt.altrom0 = (0x2000, 0x4000)
    pt.work = machine.page(simpsons.WORK)
    require(pt.work == simpsons.work_page(), 'stale sprite state')
    actual = {pg: machine.page(pg) for pg in pt.planes}
    require(actual == pt.planes, 'wrong painted strips or index')
    pt.planes = actual
    writes = machine.palette or [v for reg, v in machine.state['nrlog'] if reg == 0x44]
    require(bytes(writes[-512:]) == bytes(v for c in pt.palette for v in (c >> 1, c & 1)), 'wrong palette')
    return pt


def compare(machine, oracle, level, pt, base, pokes, tail, initial):
    regs, expected = oracle[level]
    require(all(v == regs[i] for i, v in enumerate(machine.regs) if i != 25),
            f'level {level}: registers differ at $8520')
    require(machine.state['mmu'] == [255, 255, 10, 11, 4, 5, 0, 1]
            and machine.state['p7ffd'] == 16, 'wrong mapping on return to game')
    want = bytearray(expected)
    for addr, _, new in base.sites[4:] + pt.sites:
        offset = 2 * 16384 + addr - 0x8000
        want[offset:offset+len(new)] = new
    for addr in pokes:
        want[3 * 16384 + addr - 0xC000] = 0
    got = b''.join(machine.page(pg) for pg in range(16))
    for addr, value in PLAYER.items():
        require(machine.mem[addr] == value, 'score or lives changed during load')
    # The original never loaded the NEX start-up tail. Check that those bytes
    # are exactly the ones boot left, independently of the load being tested.
    off, length = tail
    require(got[off:off+length] == initial[off:off+length], 'boot tail overwritten')
    want[off:off+length] = initial[off:off+length]
    # Below the discarded loader stack, the ROM EAR sampling calls leave two
    # return words. The bank copy and install leave their own three words.
    for addr in (0x8172, 0x8174, 0x817E):
        off = 2 * 16384 + addr - 0x8000
        want[off:off+2] = got[off:off+2]
    differences = [i for i, v in enumerate(want) if v != got[i]]
    require(not differences, f'level {level}: unexpected RAM differences {differences[:12]}')


def transitions(nex, start, tape, oracle, snapshots, painted, trainer=False):
    machine = Machine(nex, start)
    cmap = simpsons.load_colours(start)
    base = single.make_patch(start, tape, painted)
    snap = z80tonex.Z80Snapshot(str(start))
    length = len(z80tonex.build_tail(snap, 0x8000, base.slot1, True)[0])
    tail_addr = z80tonex.choose_tail_addr(snap, length, None, False)[0]
    tail = 2 * 16384 + tail_addr - 0x8000, length
    initial = b''.join(machine.page(pg) for pg in range(16))
    colours = cmap if painted else None
    result = {1: installed(machine, simpsons.Patch(z80=start, colours=colours))}
    pokes = set(single.LIVES[0]) if trainer else set()
    for address, value in PLAYER.items():
        machine.mem[address] = value
    files = single.levels(tape)
    for level, site in ROUTE:
        if level == 4:
            # Observed after playing the circus in OverSpec. The next load
            # needs its LD HL,$824E opcode again to request the fourth block.
            machine.mem[0x8208] = 0x82
        machine.load(level, site, files[level - 1])
        if level in snapshots or level == 1:
            pt = simpsons.Patch(z80=snapshots.get(level, start), colours=colours)
        else:
            pt = simpsons.Patch(mem=single.play_memory(files[level - 1]), colours=colours)
        installed(machine, pt)
        if trainer:
            # Only the bytes covered by this load of bank 3 lose a previous POKE.
            limit = 0xC000 + len(files[level - 1][3][1])
            pokes = {addr for addr in pokes if addr >= limit} | set(single.LIVES[level - 1])
        compare(machine, oracle, level, pt, base, pokes, tail, initial)
        result.setdefault(level, pt)
    return result


def negatives(nex, start, tape):
    files = single.levels(tape)[1]
    for flaw, reason in [('bank', 'wrong block bytes'), ('tape', 'load still enters tape ROM')]:
        machine = Machine(nex, start)
        if flaw == 'bank':
            # Corrupt the first data span for simp-21 in the ROM actually used.
            sy = simpsons.load_profile()['hooks']['syms']
            address = int(sy['multi_blocks'], 16) + 6 * 32 + 17
            machine.state['alt'][1][address] += 1
        else:
            for i, value in enumerate(bytes.fromhex('C36205')):
                machine.mem[single.LOAD_SITE+i] = value
        try:
            machine.load(2, ROUTE[0][1], files)
        except ValueError as exc:
            if reason in str(exc):
                continue
            raise
        raise ValueError(f'negative {flaw} escaped detection')


def replay(args):
    path, quick, plain, painted = args
    lines = []
    ok = simpsons.verify_builds(SimpleNamespace(rzx=[str(path)], quick=quick), plain, painted, lines.append)
    return ok, lines


def verify(start, tape, out, recordings, quick, say):
    raw = tape.read_bytes()
    states = tape_states(start, raw)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        snapshots, paths = {}, []
        for i, path in enumerate(recordings):
            snapshot, _ = rzx.extract(path, Path(tmp) / f'{i}.z80')
            level = simpsons.Patch(z80=snapshot).level
            snapshots[level] = snapshot
            paths.append((level, path, snapshot))
        builds = [transitions(out / f'simpsons_{label}.nex', start, raw, states, snapshots, painted)
                  for label, painted in [('sprites', False), ('enhanced', True)]]
        negatives(out / 'simpsons_sprites.nex', start, raw)
        say('Loads     : 10/10 level entries, 120/120 block returns, 128K and registers compared; '
            'both wrong-bank and tape-call controls detected')
        jobs = []
        for level, path, snapshot in paths:
            pair = [build[level] for build in builds]
            for pt in pair:
                pt.z80 = snapshot
            jobs.append((path, quick, *pair))
        with ProcessPoolExecutor(max_workers=min(5, len(jobs)), mp_context=multiprocessing.get_context('spawn')) as pool:
            for ok, lines in pool.map(replay, jobs):
                for line in lines:
                    say(line)
                require(ok, 'per-level replay failed')
