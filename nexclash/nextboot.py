"""Simulated Next boot of a .nex built by z80tonex: runs the stub, the alt ROM fill (if any) and the
start-up tail on a model of the Next memory system until the snapshot PC, then checks the result.

Model (Part A facts only): 8K pages; MMU slots 0-7 via NEXTREG $50-$57, $FF in slot 0/1 = ROM;
an unlocked 7FFD/1FFD write remaps slots 0/1 to ROM and 6/7 to the 7FFD bank; 7FFD bit 5 locks
paging, NEXTREG $08 bit 7 = 1 unlocks it; ROM number = 1FFD bit 2 (hi) + 7FFD bit 4 (lo);
alt ROM $8C: bit 7 enable, bit 6 write mode (reads ROM, writes alt), image = ROM number bit 0.
NEX launch state: paging UNLOCKED (every hardware-tested build pages with legacy writes without
unlocking first) and ROM 0 selected (worst case: the stub must select ROM3 itself). Only ROM3 (48K
BASIC) is modelled (ROMs 0-2 too when the 64K enNextZX.rom is given); reading another ROM fails the check.

The system ROM3 is what the Next really has (docs/REFACTOR.md 7): ROM3 of NextZXOS's enNextZX.rom
(enNextLG.rom's ROM3 is byte-identical), from the file named by $NEXCLASH_NEXT_ROM or `--next-rom PATH`
(the whole 64K enNextZX.rom, or its 16K ROM3; never in this repo: copy it from your card,
MACHINES/NEXT/enNextZX.rom). Without it Sinclair's ROM stands in and rom_model() says so. Verifiers
take the alt ROM image from alt_image(patch): what the stub leaves there, over that ROM3.

    python -m nexclash.nextboot GAME_sprites.nex GAME.z80 [PATCHED_REFERENCE_UNUSED]
"""
import os
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


NEXT_ROM = None             # set by `nexclash.py ... --next-rom PATH`; else $NEXCLASH_NEXT_ROM
_ROM3 = {}


def system_rom3():
    """-> (16K ROM3 the Next pages as ROM 3, label). NextZXOS's when a path is given, else Sinclair's."""
    import hashlib
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path not in _ROM3:
        if not path:
            _ROM3[path] = (rom48(), "Sinclair's 48K ROM (no --next-rom / NEXCLASH_NEXT_ROM: NextZXOS's ROM3 NOT modelled)")
        else:
            d = open(path, 'rb').read()
            if len(d) not in (16384, 65536):
                raise ValueError('%s: %d bytes; want enNextZX.rom (64K) or its ROM3 (16K)' % (path, len(d)))
            _ROM3[path] = (d[-16384:], 'ROM3 of %s (file md5 %s)' % (os.path.basename(path), hashlib.md5(d).hexdigest()[:8]))
    return _ROM3[path]


def rom_model():
    """One report line: which ROM3 the boot model and the verifiers use."""
    return system_rom3()[1]


def alt_image(patch, sysrom=None):
    """Alt ROM image 1 as the stub leaves it on the Next (z80tonex.altrom_fill): Sinclair's ROM (the
    whole-image fill) or the system ROM3 (old builds: `--altrom-fill rom3`), then the build's bytes
    lo..hi from patch.page and patch.altrom_low. The shared base of every verifier's alt ROM model:
    bytes outside lo..hi are what the Next has, not the page's (BRIEFING C2 #5)."""
    lo, hi = patch.altrom
    img = bytearray(rom48() if zt.altrom_whole(patch) else (sysrom or system_rom3()[0]))
    img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    if getattr(patch, 'altrom_low', None):
        img[0:0x2000] = patch.altrom_low[1]
    return img


def system_roms():
    """NextZXOS's four ROMs (enNextZX.rom, 64K) when given, else None (only ROM3 is modelled)."""
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path and os.path.getsize(path) == 65536:
        d = open(path, 'rb').read()
        return [d[k * 16384:(k + 1) * 16384] for k in range(4)]
    return None


def system_rom0():
    """-> (16K ROM 0 the Next pages as ROM 0, label): NextZXOS's (the first 16K of the 64K file) when
    given, else the 128K ROM 0 (SkoolKit's) stands in."""
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path and os.path.getsize(path) == 65536:
        return open(path, 'rb').read()[:16384], 'ROM0 of %s' % os.path.basename(path)
    return zt.rom128_0(), 'the 128K ROM 0 (NextZXOS ROM0 NOT modelled)'


def alt_image0(patch, rom0=None):
    """Alt ROM image 0 as the Next holds it: the 128K ROM 0 + the build's bytes (z80tonex.altrom0), or for
    an older build its setup's copy of the Next's ROM 0 + the hook bytes lo..hi (Target Renegade)."""
    a0 = zt.altrom0(patch)
    lo, hi = a0 or patch.altrom
    img = bytearray(zt.rom128_0() if a0 else (rom0 or system_rom0()[0]))
    img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    return img


def rom_view(patch, sysrom=None):
    """What the game sees at 0x0000-0x3FFF on the Next once the tail has run: the alt ROM image
    (alt_image), or for a slot-1 build the system ROM3's 0x0000-0x1FFF + its RAM page, or the ROM3."""
    rom = sysrom or system_rom3()[0]
    if getattr(patch, 'altrom', None):
        return alt_image(patch, rom)
    if getattr(patch, 'slot1', None) is not None and getattr(patch, 'page', None) is not None:
        return bytearray(rom[0:0x2000]) + bytearray(patch.page)
    return bytearray(rom)


def start_pc(nex):
    """The snapshot PC a built .nex jumps to (tail_of)."""
    return tail_of(nex)[0]


def tail_of(nex):
    """-> (snapshot PC, tail address, tail length) of a built .nex: the tail's JP (z80tonex.build_tail; the
    stub copies the tail with LD DE,tail / LD BC,len / LDIR / LD (tail+p3),A / JP tail, its bytes after)."""
    banks, _, _ = load_nex(nex)
    st = banks[zt.STUB_BANK][:0x1000]
    for i in range(len(st) - 14):
        if st[i] == 0x11 and st[i + 3] == 0x01 and st[i + 6:i + 8] == b'\xED\xB0' and st[i + 8] == 0x32 \
                and st[i + 11] == 0xC3 and st[i + 12:i + 14] == st[i + 1:i + 3]:
            n = st[i + 4] | st[i + 5] << 8
            t = st[i + 14:i + 14 + n]
            for k in (n - 3, n - 23):                       # compact tail / tail + its 20-byte register block
                if k > 0 and t[k] == 0xC3:
                    return t[k + 1] | t[k + 2] << 8, st[i + 1] | st[i + 2] << 8, n
    raise ValueError('%s: no z80tonex start-up tail found' % nex)


def rom_paths(nexes, rzxs, stop=None, sysrom=None, z80=None):
    """Every ROM byte the ORIGINAL game runs or reads in its recordings, against what each built .nex
    gives it on the Next: the .nex booted over the system ROM3 (system_rom3(): NextZXOS's when given) to
    the game start - its alt ROM images, slot-1 page or the ROM3 itself. The per-event verifiers run
    patched code only from a hook to its return, so a ROM path outside the hooks (IM 1, a ROM print) never
    runs there: Starquake's UDG print into the hooks passed them. One replay per recording for all builds.
    -> {nex: (kind, lines, faults)}: kind 'alt' / 'slot1' / 'plain'; faults = ROM addresses the game RUNS
    whose byte differs on the Next ('alt' / 'slot1': the build owns that ROM, each is a fault; 'plain':
    the Next's own ROM3 runs, reported only), and data reads of differing bytes that come from the Next's
    own ROM (the byte equals NextZXOS's there: Target Renegade e0b246e3's sound data); data reads of bytes
    the build wrote (an IM 2 vector) are listed only. Also the start-up tail (z80tonex): its bytes stay in
    game RAM, so the game must never read one before writing it (Match Day: the trophy's attributes).
    z80 (the build's snapshot): also the printer buffer bytes the .nex starts with differently, booted
    as NEXLOAD leaves it (NEXLOAD_PRINTER) - a warning: the stub puts it back only with
    keep_printer_buffer (BRIEFING C2 #36)."""
    from skoolkit import ROM48, ROM128, read_bin_file
    from .simrun import run
    builds, sysr = [], system_roms() or [None, None, None, sysrom or system_rom3()[0]]
    if sysrom is not None:
        sysr[3] = sysrom
    tails = {nex: tail_of(nex) for nex in nexes}
    for nex in nexes:
        st = boot(nex, tails[nex][0], sysrom=sysrom or system_rom3()[0], nexload=z80 is not None)
        alt_on = bool(st['nr'].get(0x8C, 0) & 0x80)
        kind = 'alt' if alt_on else ('slot1' if st['mmu'][1] != 0xFF else 'plain')
        builds.append((nex, kind, alt_on, st, bytes(st['mem'][a] for a in range(0x4000)), 2 if st['p1ffd'] & 4 else 0))
    out = {nex: (kind, [], {}) for nex, kind, *_ in builds}
    o48 = list(read_bin_file(ROM48, 16384))
    o128 = [list(read_bin_file(ROM128[0], 16384)), list(read_bin_file(ROM128[1], 16384))]
    pbuf = {}
    if z80 is not None:
        snap = zt.Z80Snapshot(z80)
        for nex, kind, alt_on, st, *_x in builds:
            pbuf[nex] = [a for a in range(0x5B00, 0x5C00) if st['mem'][a] != snap.read(a)]
    watch = {a for n in nexes for a in range(tails[n][1], tails[n][1] + tails[n][2])} | {a for v in pbuf.values() for a in v}
    for r in rzxs:
        frame, seen, tabs, written, tread = [0], set(), [], set(), {}

        class H:
            def on_sim(h, sim):
                h.is128 = hasattr(sim.memory, 'o7ffd')
                orig = o128 if h.is128 else [o48, o48]
                tabs[:] = []
                for nex, kind, alt_on, st, view, hi_rom in builds:
                    nx, d = {}, {}
                    for sel in (0, 1):
                        img = st['alt'][sel if h.is128 else 1] if alt_on else (
                            None if h.is128 and (hi_rom | sel) != 3 else view)      # another system ROM: not modelled
                        nx[sel] = img
                        d[sel] = {a for a in range(0x4000) if img[a] != orig[sel][a]} if img is not None else None
                    tabs.append((nex, nx, d, orig, {}))

            def on_read(h, a, pc, mem):
                if a >= 0x4000:
                    if a in watch and a not in written and a not in tread:          # data or code fetch
                        tread[a] = (pc, frame[0])
                    return
                sel = (mem.o7ffd >> 4) & 1 if h.is128 else 1
                seen.add((sel, a))
                ex = pc <= a <= pc + 3
                for nex, nx, d, orig, diff in tabs:
                    ds = d[sel]
                    if ds is None:
                        diff.setdefault(('?', sel, ''), (pc, frame[0]))
                    elif a in ds:
                        own = sysr[3 if sel else 0]          # where an old fill's byte came from (ROM3 / ROM 0)
                        k = (sel, a, 'run' if ex else ('next' if own is not None and own[a] == nx[sel][a] else 'data'))
                        if k not in diff:
                            diff[k] = (pc, frame[0], orig[sel][a], nx[sel][a])

            def on_write(h, a, v, pc, mem):
                if a in watch:
                    written.add(a)

            def on_frame(h, n):
                frame[0] = n
        n = run(None, [r], H(), stop=stop)
        name = os.path.basename(r)
        for (nex, nx, d, orig, diff), (_, kind, alt_on, *_x) in zip(tabs, builds):
            lines, faults = out[nex][1], out[nex][2]
            run_d = sorted(k for k in diff if k[0] != '?' and k[2] in ('run', 'next'))
            data_d = sorted(k for k in diff if k[0] != '?' and k[2] == 'data')
            unk = sorted({k[1] for k in diff if k[0] == '?'})
            img = (lambda sel: 'image %d ' % sel) if alt_on else (lambda sel: '')
            head = '%s: %s %d frames, %d ROM bytes used' % (os.path.basename(nex), name, n, len(seen))
            if run_d and kind != 'plain':
                faults[name] = run_d
                lines.append('%s; MISMATCH: the Next gives other ROM bytes at %d addresses the game runs or reads '
                             '(the Next\'s own ROM there): %s' % (head, len(run_d), ', '.join(
                                 '%s0x%04X %s (%02X here, %02X recorded; PC 0x%04X frame %d)' % (
                                     (img(k[0]), k[1], 'run' if k[2] == 'run' else 'read') + (diff[k][3], diff[k][2]) + diff[k][:2])
                                 for k in run_d[:4])))
            elif run_d:
                lines.append('%s; plain build (the Next\'s own ROM3 runs): %d bytes it runs or reads differ from the recording\'s ROM, e.g. %s'
                             % (head, len(run_d), ', '.join('0x%04X' % k[1] for k in run_d[:6])))
            else:
                lines.append('%s; every byte the game runs is as recorded' % head)
            if data_d:
                lines.append('            reads %d ROM bytes held differently on the Next (data: the build\'s own, e.g. a '
                             'vector, or a fault): %s' % (len(data_d), ', '.join('%s0x%04X' % (img(k[0]), k[1]) for k in data_d[:8])))
            if unk:
                lines.append('            ROM select %s not modelled (a Next system ROM other than ROM3)' % ', '.join(map(str, unk)))
            ta, tn = tails[nex][1], tails[nex][2]
            rd = sorted(a for a in tread if ta <= a < ta + tn)
            if rd:
                faults.setdefault(name, []).append(('tail', rd[0]))
                lines.append('            MISMATCH: the game reads the start-up tail\'s bytes before writing them: %d of '
                             '0x%04X-0x%04X, first 0x%04X (PC %d, frame %d); they hold the tail, not the snapshot\'s'
                             % (len(rd), ta, ta + tn - 1, rd[0], tread[rd[0]][0], tread[rd[0]][1]))
            else:
                lines.append('            tail 0x%04X-0x%04X: never read before written' % (ta, ta + tn - 1))
            pb = sorted(a for a in tread if a in pbuf.get(nex, ()) and not ta <= a < ta + tn)
            if pb:
                lines.append('            WARNING: the game reads %d printer buffer bytes before writing them, which the .nex '
                             'leaves as NEXLOAD wrote them (first 0x%04X, PC %d, frame %d): keep_printer_buffer '
                             '(BRIEFING C2 #36)' % (len(pb), pb[0], tread[pb[0]][0], tread[pb[0]][1]))
    return out


# What NEXLOAD leaves in the 48K printer buffer before the stub runs (NextZXOS paging routines and
# system variables live at 0x5B00-0x5BFF; hardware 2026-10-20, Match Day): modelled as a pattern no
# game data matches, so a check with nexload=True shows every byte the stub does not put back.
NEXLOAD_PRINTER = bytes((0xA5 ^ k) for k in range(256))


def boot(nex, pc_stop, limit=5_000_000, nexload=False, sysrom=None):
    """Run the NEX from its entry point until PC == pc_stop. Returns the machine state dict.
    nexload: start with the printer buffer overwritten as NEXLOAD leaves it (NEXLOAD_PRINTER).
    sysrom: the system ROM3 (default Sinclair's: a check of the stub alone, as the engines' own boot
    checks expect; check() and rom_paths() pass system_rom3(), NextZXOS's when given; pass a different
    ROM to prove an image does not depend on it, BRIEFING C2 #5)."""
    banks, sp, pc = load_nex(nex)
    pages = {}
    for b, data in banks.items():
        pages[2 * b] = bytearray(data[0:8192])
        pages[2 * b + 1] = bytearray(data[8192:16384])
    if nexload and 10 in pages:
        pages[10][0x1B00:0x1C00] = NEXLOAD_PRINTER
    rom = sysrom if sysrom is not None else rom48()
    others = system_roms()                     # NextZXOS's ROMs 0-2 when the 64K file is given
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 20, 21], 'nr': {0x8C: 0, 0x08: 0}, 'p7ffd': 0x00, 'p1ffd': 0,
          'alt': [bytearray(16384), bytearray(16384)], 'bad': [], 'sel': 0, 'ports': {}, 'nrlog': []}

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
                    return others[n][a] if others else 0
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
        st['nrlog'].append((reg, val))         # every NEXTREG write in order (palette uploads)
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
            st['ports'][port] = value          # last value written to each port (e.g. 0x123B)
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


def check(nex, z80, patch=None, tail=None, nexload=False, sysrom=None):
    """Boot the NEX and compare with the snapshot: registers (except R), RAM 0x4000-0xFFFF (patched
    RAM from the NEX's own banks 5/2/0, except the tail bytes), what slots 0/1 show (ROM3 or
    ROM3 + alt ROM patch bytes), paging lock, $8C. Returns a list of problems (empty = OK).
    nexload=True: the printer buffer starts as NEXLOAD leaves it (a build must put it back)."""
    import copy
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)          # apply() again on a fresh snapshot, caller's object untouched
        patch.apply(s)
    sysrom = sysrom if sysrom is not None else system_rom3()[0]
    st = boot(nex, s.pc, nexload=nexload, sysrom=sysrom)
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
    img = bytearray(sysrom)
    if getattr(patch, 'altrom', None) or getattr(patch, 'slot1', None):
        regs = zt.build_tail(s, 0x8000, patch.slot1, bool(getattr(patch, 'altrom', None)))[3]
        rb = patch.slot1[1]
        if getattr(patch, 'altrom', None):
            img = alt_image(patch, sysrom)                   # what the stub writes (z80tonex.altrom_fill)
        else:
            img[0x2000:0x4000] = patch.page
        img[rb:rb + len(regs)] = regs                    # register block written by the stub
    if zt.altrom0(patch):                                # alt image 0 = the 128K ROM 0 + the build's bytes
        lo0, hi0 = zt.altrom0(patch)
        img0 = bytearray(zt.rom128_0())
        img0[lo0:hi0] = patch.page[lo0 - 0x2000:hi0 - 0x2000]
        if bytes(st['alt'][0]) != bytes(img0):
            bad.append(('alt image 0 differs from the 128K ROM 0 + the build\'s bytes',))
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
