"""Data-free differential checks of assembled DMA hooks and the strict functional model."""
import collections
import random
import unittest

from . import hooklib as h
from .dma import DMA, DMAError


def setup(sim, nm, syms, core=0x33, owned=1, hwim2=0):
    nm.nr[1], nm.nr[0xC0] = core, hwim2
    nm.dma.blitter = 0x33 <= core < 0xFF
    h.call(sim, syms['hlib_dma_init'], {h.A: owned})


def rectangle(code, syms, core=0x33, owned=1, hwim2=0, policy=None):
    sim, nm = h._machine(code)
    setup(sim, nm, syms, core, owned, hwim2)
    if policy is not None:
        sim.memory[syms['hlib_dma_policy']] = policy
    rnd = random.Random(64)
    source = bytes(rnd.randrange(256) for _ in range(1280))
    sim.memory[0x4000:0x4500] = source
    sim.memory[0x6000:0x6900] = [0xA5] * 2304
    want = bytearray([0xA5] * 2304)
    for row in range(20):
        want[488 + row * 80:488 + row * 80 + 64] = source[row * 64:(row + 1) * 64]
    t0 = sim.registers[h.T]
    h.call(sim, syms['hlib_dma_rect'], {h.H: 0x40, h.L: 0, h.D: 0x61, h.E: 0xE8})
    assert bytes(sim.memory[0x6000:0x6900]) == want, 'rectangle differs (including untouched gaps)'
    assert bytes(sim.memory[0x4000:0x4500]) == source, 'source overwritten'
    return nm.dma.stats, sim.registers[h.T] - t0


def check_policy(define=None, verbose=False):
    code, syms = h.assemble(defines=(define,) if define else ())
    expected_policy = {None: 2, 'HLIB_NO_BLITTER': 1, 'HLIB_CPU_ONLY': 0}[define]
    assert code[syms['hlib_dma_policy'] - 0x8000] == expected_policy
    results = []
    for core, owned, hwim2 in ((0x33, 1, 0), (0x32, 1, 0), (0x33, 0, 0),
                               (0x33, 1, 1), (0xFF, 1, 0), (0x2F, 1, 0)):
        stats, ticks = rectangle(code, syms, core, owned, hwim2)
        capable = owned and not hwim2 and 0x30 <= core < 0xFF
        backend = min(expected_policy, 2 if core >= 0x33 else 1) if capable else 0
        jobs = (0, 20, 1)[backend]
        assert stats['jobs'] == jobs, (core, owned, hwim2, stats)
        assert stats['writes'] == (1280 if jobs else 0)
        results.append((core, owned, hwim2, backend, ticks, stats['program bytes']))
    # Runtime override also prevents DDMA on a supporting core.
    stats, _ = rectangle(code, syms, policy=0)
    assert stats['program bytes'] == 0
    if expected_policy:
        stats, _ = rectangle(code, syms, policy=1)
        assert stats['jobs'] == 20
    for core in (0x32, 0x33):
        def init(sim, nm, sy):
            setup(sim, nm, sy, core)
        for test in (h._t_cache, h._t_commit):
            counters = test(code, syms, setup=init)
            assert not [k for k in counters if k.endswith('!')], counters
    if verbose:
        print('Policy: %s; assembled hooks, synthetic data; CPU T excludes DMA stall (not elapsed timing)' %
              ('blitter preferred', 'ordinary DMA only', 'CPU only')[(2, 1, 0).index(expected_policy)])
        for core, owned, hwim2, backend, ticks, program in results:
            print('core=%02X owned=%d hwim2=%d backend=%s CPU-T=%d program-bytes=%d' %
                  (core, owned, hwim2, ('cpu', 'dma', 'blitter')[backend], ticks, program))
        print('PASS: rectangle bytes/gaps, old-core and unsafe-context fallback, cache, atomic commits')
    return results


def word(cmd, value):
    return [cmd, value & 255, value >> 8]


def program(src, dst, width, rows, astride, bstride, flags=2):
    return ([0x83, 0xC3, 0x7D, src & 255, src >> 8, 0, 0, 0x14, 0x10, 0xAD,
             dst & 255, dst >> 8, 0x82, 0xDF, flags] + word(0xE3, width) + word(0xE7, rows) +
            word(0xEB, astride) + word(0xEF, bstride))


class Checks(unittest.TestCase):
    def test_policies(self):
        for define in (None, 'HLIB_NO_BLITTER', 'HLIB_CPU_ONLY'):
            with self.subTest(define=define):
                check_policy(define)

    def test_model_rectangles(self):
        rnd = random.Random(25)
        for flags in (2, 6, 10, 14):
            for _ in range(35):
                mem = bytearray(rnd.randrange(8) for _ in range(65536))
                want = bytearray(mem)
                width, rows = rnd.randrange(0, 30), rnd.randrange(0, 10)
                astride, bstride = rnd.randrange(32, 50), rnd.randrange(32, 50)
                for row in range(max(1, rows)):
                    for col in range(max(1, width)):
                        value = 3 if flags & 8 else want[0x2000 + row * astride + col]
                        if not flags & 4 or value != 3:
                            want[0x4000 + row * bstride + col] = value
                model = DMA(mem.__getitem__, mem.__setitem__, None, blitter=True)
                for b in program(0x2000, 0x4000, width, rows, astride, bstride, flags) + [0xF3, 3, 0xF7, 3, 0xCF, 0x87]:
                    model.feed(b)
                self.assertEqual(mem, want)
                self.assertEqual(model.stats['reads'], 0 if flags & 8 else max(1, width) * max(1, rows))

    def test_physical_boundary_and_reset(self):
        ram = bytearray(0x40000)
        ram[0xFFFC:0x10004] = b'boundary'
        virtual = bytearray(65536)
        model = DMA(virtual.__getitem__, virtual.__setitem__, None, blitter=True, physical=ram)
        for b in program(0xFFFC, 0x2000, 8, 1, 8, 8, 3) + [0xDB, 2, 0xCF, 0x87]:
            model.feed(b)
        self.assertEqual(ram[0x22000:0x22008], b'boundary')
        model.feed(0xC3)
        self.assertEqual((model.flags, model.ahi, model.bhi, model.width), (0, 0, 0, 0))
        self.assertEqual((model.a, model.b), (0xFFFC, 0x2000))
        # A following ordinary job must use virtual RAM, never leaked physical/2D flags.
        virtual[0x1000:0x1003] = b'new'
        for b in [0x7D, 0, 0x10, 3, 0, 0x14, 0x10, 0xAD, 0, 0x30, 0xCF, 0x87]:
            model.feed(b)
        self.assertEqual(virtual[0x3000:0x3003], b'new')
        with self.assertRaises(DMAError):
            for b in program(0, 0, 1, 1, 1, 1, 3) + [0xDB, 4, 0xCF, 0x87]:
                model.feed(b)

    def test_rearm_port_and_zero(self):
        mem, out = bytearray(range(256)) * 256, []
        model = DMA(mem.__getitem__, mem.__setitem__, lambda p, v: out.append((p, v)))
        for b in [0xC3, 0x7D, 0xFF, 0xFF, 2, 0, 0x14, 0x28, 0xAD, 0x5B, 0, 0x82, 0xCF, 0x87]:
            model.feed(b)
        self.assertEqual(out, [(0x5B, 255), (0x5B, 0)])
        for b in [0x1D, 5, 0, 0xCF, 0x87]:
            model.feed(b)
        self.assertEqual(out[-2:], [(0x5B, 5), (0x5B, 6)])
        for b in [0x7D, 8, 0, 0, 0, 0xCF, 0x87]:
            model.feed(b)
        self.assertEqual(out[-1], (0x5B, 8))

    def test_negative_controls(self):
        code, sy = h.assemble()
        broken = bytearray(code)
        # Wrong destination stride: gap 16 instead of start-to-start distance 80.
        addr = sy['hlib_dma_rect_end'] - 4 - 0x8000
        self.assertEqual(broken[addr], 80)
        broken[addr] = 16
        with self.assertRaisesRegex(AssertionError, 'rectangle differs'):
            rectangle(bytes(broken), sy)
        model = DMA(lambda a: 0, lambda a, v: None, None)
        with self.assertRaisesRegex(DMAError, 'without blitter'):
            model.feed(0xDF)
        with self.assertRaisesRegex(DMAError, 'without load'):
            model.feed(0x87)
        with self.assertRaisesRegex(DMAError, 'unsupported'):
            model.feed(0xFB)
        # Omit reset after a transparent job: a zero byte that should be copied stays stale.
        mem = bytearray(65536)
        mem[0x3000] = 9
        model = DMA(mem.__getitem__, mem.__setitem__, None, blitter=True)
        for b in program(0x2000, 0x3000, 1, 1, 1, 1, 6) + [0xCF, 0x87, 0xCF, 0x87]:
            model.feed(b)
        self.assertNotEqual(mem[0x3000], mem[0x2000])

    def test_profiler_is_observational(self):
        from .hookprofile import InstructionCosts
        from .ikari_warriors import run_to
        # Known 12-T OUT (C),A; one byte uploaded, all other work in another bucket.
        code = bytes.fromhex('015b003e07ed793e033d20fdc31080')
        machines = [h._machine(code, speed=3) for _ in range(2)]
        p = InstructionCosts([(0x8000, 0x8010, 'generation')], [(0x8000, 'entry')])
        p.ns = machines[1][1]
        for i, (sim, nm) in enumerate(machines):
            sim.registers[h.PC] = 0x8000
            self.assertTrue(run_to(sim, 0x8010, {0x8000: 'entry'}, collections.Counter(), observer=p if i else None))
        self.assertEqual(list(machines[0][0].registers), list(machines[1][0].registers))
        self.assertEqual(machines[0][0].memory, machines[1][0].memory)
        self.assertEqual(machines[0][1].pattern, machines[1][1].pattern)
        self.assertEqual(p.upload_bytes, 1)
        self.assertEqual(p.raw['pattern port instructions'], 12)
        self.assertEqual(p.equivalent['pattern port instructions'], 1.5)
        self.assertEqual(sum(p.raw.values()), machines[1][0].registers[h.T])
        p.end_frame()
        self.assertEqual(p.report()['sync_intervals'], 1)

    def test_stall_accounting(self):
        code, sy = h.assemble()
        sim, nm = h._machine(code)
        setup(sim, nm, sy)
        nm.dma.stall = lambda n: setattr(nm, 'real', nm.real + 10000)
        before, cpu = nm.now(), sim.registers[h.T]
        h.call(sim, sy['hlib_dma_rect'], {h.H: 0x40, h.L: 0, h.D: 0x60, h.E: 0})
        self.assertEqual(nm.now() - before - (sim.registers[h.T] - cpu), 10000)
        # ORIGINAL pacing sees the injected stall through raster time and waits less,
        # rather than adding a complete target wait after the transfer.
        for stall in (0, 10000):
            sim, nm = h._machine(code, speed=3)
            setup(sim, nm, sy)
            nm.dma.stall = lambda n: setattr(nm, 'real', nm.real + stall)
            start = nm.now()
            h.call(sim, sy['hlib_pace_open'])
            h.call(sim, sy['hlib_dma_rect'], {h.H: 0x40, h.L: 0, h.D: 0x60, h.E: 0})
            target = h.lines16(20000)
            h.call(sim, sy['hlib_pace_wait'], {h.A: 0, h.H: target >> 8, h.L: target & 255})
            self.assertLess(abs(nm.now() - start - 20000), 448)


def selfcheck():
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(Checks).run(result)
    return [str(test) + ': ' + details for test, details in result.failures + result.errors]


if __name__ == '__main__':
    unittest.main()
