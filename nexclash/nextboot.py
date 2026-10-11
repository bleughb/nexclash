"""Simulated Next boot of a .nex built by z80tonex: runs the stub, the alt ROM fill (if any) and the
start-up tail on a model of the Next memory system until the snapshot PC, then checks the result.

Model (Part A facts only): 8K pages; MMU slots 0-7 via NEXTREG $50-$57, $FF in slot 0/1 = ROM;
an unlocked 7FFD/1FFD write remaps slots 0/1 to ROM and 6/7 to the 7FFD bank; 7FFD bit 5 locks
paging, NEXTREG $08 bit 7 = 1 unlocks it; ROM number = 1FFD bit 2 (hi) + 7FFD bit 4 (lo);
alt ROM $8C: bit 7 enable, bit 6 write mode (reads ROM, writes alt), image = ROM number bit 0.
NEX launch state: paging UNLOCKED (every hardware-tested build pages with legacy writes without
unlocking first) and ROM 0 selected (worst case: the stub must select ROM3 itself). Only ROM3 (48K
BASIC) is modelled; reading another ROM fails the check.

    python -m nexclash.nextboot GAME_sprites.nex GAME.z80 [PATCHED_REFERENCE_UNUSED]
"""
import sys
from .dizzy6 import _rw_simulator
from . import z80tonex as zt
from .build import rom48


def load_nex(path):
    d = open(path, 'rb').read()
    present = [b for b in range(112) if d[18 + b]]
    banks, off = {}, 512
    for b in zt.BANK_FILE_ORDER:
        if b in present:
            banks[b] = d[off:off + 16384]
            off += 16384
    return banks, d[12] | d[13] << 8, d[14] | d[15] << 8


def boot(nex, pc_stop, limit=5_000_000):
    """Run the NEX from its entry point until PC == pc_stop. Returns the machine state dict."""
    banks, sp, pc = load_nex(nex)
    pages = {}
    for b, data in banks.items():
        pages[2 * b] = bytearray(data[0:8192])
        pages[2 * b + 1] = bytearray(data[8192:16384])
    rom = rom48()
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 20, 21], 'nr': {0x8C: 0, 0x08: 0}, 'p7ffd': 0x00, 'p1ffd': 0,
          'alt': [bytearray(16384), bytearray(16384)], 'bad': [], 'sel': 0}

    def page(n):
        return pages.setdefault(n, bytearray(8192))

    def romn():
        return ((st['p1ffd'] >> 2) & 1) << 1 | ((st['p7ffd'] >> 4) & 1)

    class Mem(list):
        def __getitem__(s, a):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                n, r = romn(), st['nr'][0x8C]
                if r & 0xC0 == 0x80:
                    return st['alt'][n & 1][a]
                if n != 3:
                    st['bad'].append(('read of ROM %d' % n, a))
                    return 0
                return rom[a]
            return page(m)[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                if st['nr'][0x8C] & 0xC0 == 0xC0:
                    st['alt'][romn() & 1][a] = v
                return
            page(m)[a & 0x1FFF] = v

    Sim = _rw_simulator()
    sim = Sim(Mem([0] * 65536), {'PC': pc, 'SP': sp})
    R, ed = sim.registers, sim.after_ED
    from skoolkit.simulator import R2

    def nextreg(reg, val):
        st['nr'][reg] = val
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = val
        elif reg == 0x08 and val & 0x80:
            st['p7ffd'] &= ~0x20

    def nn():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], sim.memory[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs, port):
            return st['nr'].get(st['sel'], 0) if port == 0x253B else 0xFF

        def write_port(s, regs, port, value, *x):
            if port == 0x243B:
                st['sel'] = value
            elif port in (0x7FFD, 0x1FFD) and not st['p7ffd'] & 0x20:
                st['p7ffd' if port == 0x7FFD else 'p1ffd'] = value
                b = st['p7ffd'] & 7
                st['mmu'][0:2] = [0xFF, 0xFF]
                st['mmu'][6:8] = [2 * b, 2 * b + 1]
    sim.set_tracer(Tr())
    ops, mem, n = sim.opcodes, sim.memory, 0
    while R[24] != pc_stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            raise RuntimeError('boot did not reach PC %d (at %d)' % (pc_stop, R[24]))
    st['R'], st['mem'] = R, mem
    return st


def check(nex, z80, patch=None, tail=None):
    """Boot the NEX and compare with the snapshot: registers (except R), RAM 0x4000-0xFFFF (patched
    RAM from the NEX's own banks 5/2/0, except the tail bytes), what slots 0/1 show (ROM3 or
    ROM3 + alt ROM patch bytes), paging lock, $8C. Returns a list of problems (empty = OK)."""
    import copy
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)          # apply() again on a fresh snapshot, caller's object untouched
        patch.apply(s)
    st = boot(nex, s.pc)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = {'BC': w(2, 3), 'DE': w(4, 5), 'HL': w(6, 7), 'AF': w(0, 1), 'IX': w(8, 9), 'IY': w(10, 11),
           "BC'": w(18, 19), "DE'": w(20, 21), "HL'": w(22, 23), "AF'": w(16, 17), 'SP': R[12], 'I': R[14],
           'IM': R[27], 'IFF': R[26]}
    exp = {'BC': s.bc, 'DE': s.de, 'HL': s.hl, 'AF': s.a * 256 + s.f, 'IX': s.ix, 'IY': s.iy,
           "BC'": s.bc_, "DE'": s.de_, "HL'": s.hl_, "AF'": s.a_ * 256 + s.f_, 'SP': s.sp, 'I': s.i,
           'IM': s.im, 'IFF': s.iff1}
    bad += [('register', k, got[k], exp[k]) for k in exp if got[k] != exp[k]]
    ram = s.banks[5] + s.banks[2] + s.banks[0]
    t0, t1 = tail if tail else (0, 0)
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    rom = rom48()
    img = bytearray(rom)
    if getattr(patch, 'altrom', None) or getattr(patch, 'slot1', None):
        regs = zt.build_tail(s, 0x8000, patch.slot1, bool(getattr(patch, 'altrom', None)))[3]
        rb = patch.slot1[1]
        if getattr(patch, 'altrom', None):
            lo, hi = patch.altrom
            img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        else:
            img[0x2000:0x4000] = patch.page
        img[rb:rb + len(regs)] = regs                    # register block written by the stub
    if getattr(patch, 'altrom', None):
        if st['nr'][0x8C] != 0x80:
            bad.append(('$8C', st['nr'][0x8C]))
    elif st['nr'][0x8C] != 0:
        bad.append(('$8C', st['nr'][0x8C]))
    view = bytes(mem[a] for a in range(0x4000))
    if view != bytes(img):
        d = [a for a in range(0x4000) if view[a] != img[a]]
        bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
    if st['p7ffd'] & 0x30 != 0x30 or not st['p1ffd'] & 4:
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    s1 = patch.slot1[0] if getattr(patch, 'slot1', None) and not getattr(patch, 'altrom', None) else 0xFF
    if st['mmu'] != [0xFF, s1, 10, 11, 4, 5, 0, 1]:
        bad.append(('MMU', st['mmu']))
    return bad


if __name__ == '__main__':
    print(check(sys.argv[1], sys.argv[2]) or 'OK')
