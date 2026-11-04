"""Inferno stage-2 foundation: banked tape bytes and original-ROM decoder equivalence.

Not registered in engines.py: no sprite build exists yet. Run the assembled loader tests with
python -m nexclash.inferno --loader-tests ../specnext/reference/inferno/Inferno.tzx.
The independent oracle executes the original ROM decoder, feeding complete bytes at 05D8;
it does not claim physical tape-edge timing equivalence or full-game continuation coverage.
"""
import argparse
from collections import Counter
from functools import reduce
import json
from pathlib import Path

ROM_ORG, ALT_PAGE, STATE_PAGE = 0x386E, 24, 68
TAPE_FIRST, TAPE_LAST = 32, 55
CMP = tuple(i for i in range(30) if i not in (15, 25, 29))
ROOT = Path(__file__).resolve().parent.parent


def _profile_path():
    return ROOT / 'docs/profiles/inferno.json'


def load_profile():
    return json.loads(_profile_path().read_text())


def is_inferno(snap):
    """Fail closed until the renderer's checked signature and sites are established."""
    sg = load_profile()['signature']
    sig = bytes.fromhex(sg['bytes'])
    return bool(sig) and snap.machine == '48K' and bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def tape_blocks(path):
    """Refuse unsupported content rather than silently losing a tape control block."""
    from skoolkit.tape import parse_tzx
    tape = parse_tzx(str(path))
    if tape.warnings:
        raise ValueError('TZX warnings: ' + str(tape.warnings))
    blocks = []
    for b in tape.blocks:
        if b.block_id == 0x10:
            data = bytes(b.data)
            if len(data) < 2 or reduce(int.__xor__, data, 0):
                raise ValueError('invalid block/checksum at TZX block %d' % b.number)
            blocks.append(data)
        elif b.block_id not in (0x20, 0x30):
            raise ValueError('unsupported TZX block %02x' % b.block_id)
    if len(blocks) != 32:
        raise ValueError('Inferno requires the 32 original header/data blocks')
    for i in range(0, len(blocks), 2):
        h, d = blocks[i:i + 2]
        if len(h) != 19 or h[0] != 0 or d[0] != 255:
            raise ValueError('invalid header/data pair %d' % (i // 2))
        if int.from_bytes(h[12:14], 'little') != len(d) - 2:
            raise ValueError('header length mismatch at pair %d' % (i // 2))
    return blocks


def packed_tape(blocks, start=4):
    """Pack raw blocks unchanged; descriptors address byte 0 (the flag) and include checksum."""
    if not 0 <= start <= len(blocks) <= 32:
        raise ValueError('invalid tape cursor/count')
    payload = bytearray()
    state = bytearray(8192)
    state[0:2] = bytes((start, len(blocks)))
    for i, block in enumerate(blocks):
        if not 2 <= len(block) <= 65535:
            raise ValueError('invalid raw block length')
        page, off = divmod(len(payload), 8192)
        desc = bytes((TAPE_FIRST + page,)) + off.to_bytes(2, 'little') + len(block).to_bytes(2, 'little')
        state[0x100 + 5 * i:0x105 + 5 * i] = desc
        payload.extend(block)
    if len(payload) > (TAPE_LAST - TAPE_FIRST + 1) * 8192:
        raise ValueError('tape exceeds reserved pages')
    pages = {TAPE_FIRST + i: bytearray(payload[i * 8192:(i + 1) * 8192]).ljust(8192, b'\0')
             for i in range((len(payload) + 8191) // 8192)}
    pages[STATE_PAGE] = state
    return pages


def loader_rom(code=None):
    from .build import rom48
    rom = bytearray(rom48())
    prof = load_profile()
    entry = prof['loader']['entry']
    old = bytes.fromhex(prof['loader']['original'])
    if rom[entry:entry + len(old)] != old:
        raise ValueError('unexpected ROM loader entry')
    code = code if code is not None else bytes.fromhex(prof['hooks']['rom'])
    if ROM_ORG + len(code) > 0x3D00 or any(b != 255 for b in rom[ROM_ORG:ROM_ORG + len(code) + 20]):
        raise ValueError('loader does not fit unused ROM')
    rom[entry:entry + 3] = b'\xC3' + ROM_ORG.to_bytes(2, 'little')
    rom[ROM_ORG:ROM_ORG + len(code)] = code
    return rom


class LoaderMemory:
    """48K RAM unchanged, alt ROM and slot-0 tape/state mapping; all writes audited."""
    def __init__(self, ram, pages, code=None):
        self.ram = list(ram)
        self.rom = loader_rom(code)
        self.pages = {p: bytearray(v) for p, v in pages.items()}
        self.mmu0 = 255
        self.writes = []
        self.maps = []

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        if a < 8192 and self.mmu0 != 255:
            return self.pages[self.mmu0][a]
        return self.rom[a] if a < 16384 else self.ram[a]

    def __setitem__(self, a, v):
        self.writes.append((a, v, self.mmu0))
        if a < 8192 and self.mmu0 != 255:
            self.pages[self.mmu0][a] = v
        elif a >= 16384:
            self.ram[a] = v
        else:
            raise AssertionError('write to read-only ROM: %04X' % a)

    def nextreg(self, reg, value):
        if reg != 0x50:
            raise AssertionError('unexpected NextReg %02X' % reg)
        if value != 255 and value != STATE_PAGE and not TAPE_FIRST <= value <= TAPE_LAST:
            raise AssertionError('unallocated page %d' % value)
        self.mmu0 = value
        self.maps.append(value)



class BootstrapPatch:
    """Diagnostic loader-only build, starting at the original tape's first USR 24200.

    Tail 5D30 is untouched through the 2,000-frame initial startup scan; later lifetime
    is NOT yet proved. This class is deliberately unavailable through auto detection.
    """
    name = 'Inferno diagnostic bank loader (no sprites; not a release)'
    uses_printer_buffer = True
    keep_printer_buffer = True
    tail_addr, max_tail = 0x5D30, 0x100
    stub_extra, hook_page_data, setup_call = b'', b'', None
    sites = ()

    def __init__(self, blocks):
        self.pages = packed_tape(blocks)
        rom = loader_rom()
        self.regblock = int(load_profile()['hooks']['syms']['rom_end'], 16)
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)
        self.altrom_low = (26, bytes(rom[:8192]))
        self.page = bytes(rom[8192:])
        self.extra_banks = {12: self.page + bytes(8192), 13: self.altrom_low[1] + bytes(8192)}
        for p, data in self.pages.items():
            bank = p // 2
            image = bytearray(self.extra_banks.get(bank, bytes(16384)))
            off = (p & 1) * 8192
            image[off:off + 8192] = data
            self.extra_banks[bank] = bytes(image)

    def apply(self, snap):
        if snap.is128 or snap.pc != 24200:
            raise ValueError('bootstrap requires the original tape at first USR 24200')
        # Check the compressed main entry, before decompression or any game patch.
        sig = bytes.fromhex('CDFECECD56D3C310D3')
        ram = snap.banks[5] + snap.banks[2] + snap.banks[0]
        if bytes(ram[24200 - 16384:24200 - 16384 + len(sig)]) != sig:
            raise ValueError('unexpected compressed main entry')


def bootstrap(tape, folder):
    """Reproduce BASIC startup from the actual TZX, then check a diagnostic NEX boot.

    No restored gameplay snapshots, synthesized BASIC variables, new front end or level menu.
    Full ROM images make this independent of NextZXOS's ROM3 data in the FF hook area.
    """
    import subprocess
    import sys
    from hashlib import md5
    from . import z80tonex, nextboot
    from .build import rom48
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / 'Inferno_bootstrap.z80'
    log = folder / 'bootstrap_tape.log'
    with log.open('w') as out:
        subprocess.run([sys.executable, '-c',
                        'from skoolkit.tap2sna import main; import sys; main(sys.argv[1:])',
                        str(tape), '--start', '24200', str(snapshot)],
                       stdout=out, stderr=subprocess.STDOUT, check=True)
    patch = BootstrapPatch(tape_blocks(tape))
    nex = folder / 'Inferno_loader_diagnostic.nex'
    _, tail, data, _ = z80tonex.convert(str(snapshot), str(nex), quiet=True, patch=patch)
    results = {}
    for label, foreign in [('Sinclair', None), ('foreign ROM3', bytes(v ^ 0xA5 for v in rom48()))]:
        results[label] = nextboot.check(str(nex), str(snapshot), patch, (tail, tail + len(data)),
                                        nexload=True, sysrom=foreign)
    return {'boot_checks': results, 'tail': [tail, tail + len(data)],
            'snapshot_md5': md5(snapshot.read_bytes()).hexdigest(),
            'nex_md5': md5(nex.read_bytes()).hexdigest(),
            'scope': 'diagnostic boot only; no full continuation or sprite release'}


def run_loader(ram, regs, pages, code=None, limit=4_000_000):
    """Run the assembled hook to its CALL return, auditing every instruction's mapping/IFF."""
    from .dizzy6 import _rw_simulator
    from . import z80n
    mem = LoaderMemory(ram, pages, code)
    sim = _rw_simulator()(mem)
    sim.registers[:] = regs
    R = sim.registers
    sp = R[12]
    ret = ram[sp] | ram[(sp + 1) & 65535] << 8
    z80n.install(sim, mem.nextreg)
    steps = 0
    while R[24] != ret or R[12] != (sp + 2) & 65535:
        if steps >= limit:
            raise RuntimeError('loader did not return')
        sim.opcodes[mem[R[24]]]()
        if mem.mmu0 != 255 and R[26]:
            raise AssertionError('interrupt enabled with tape/state mapped')
        steps += 1
    if mem.mmu0 != 255 or R[26]:
        raise AssertionError('loader did not restore ROM/DI')
    return sim, mem, steps


def rom_byte_oracle(ram, regs, block):
    """Independent original ROM instructions; substitute completed bytes, never copy hook logic.

    Entry is after INC D / EX AF / DEC D / DI. Model the tape's clean byte boundary, C=22,
    B=B0, at 05D8. Missing bytes take the edge-timeout return (XOR A canonical failure).
    Memory below the returned SP is dead stack; compare it only when callers have converged.
    """
    from skoolkit.simulator import Simulator
    from .build import rom48
    mem = list(rom48()) + list(ram[16384:])
    sim = Simulator(mem)
    R = sim.registers
    R[:] = regs
    sp = R[12]
    ret = mem[sp] | mem[(sp + 1) & 65535] << 8
    R[6], R[2], R[3], R[26] = 0, 176, 0x22, 0
    cursor = 0
    R[24] = 0x5C8
    while R[24] != ret or R[12] != (sp + 2) & 65535:
        if R[24] == 0x5C8:
            if cursor >= len(block):
                R[0], R[1], R[24] = 0, 0x44, 0x5E2
            else:
                R[2], R[7], R[24] = 176, block[cursor], 0x5D8
                cursor += 1
        else:
            sim.opcodes[mem[R[24]]]()
    return sim


def _case(blocks, index, length, flag=255, verify=False, code=None, dest=0xA000, corrupt_verify=False):
    """Deterministic non-zero registers/RAM make preservation failures visible."""
    from skoolkit.simulator import Simulator
    ram = [(i * 37 + (i >> 8) * 11) & 255 for i in range(65536)]
    block = blocks[index] if index < len(blocks) else b''
    if verify and block:
        for i, v in enumerate(block[1:1 + length]):
            a = (dest + i) & 65535
            if a >= 16384:
                ram[a] = v
        if corrupt_verify:
            ram[dest] ^= 1
    regs = list(Simulator([0] * 65536).registers)
    for i in (*range(8), *range(16, 24)):
        regs[i] = (i * 19 + 13) & 255
    regs[8], regs[9] = dest >> 8, dest & 255
    regs[10], regs[11] = 0xAB, 0xCD
    regs[4], regs[5] = length >> 8, length & 255
    regs[12], regs[24], regs[26], regs[27], regs[14] = 0x5B80, 0x562, 0, 2, 0xFE
    # AF' is the flag and carry saved by the game's 7311/7312/7313 sequence.
    # AF' captures INC D flags, before DEC D restores the requested length.
    d = length >> 8
    from skoolkit.simtables import INC
    regs[16], regs[17] = flag, INC[0][d][1] | (not verify)
    ram[0x5B80:0x5B82] = [0x00, 0x80]
    pages = packed_tape(blocks, index)
    patched, memory, steps = run_loader(ram, regs, pages, code)
    original = rom_byte_oracle(ram, regs, block)
    errors = []
    diff = [i for i in CMP if patched.registers[i] != original.registers[i]]
    if diff:
        errors.append(('registers', [(i, original.registers[i], patched.registers[i]) for i in diff]))
    # The hook uses 24 bytes below entry SP. Neither caller nor oracle reads those dead bytes.
    diff = [a for a in range(16384, 65536) if not 0x5B68 <= a < 0x5B80
            and memory.ram[a] != original.memory[a]]
    if diff:
        errors.append(('memory', diff[:8]))
    if memory.pages[STATE_PAGE][0] != min(index + 1, len(blocks)):
        errors.append(('cursor', memory.pages[STATE_PAGE][0]))
    if any(a < 8192 and not (page == STATE_PAGE and a == 0) for a, v, page in memory.writes):
        errors.append(('write outside cursor',))
    if any(memory.pages[p] != pages[p] for p in pages if p != STATE_PAGE):
        errors.append(('payload modified',))
    return errors, steps, patched.registers[1] & 1


def loader_tests(path):
    blocks = tape_blocks(path)
    counts, examples = Counter(), []

    def check(name, bs, i, n, **kw):
        errors, steps, carry = _case(bs, i, n, **kw)
        counts[name] += 1
        counts['instructions'] += steps
        if errors:
            counts['loader!'] += 1
            if len(examples) < 5:
                examples.append((name, i, n, errors))
        return errors, carry

    for i, b in enumerate(blocks):
        n = len(b) - 2
        h = blocks[i - 1] if i % 2 else None
        dest = (int.from_bytes(h[14:16], 'little') if h[1] == 3 else 23755) if h else 0xA000
        check('real block', blocks, i, n, flag=b[0], dest=dest)
        check('verify block', blocks, i, n, flag=b[0], verify=True, dest=dest)
    for n in (0, 1, 17, 255, 256, 8191, 8192, 8193, 21536):
        check('capacity', blocks, 5, n)
    check('wrong flag', blocks, 4, 17, flag=255)
    bad = list(blocks)
    bad[5] = bad[5][:-1] + bytes((bad[5][-1] ^ 1,))
    _, carry = check('bad checksum', bad, 5, len(bad[5]) - 2)
    if carry:
        counts['checksum accepted!'] += 1
    check('verify mismatch', blocks, 5, len(blocks[5]) - 2, verify=True, corrupt_verify=True)
    check('exhausted', blocks, len(blocks), 17)
    for dest in (0x1FF8, 0x3FF8, 0xFFF8):
        check('ROM/wrap destination', blocks, 5, 17, dest=dest)
        check('ROM/wrap verify', blocks, 5, 17, dest=dest, verify=True)
    # The broken builds use the real packed tape, never substitute good tables.
    prof = load_profile()
    code = bytearray.fromhex(prof['hooks']['rom'])
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    controls = [('write_byte', b'\0\0\0', 5, len(blocks[5]) - 2),
                ('parity', b'\xFE\x00', 5, len(blocks[5]) - 2)]
    for label, replacement, i, n in controls:
        broken = bytearray(code)
        off = syms[label] - ROM_ORG
        broken[off:off + len(replacement)] = replacement
        errors, _, _ = _case(blocks, i, n, code=broken)
        counts['negative control'] += 1
        if not errors:
            counts['negative control!'] += 1
    return counts, examples



def continuation_case(snapshot, blocks, level, limit=2_000_000):
    """Crafted original 7131 invocation, not a recorded transition or full-game proof.

    Both machines run the game's 7131 loader and Na initializer up to CALL Nb (718C). One uses the original ROM decoder;
    the other runs the assembled bank hook. Any differing hook stack bytes must be overwritten
    before a later read. No timed interrupts are supplied; HALT before the handoff fails this prefix test.
    """
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    from skoolkit.simulator import Simulator
    from .build import rom48
    source = from_snapshot(Simulator, Snapshot.get(str(snapshot)))
    regs = list(source.registers)
    regs[0], regs[24], regs[26] = level, 0x7131, 0
    ram = list(source.memory)
    if bytes(ram[0x7131:0x7137]) != bytes.fromhex('211271E5C630'):
        raise ValueError('unexpected original loading routine')
    cursor = 4 + 4 * level
    pages = packed_tape(blocks, cursor)
    po = LoaderMemory(ram, pages)
    oo = LoaderMemory(ram, pages)
    oo.rom = bytearray(rom48())
    dead = set()

    class Watch:
        def __init__(self, base, watch):
            self.base, self.watch = base, watch

        def __getitem__(self, a):
            if isinstance(a, slice):
                return [self[i] for i in range(*a.indices(65536))]
            if self.watch and a in dead:
                raise AssertionError('caller reads differing hook-stack byte %04X' % a)
            return self.base[a]

        def __setitem__(self, a, v):
            if self.watch:
                dead.discard(a)
            self.base[a] = v

    # Both full-game paths ignore original ROM writes just as the Spectrum does.
    class Tracer:
        def __init__(self):
            self.outputs = []

        def read_port(self, regs, port):
            return 255

        def write_port(self, regs, port, value, *args):
            self.outputs.append((port, value))
            if port & 1 and port not in (0x7FFD, 0x1FFD) and port & 0xC002 not in (0x8000, 0xC000):
                raise AssertionError('unclassified loader port %04X' % port)

    original, patched = Simulator(Watch(oo, False)), Simulator(Watch(po, True))
    traces = [Tracer(), Tracer()]
    for sim, tracer in zip((original, patched), traces):
        sim.registers[:] = regs
        sim.set_tracer(tracer)
    calls, steps = 0, 0
    refresh_reads = Counter()
    original_cursor = cursor
    while patched.registers[24] != 0x718C or steps == 0:
        pc = patched.registers[24]
        if pc != original.registers[24]:
            raise AssertionError('continuation diverged at %04X / %04X' % (pc, original.registers[24]))
        if steps >= limit:
            raise RuntimeError('continuation instruction limit at %04X' % pc)
        if pc == 0x562:
            entry_sp = patched.registers[12]
            new, pm, _ = run_loader(po.ram, patched.registers, po.pages)
            block = blocks[original_cursor] if original_cursor < len(blocks) else b''
            orig = rom_byte_oracle(oo.ram, original.registers, block)
            original_cursor += 1
            po.ram[:], po.pages = pm.ram, pm.pages
            oo.ram[:] = orig.memory
            patched.registers[:], original.registers[:] = new.registers, orig.registers
            differences = {a for a in range(16384, 65536) if po.ram[a] != oo.ram[a]}
            allowed = dead | set(range(entry_sp - 24, entry_sp))
            if differences - allowed:
                raise AssertionError('loader differs outside dead stack: ' + str(sorted(differences - allowed)[:8]))
            dead = differences
            calls += 1
        else:
            if po[pc] == 0x76:
                raise RuntimeError('unexpected HALT before Nb handoff at %04X' % pc)
            if oo[pc] == 0xED and oo[(pc + 1) & 65535] == 0x5F:
                # R is a nondeterministic input (tape pulse acquisition and bank hooks have
                # different M1 counts). Compare continuation under the SAME R input; report
                # each such site rather than quietly treating derived A/RAM as exempt.
                original.registers[15] = patched.registers[15]
                refresh_reads['%04X' % pc] += 1
            original.opcodes[oo[pc]]()
            patched.opcodes[po[pc]]()
        if any(patched.registers[i] != original.registers[i] for i in CMP):
            raise AssertionError('continuation register difference after %04X: %s' %
                                 (pc, [(i, original.registers[i], patched.registers[i]) for i in CMP
                                       if patched.registers[i] != original.registers[i]]))
        steps += 1
    if calls != 4 or po.pages[STATE_PAGE][0] != cursor + 4:
        raise AssertionError('did not consume both header/data pairs')
    if traces[0].outputs != traces[1].outputs:
        raise AssertionError('continuation I/O differs')
    return {'io_writes': len(traces[0].outputs), 'level': level, 'calls': calls, 'instructions': steps, 'unread_dead_stack': len(dead),
            'next_block': po.pages[STATE_PAGE][0], 'handoff_sp': patched.registers[12], 'handoff_pc': patched.registers[24],
            'synchronized_refresh_reads': dict(refresh_reads)}


def continuation_tests(folder):
    folder = Path(folder)
    blocks = tape_blocks(folder / 'Inferno.tzx')
    results = []
    for level in range(7):
        # Every pair loads from the live level-1 state; no independent target-level restore.
        results.append(continuation_case(folder / 'Inferno.z80', blocks, level))
    return {'cases': results, 'scope': 'crafted 7131 invocations to 718C; Na executed, Nb loaded but not executed; canonical bytes/equal R inputs'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--loader-tests', type=Path)
    ap.add_argument('--bootstrap', type=Path)
    ap.add_argument('--continuation-tests', type=Path)
    ap.add_argument('--out', type=Path, default=Path('work/inferno'))
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    if a.continuation_tests:
        result = continuation_tests(a.continuation_tests)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0
    if a.bootstrap:
        result = bootstrap(a.bootstrap, a.out)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(result['boot_checks'].values()))
    if not a.loader_tests:
        ap.error('choose --loader-tests or --bootstrap')
    counts, examples = loader_tests(a.loader_tests)
    result = {'counts': dict(counts), 'examples': examples,
              'scope': 'byte decoder only; no pulse timing, bootstrap or full-game proof'}
    if a.json:
        a.json.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(any(v for k, v in counts.items() if k.endswith('!')))


if __name__ == '__main__':
    raise SystemExit(main())
