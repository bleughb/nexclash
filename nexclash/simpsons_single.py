"""Build the five-level Ocean tape as one NEX. Run with --help for inputs."""
import argparse
import hashlib
import struct
from pathlib import Path

from . import nxc, simpsons, z80tonex

TAPE_MD5 = '8e08c32c3265f6c4a65cf7e5f72b9913'
START_MD5 = '14ee8b0b105fbf8b58bfeaed03e97a13'
TAPE_BANKS = range(25, 46)
HOOK_PAGES = (24, 16, 17, 18, 19)
# Level 1's active pages are saved by multi_install after the boot stub returns.
COLOUR_SOURCES = ((20, 21, 92, 93, 94), tuple(range(34, 40)), tuple(range(40, 44)),
                  tuple(range(44, 50)), (22, 23, 25))
LIVES = ((55778,), (56607,), (55736,), (55649,), (55111, 55649))
LOAD_SITE = 0x82D6
START_SITE = 0x8236
TITLE = 'The Simpsons: Bart vs. the Space Mutants'


def levels(tape):
    """Extract the six CODE header/payload pairs per level of this tape release."""
    if hashlib.md5(tape).hexdigest() != TAPE_MD5:
        raise ValueError('expected the 128K Ocean TAP, MD5 ' + TAPE_MD5)
    blocks = [tape[o + 1:o + n - 1] for o, n in nxc.tape_blocks(tape, nxc.KIND_TAP)]
    return [list(zip(blocks[i:i + 12:2], blocks[i + 1:i + 12:2])) for i in range(8, 68, 12)]


def play_memory(files):
    view = bytearray(65536)
    for header, payload in files[:2]:
        addr = int.from_bytes(header[13:15], 'little')
        view[addr:addr + len(payload)] = payload
    return view


def make_patch(start, tape, painted):
    """Start in level 1. Every reload uses the original TAP payloads, including restarts."""
    if hashlib.md5(start.read_bytes()).hexdigest() != START_MD5:
        raise ValueError('expected the level 1 start snapshot, MD5 ' + START_MD5)
    cmap = simpsons.load_colours(start)
    if painted and not cmap:
        raise ValueError('Enhanced needs ' + simpsons.COLOURS_NAME + ' beside the snapshot')
    first = simpsons.Patch(z80=start, colours=cmap if painted else None)
    sy = first.syms
    hooks = first.prof['hooks']
    pages = {}
    control = bytearray.fromhex(hooks['install']).ljust(8192, b'\0')
    source_at = sy['multi_save_pages'] - 0x4000
    if tuple(control[source_at:source_at + 5]) != COLOUR_SOURCES[0]:
        raise ValueError('initial colour save page mismatch')
    directory = bytearray()
    stream = bytearray()
    for level, files in enumerate(levels(tape), 1):
        for part, (header, payload) in enumerate(files, 1):
            length, addr = struct.unpack_from('<HH', header, 11)
            if len(payload) != length or header[1:11].rstrip() != f'simp-{level}{part}'.encode():
                raise ValueError(f'wrong Ocean block at level {level} part {part}')
            spans = bytearray(header)
            pos = len(stream)
            stream.extend(payload)
            while pos < len(stream):
                page, offset = divmod(pos, 8192)
                count = min(8192 - offset, len(stream) - pos)
                spans.extend(struct.pack('<BHH', 2 * TAPE_BANKS.start + page, offset, count))
                pos += count
            if len(spans) > 32:
                raise ValueError('tape block needs more than three source pages')
            directory.extend(spans.ljust(32, b'\0'))
        pt = simpsons.Patch(mem=play_memory(files), colours=cmap if painted else None)
        if pt.level != level or (level == 1 and pt.sites != first.sites):
            raise ValueError(f'graphics sites differ at level {level}')
        lives = LIVES[level - 1]
        # The second level 5 site is just beyond its block, inherited from level 4.
        if files[3][1][lives[0] - 0xC000] != 1:
            raise ValueError(f'unexpected lives instruction operand at level {level}')
        sources = COLOUR_SOURCES[level - 1]
        if painted and len(pt.planes) != len(sources):
            raise ValueError('colour map exceeds reserved layout')
        image = bytearray(pt.page)
        image[0x1800:0x1A00] = bytes(v for c in pt.palette for v in (c >> 1, c & 1))
        hook_page = HOOK_PAGES[level - 1]
        pages[hook_page] = image
        for i, source in enumerate(sources):
            page = simpsons.CPAGE + i if level == 1 else source
            pages[page] = pt.planes.get(simpsons.CPAGE + i, bytes(8192))
        desc = bytes((hook_page, len(sources), *sources)).ljust(8, b'\0')
        desc += b''.join(struct.pack('<H', addr) + new for addr, _, new in pt.sites)
        desc += struct.pack('<HH', lives[0], lives[-1])
        off = sy['multi_levels'] - 0x4000 + 32 * (level - 1)
        control[off:off + 32] = desc

    if (len(stream) + 16383) // 16384 != len(TAPE_BANKS):
        raise ValueError('tape data exceeds reserved banks')
    for i in range(0, len(stream), 8192):
        pages[2 * TAPE_BANKS.start + i // 8192] = stream[i:i + 8192].ljust(8192, b'\0')
    pages[26], pages[27] = first.work, control
    first.sites += [(0x8191, bytes.fromhex('318081'), b'\xc3' + struct.pack('<H', sy['multi_begin'])),
                    (LOAD_SITE, bytes.fromhex('C36205'), b'\xc3' + struct.pack('<H', sy['multi_read'])),
                    (START_SITE, bytes.fromhex('C32085'), b'\xc3' + struct.pack('<H', sy['multi_finish']))]
    page = pages[24]
    off = sy['multi_read'] - 0x2000
    reader = bytes.fromhex(hooks['reader'])
    page[off:off + len(reader)] = reader
    off = sy['multi_blocks'] - 0x2000
    page[off:off + len(directory)] = directory
    first.page = bytes(page)
    first.altrom = first.altrom0 = (0x2000, 0x2000 + off + len(directory))
    first.setup_call = sy['multi_setup']
    first.stub_extra = first.stub_extra.ljust(first.setup_call - 0xD000, b'\0') + bytes.fromhex(hooks['multisetup'])
    first.extra_banks = {b: bytes(pages.get(2*b, bytes(8192))) + bytes(pages.get(2*b+1, bytes(8192)))
                         for b in {p // 2 for p in pages}}
    return first


def build(start, tape, out, package=False, proof=None):
    out.mkdir(parents=True, exist_ok=True)
    raw = tape.read_bytes()
    for painted, name in ((False, 'simpsons_sprites'), (True, 'simpsons_enhanced')):
        patch = make_patch(start, raw, painted)
        path = out / (name + '.nex')
        z80tonex.convert(str(start), str(path), patch=patch, quiet=True)
        path.write_bytes(z80tonex.automap_off(path.read_bytes()))
        bad = simpsons.boot_check(path, start, patch)
        if bad:
            raise ValueError(f'{name} boot mismatch: {bad[:3]}')
        print(name, hashlib.md5(path.read_bytes()).hexdigest(), 'both boots passed', flush=True)
    if package:
        summary = {}
        patch, stats = nxc.make(tape, out / 'simpsons_sprites.nex', {'file': tape.name, 'title': TITLE},
                         {'publisher': 'Ocean, 1991', 'version': '1.1', 'patch_by': 'Jon Attree',
                          'colours_by': 'Jon Attree', 'build': 'simpsons_sprites',
                          'build_screen': str(nxc.tape_blocks(raw, nxc.KIND_TAP)[5][0] + 1),
                          'notes': 'All five levels load from memory. Enhanced paints the figures. Test copy.'},
                         proof=proof, start=start, colours={'Enhanced': out / 'simpsons_enhanced.nex'},
                         tape_banks=TAPE_BANKS, residual_max=10240, tape_summary=summary,
                         trainer_blocks=[nxc.trn1('Infinite lives', [(3, LIVES[0][0] - 0xC000, 0)])])
        (out / 'Simpsons 1.1.nxc').write_bytes(patch)
        print('Ocean TAP', summary, stats, flush=True)


def auto(a, z80, out, say):
    from . import simpsons_single_verify
    if len(a.tape) != 1:
        raise ValueError('expected one Ocean 128K tape')
    start, tape, folder = Path(z80), Path(a.tape[0]), Path(out)
    build(start, tape, folder, package=not getattr(a, 'no_nxc', False))
    a.no_nxc = True  # the tape package, when requested, was built above
    say('Boot      : simulated with and without the NEXLOAD printer buffer, both builds OK')
    if a.rzx:
        simpsons_single_verify.verify(start, tape, folder, a.rzx, getattr(a, 'quick', None), say)
    say('Result    : PASSED')
    return True


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('start', type=Path, help='simpsons_l1.z80, beside simpsons_colours.json')
    ap.add_argument('tape', type=Path, help='the Ocean 128K TAP')
    ap.add_argument('output', type=Path)
    ap.add_argument('--nxc', action='store_true')
    args = ap.parse_args()
    build(args.start, args.tape, args.output, args.nxc)
