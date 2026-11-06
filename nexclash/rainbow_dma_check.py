"""Execute the real sky game's patched tcommit with its MMU map and strict DMA effects.

python -m nexclash.rainbow_dma_check
No game data is used. Full recording verification is a separate game-specific command.
"""
import random
import unittest

from . import rainbow_z80n_sky as g
from .rainbow_dma import RainbowDMA, ORG
from .dma import DMAError


def commit_case(policy=2, core=0x33, hwim2=0, mbps=4, broken=None, start_line=307):
    from skoolkit.simulator import Simulator
    from .build import rom48
    patch = RainbowDMA(policy, core, hwim2, mbps)
    rng = random.Random(1480)
    ns = g.NextState(patch)
    ns.nr[0x50], ns.nr[7] = g.PAGE_S, 3
    ns.nr.update({0xCC: 0xFF, 0xCD: 0x81, 0xCE: 0x40}) # pending masks must never be blindly cleared
    before_nr = {r: ns.nr[r] for r in (0xC0, 0xCC, 0xCD, 0xCE)}
    source = bytes(rng.randrange(256) for _ in range(1280))
    shadow = ns.pages[g.PAGE_SH]
    shadow[:1280] = source
    ns.pages[g.PAGE_TM][:] = bytes(rng.randrange(256) for _ in range(8192))
    before = bytes(ns.pages[g.PAGE_TM])
    expected = bytearray(before)
    for row in range(20):
        expected[488+row*80:488+row*80+64] = source[row*64:(row+1)*64]
    ns.scratch[g.V_TOK] = 1
    ns.scratch[g.V_N58] = 160
    ns.scratch[g.V_MSB] = 3
    ns.scratch[g.V_LL:g.V_LL+2] = start_line.to_bytes(2, 'little')
    ns.scratch[0xFA:0xFC] = b'\x00\x80'
    mem = list(rom48()) + [0] * 49152
    mem[0x2000:0x4000] = patch.page
    if broken == 'wrong stride':
        off = patch.dma_syms['hlib_dma_rect_prog'] - 0x4000
        k = shadow.index(bytes.fromhex('ef5000'), off)
        shadow[k+1] = 79
    elif broken == 'no enable':
        off = patch.dma_syms['hlib_dma_rect_prog'] - 0x4000
        k = shadow.index(bytes.fromhex('cf87'), off)
        shadow[k+1] = 0x83
    elif broken == 'missing sample':
        shadow[0x1000+15:0x1000+18] = bytes(3) # final CALL LSAMP
    elif broken == 'old core bypass':
        # Change core comparison to accept 3.02 as DDMA; strict model must reject it.
        k = shadow.index(bytes.fromhex('fe33'), 0x1000)
        shadow[k+1] = 0x32
    elif broken == 'wrong mapping':
        k = mem.index(0x1C, patch.syms['tcommit'] + 7, patch.syms['tcommit'] + 12)
        mem[k] = 29

    class M:
        def __len__(self):
            return 65536
        def __getitem__(self, a):
            if a < 0x2000 and ns.nr.get(0x50) == g.PAGE_S:
                return ns.scratch[a]
            if 0x4000 <= a < 0x8000:
                page = ns.nr[0x50 + (a >> 13)]
                if page not in (10, 11):
                    return ns.pages[page][a & 8191]
            return mem[a]
        def __setitem__(self, a, v):
            if a < 0x2000 and ns.nr.get(0x50) == g.PAGE_S:
                ns.scratch[a] = v
            elif 0x4000 <= a < 0x8000 and ns.nr[0x50+(a >> 13)] not in (10, 11):
                ns.pages[ns.nr[0x50+(a >> 13)]][a & 8191] = v
            else:
                mem[a] = v
    ram = M()
    from .dizzy6 import _rw_simulator
    sim = g._machine(_rw_simulator(), ram, Simulator([0]*65536, {'PC': patch.syms['tcommit'], 'SP': 0xFA}).registers[:], ns)
    ns.line_x = (start_line - g.INT_LINE) * g.LINE_T
    if not g._run(sim, (0x8000,), 200000):
        raise AssertionError('tcommit did not return')
    assert bytes(ns.pages[g.PAGE_TM]) == expected, 'tilemap mismatch (including gaps and definitions)'
    assert bytes(shadow[:1280]) == source, 'source overwritten'
    assert ns.nr[0x52] == 10 and ns.nr[0x53] == 11, 'MMU not restored'
    assert ns.clip_tm == [16, 143, 48, 207] and ns.nr[0x6B] == 0x81, 'clip/enable changed'
    assert {r: ns.nr[r] for r in before_nr} == before_nr, 'interrupt state changed'
    assert ns.R[26] == 0, 'IFF enabled within ISR'
    assert ns.scratch[0xED] == 0, 'private stack exceeded lower bound'
    return ns, sim.registers[25]


def setup_case(patch):
    from skoolkit.simulator import Simulator
    mem = bytearray(65536)
    mem[0xD000:0xD000+len(patch.stub_extra)] = patch.stub_extra
    mem[0x8000:0x8003] = b'\xCD' + patch.setup_call.to_bytes(2, 'little')
    ns = g.NextState(patch)
    sim = g._machine(Simulator, mem, Simulator(mem, {'PC': 0x8000, 'SP': 0x7FF0}).registers[:], ns)
    assert g._run(sim, (0x8003,), 2000000), 'startup did not return'
    got = bytes(e[2] for e in ns.events if e[0] == 'nr' and e[1] == 0x41)
    assert got == patch.cfg.palette() + patch.cfg.tile_palette(), 'startup palette mismatch'
    assert ns.dma.stats['jobs'] == 0, 'startup initiated a transfer'


class Checks(unittest.TestCase):
    def test_game_policies_and_core_gate(self):
        for policy in (0, 1, 2):
            for core in (0x2F, 0x32, 0x33, 0xFF):
                for hwim2 in (0, 1):
                    with self.subTest(policy=policy, core=core, hwim2=hwim2):
                        ns, ticks = commit_case(policy, core, hwim2)
                        backend = min(policy, 2 if core >= 0x33 else 1) if 0x30 <= core < 0xFF and not hwim2 else 0
                        self.assertEqual(ns.dma.stats['jobs'], (0, 20, 1)[backend])
                        self.assertEqual(ns.dma.stats['writes'], 1280 if backend else 0)
                        if backend == 2:
                            self.assertEqual(ns.dma_jobs, [(2, 0, 64, 20, 64, 80)])

    def test_elapsed_stalls_and_recovery(self):
        for policy in (1, 2):
            fast, ft = commit_case(policy, mbps=8)
            slow, st = commit_case(policy, mbps=1)
            # Extra raster-read retries and the wrap branch have CPU cost too.
            delta = st-ft - (slow.dma_ticks-fast.dma_ticks)
            self.assertGreaterEqual(delta, 0)
            self.assertLess(delta, g.LINE_T)
            self.assertEqual(slow.scratch[g.V_WR], 1, 'stall wrap was not credited')
            sampled = int.from_bytes(slow.scratch[g.V_LL:g.V_LL+2], 'little')
            self.assertLessEqual((slow.video_line()-sampled) % 312, 1)

    def test_conservative_map_budget(self):
        for policy in (0, 1, 2):
            ns, ticks = commit_case(policy, mbps=0.5, start_line=240)
            self.assertLess(ticks, 64*g.LINE_T)

    def test_loading_entry_bank(self):
        import tempfile
        from pathlib import Path
        from . import nextboot
        header = bytearray(512)
        header[:8] = b'NextV1.2'
        header[9] = 2
        header[12:16] = bytes.fromhex('f0bf00c0')
        header[18+10] = header[18+32] = 1
        header[139] = 32
        # Bank 10 and the declared entry bank deliberately disagree.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'entry.nex'
            path.write_bytes(header + bytes.fromhex('3e11') + bytes(16382) +
                             bytes.fromhex('3e22') + bytes(16382))
            state = nextboot.boot(str(path), 0xC002)
            self.assertEqual(state['R'][0], 0x22)

    def test_clock_adjusted_complete_hook(self):
        from skoolkit.simulator import Simulator
        patch = RainbowDMA()
        ns = g.NextState(patch)
        mem = bytearray(65536)
        mem[0x8000:0x800A] = bytes.fromhex('ed91070300ed91070000')
        sim = g._machine(Simulator, mem, Simulator(mem, {'PC': 0x8000}).registers[:], ns)
        self.assertTrue(g._run(sim, (0x800A,)))
        raw, stalls, elapsed = ns.hook_times[0x8000][0]
        self.assertEqual((raw, stalls, elapsed), (48, 0, 216))
        self.assertEqual(sim.registers[25], 48, 'profiling changed emulated CPU time')

    def test_setup_palette_and_control(self):
        for policy in (0, 1, 2):
            setup_case(RainbowDMA(policy))
        patch = RainbowDMA()
        # A stale absolute palette operand must fail, even though setup still returns.
        bad = bytearray(patch.stub_extra)
        at = bad.index(0x21) + 1  # first LD HL,pal operand
        address = int.from_bytes(bad[at:at+2], 'little')
        bad[at:at+2] = (address+4).to_bytes(2, 'little')
        patch.stub_extra = bytes(bad)
        with self.assertRaises(AssertionError):
            setup_case(patch)

    def test_negative_controls(self):
        for name in ('wrong stride', 'no enable', 'wrong mapping'):
            with self.subTest(name=name), self.assertRaises((AssertionError, DMAError)):
                commit_case(broken=name)
        with self.assertRaises(DMAError):
            commit_case(core=0x32, broken='old core bypass')
        good, _ = commit_case(mbps=1)
        bad, _ = commit_case(mbps=1, broken='missing sample')
        self.assertNotEqual(good.scratch[g.V_WR], bad.scratch[g.V_WR])


def selfcheck():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    selfcheck()
