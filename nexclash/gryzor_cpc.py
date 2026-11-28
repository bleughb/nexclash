"""Build Gryzor's optional CPC figure set from the player's original DSK.

python -m nexclash.gryzor_cpc DEFAULT.nex Gryzor.dsk ENHANCED.nex
The default input is the Gryzor 1.2 outline build, including trainer variants.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from hashlib import md5, sha256
import json
from pathlib import Path
from struct import pack, unpack_from

from . import gryzor, recolour

RECIPE = Path(gryzor._profile_path()).with_name('gryzor_cpc_copy.json')
DISK_NAME = 'Gryzor_1987_Ocean_Software.dsk'
DESCRIPTORS = 0x4cc7
START, END = 0x483a, 0x74a5


def copy_bank(disk, recipe):
    bank = bytearray(16384)
    pos = START - 0x4000
    for run in recipe['runs']:
        i, n = run['offset'], run['length']
        data = disk[i:i + n]
        if (run['bank'] != 21 or run['bank_offset'] != pos or n <= 0 or
                i < 0 or len(data) != n or pos + n > len(bank) or md5(data).hexdigest() != run['md5']):
            raise ValueError(f'Invalid CPC copy run at disk offset {i}')
        bank[pos:pos + n] = data
        pos += n
    if pos != END - 0x4000 or sha256(disk).hexdigest() != recipe['sha256']:
        raise ValueError('Expected the Ocean Gryzor CPC disk named in the copy recipe')
    return bytes(bank)


@dataclass(frozen=True)
class Pose:
    lists: tuple
    exposure: int = 0


@dataclass(frozen=True)
class Draw:
    pose: Pose
    x: int                      # CPC anchor relative to the Spectrum plot, physical pixels
    y: int
    mirror: bool


def mapping():
    draws = {}

    def put(image, shape, poses, x, y, mirror=False, exposure=0):
        if isinstance(poses, int):
            poses = (poses,)
        key = (image, shape)
        if key in draws:
            raise ValueError(f'Duplicate draw {key}')
        draws[key] = Draw(Pose(poses, exposure), x, y, mirror)

    # At the paired hooks the game places the right-facing legs one column
    # left of the torso. Both CPC lists use the same hip origin.
    legs = (0x484c, 0x483b, 0x4842, 0x4850, 0x4861, 0x4850, 0x4857, 0x483b)
    uppers = (0x4865, 0x4865, 0x4869, 0x4865, 0x486d, 0x486d, 0x4871, 0x486d)
    for mirror in (False, True):
        for phase, leg in enumerate(legs):
            key = phase + 8 * mirror
            hip = 15 if leg in (0x4842, 0x4850, 0x4861) else 16
            origin = 18 if mirror else 6
            sign = -1 if mirror else 1
            for shift_key, shift in ((0, 0), (16, 2), (48, 4)):
                put(0x100 + key + shift_key, 1, leg, origin + (0 if mirror else 8) + sign*shift,
                    hip - 16, mirror)
            for group, upper in enumerate((uppers[phase], 0x4879, 0x488f, 0x4896), 2):
                put(group * 256 + key, 1, upper, origin + sign*(0, 0, 2, 4)[group-2], hip, mirror)
        for phase, (pose, hip) in enumerate(((0x48b4, 11), (0x48bb, 12), (0x48c2, 15),
                                               (0x48c9, 18), (0x48dd, 16))):
            put(0x600 + phase + 8 * mirror, 1, pose, 12, hip, mirror)

    for image, upper, x, mirror in (
            (0xcda0, 0x4879, 6, False), (0xcb60, 0x4879, 19, True),
            (0xcf20, 0x4887, 8, False), (0xcaa0, 0x4887, 16, True),
            (0xce60, 0x488f, 8, False), (0xcc20, 0x488f, 16, True),
            (0xcce0, 0x4896, 16, True)):
        put(image, gryzor.shape_of(3, 16), (upper, 0x4875), x, 15, mirror)
    put(0xdc00, gryzor.shape_of(3, 16), 0x48d0, 10, 18)
    for image, x, mirror in ((0xda40, 16, False), (0xc960, 24, True)):
        put(image, gryzor.shape_of(5, 8), 0x48a0, x, 10, mirror)

    runners = (0x4a69, 0x4a76, 0x4a83, 0x4a8d)
    for i in range(4):
        shape = gryzor.shape_of(4, 16)
        put(0x6ac8 + 256*i, shape, runners[i], 13+i, 15)
        put(0xe860 + 256*i, shape, runners[3-i], 16+i, 15, True)
        put(0xec60 + 256*i, shape, 0x4c83, 16+2*i, 6)
        put(0xf060 + 256*i, shape, 0x4c76, 18+2*i, 13)
        put(0xf460 + 256*i, shape, 0x4c66, 17+2*i, 13)
        for rows in range(2, 8):
            # The Spectrum exposes just the top of the crouching gunner.
            # CPC $3423 raises piece $E4 into placeholder $A1 in four steps.
            stage = (0, 1, 1, 2, 2, 3)[rows-2]
            pose = (0x4c90, 0x4c90, 0x4c94, 0x4c9b)[stage]
            height = (1, 5, 9, 13)[stage]
            put(0xf060 + 256*i, gryzor.shape_of(4, rows), pose, 18+2*i,
                2*rows-7, exposure=height)
    for image, y in ((0x6fc8, 17), (0x70c8, 14)):
        put(image, gryzor.shape_of(4, 16), 0x4a9d, 15, y)
    for i in range(8):
        put(0xb8c1 + 16*i, gryzor.shape_of(2, 2), 0x4b47, 3+i, 2)
    for i, (pose, x, y) in enumerate(((0x4b6b, 16, 7), (0x4b6f, 13, 9),
                                       (0x4b73, 13, 9), (0x4b77, 12, 10))):
        put(0x74c8 + 144*i, gryzor.shape_of(3, 12), pose, x, y)
    wall = (0x4acf, 0x4ad6, 0x4add, 0x4ae4, 0x4aeb,
            0x4aeb, 0x4ae4, 0x4add, 0x4ad6, 0x4acf)
    for phase, pose in enumerate(wall):
        put(0x700 + phase, 1, pose, 12, 12)
    put(0x70a, 1, 0x4af3, 12, 11)
    return draws


def bounds(bank, pose):
    """Only inspect list and descriptor geometry. The Next reads every pixel."""
    rectangles = []
    for address in pose.lists:
        i = address - 0x4000
        while bank[i] != 128:
            x, dy, piece = unpack_from('<bbB', bank, i)
            if piece in (0xa1, 0x9e) and pose.exposure:
                master = 0xe4 if piece == 0xa1 else 0xc8
                w = bank[DESCRIPTORS - 0x4000 + 4*master]
                h = pose.exposure
            else:
                w, h = unpack_from('BB', bank, DESCRIPTORS - 0x4000 + 4*piece)
            rectangles.append((x, 1-dy-h, x+w, 1-dy))
            i += 3
    left = min(r[0] for r in rectangles)
    top = min(r[1] for r in rectangles)
    width = max(r[2] for r in rectangles) - left
    lines = max(r[3] for r in rectangles) - top
    if not (-16 <= left and left+width <= 16 and -32 <= top and top+lines <= 32):
        raise ValueError('Pose exceeds CPC boot canvas')
    return left, top, (width+7)//8, lines


def tables(bank, draws, index_address):
    templates = bytearray()
    atlas = {}
    pattern = 0
    buckets = defaultdict(bytearray)
    for (image, shape), draw in draws.items():
        pose = draw.pose
        if pose not in atlas:
            left, top, cols, lines = bounds(bank, pose)
            rows = (lines+15)//16
            atlas[pose] = pattern, left, top, cols, rows
            templates.extend(pack('<HHbbBBB', pose.lists[0], next(iter(pose.lists[1:]), 0),
                                  left, top, cols, lines, pose.exposure))
            pattern += cols*rows
        first, left, top, cols, rows = atlas[pose]
        dx = -4*left-32 if draw.mirror else 4*left
        buckets[image >> 8].extend(pack('<BBBBBbbB', shape, image & 255, first, cols, rows,
                                        draw.x+dx, draw.y+top, 8 if draw.mirror else 0))
    if pattern > 128:
        raise ValueError(f'{pattern} CPC patterns exceed the Next sprite RAM')
    data = bytearray(513)
    for hi in range(256):
        address = index_address + 512
        if hi in buckets:
            address = index_address + len(data)
            data.extend(buckets[hi] + b'\0')
        data[2*hi:2*hi+2] = pack('<H', address)
    return templates + b'\0\0', data


def enhance(nex, disk):
    banks = recolour.banks(nex)
    # All published trainer POKEs live in game banks. Guard the actual hook
    # and boot donor, including its assembler layout, before changing either.
    for b, digest in ((10, '824732c0ad45a2846f25f727037ef9d3'), (12, '4718b4b7dc8ec25d659ddcdc03a8e8bb')):
        if md5(banks[b]).hexdigest() != digest:
            raise ValueError('Expected the Gryzor 1.2 default sprite NEX')
    if 21 in banks:
        raise ValueError('CPC source bank 21 is already occupied')
    source = copy_bank(disk, json.loads(RECIPE.read_text()))
    hooks = gryzor.load_profile()['hooks']
    syms = {k:int(v, 16) for k,v in hooks['syms'].items()}
    boot, index = tables(source, mapping(), syms['cpc_index'])
    boot = bytes.fromhex(hooks['cpcboot']) + boot
    draw = bytes.fromhex(hooks['cpcdraw']) + index
    gate = bytes.fromhex(hooks['cpcgate'])
    if len(boot) > 0xe00 or len(draw) > 8192:
        raise ValueError('CPC code or mapping table exceeds its bank allocation')
    setup = bytearray(banks[10])
    setup[4096:4096+len(boot)] = boot
    code = bytearray(banks[12])
    start = syms['cpc_redirect'] - 0x2000
    code[start:start+len(gate)] = gate
    tick = bytes.fromhex(hooks['cpctick'])
    at = syms['cpc_tick'] - 0x2000
    code[at:at+len(tick)] = tick
    call = syms['b_tick.hide_call'] - 0x2000
    code[call+1:call+3] = pack('<H', syms['cpc_tick'])
    code[8192:8192+len(draw)] = draw
    from . import nxc
    header = nxc.extended_header(nex[:512], {'added': [21]})
    banks.update({10: setup, 12: code, 21: source})
    return bytes(header) + b''.join(banks[b] for b in nxc.ORDER if b in banks)


def local_menu(default, enhanced, donor, snapshot):
    """Build the menu locally. Its SET3 carrier holds the raw DSK bank once."""
    from . import nxc
    game = snapshot.read_bytes()
    if nxc.apply(donor, game=game) != default.read_bytes():
        raise ValueError('The supplied patch and default NEX do not match')
    original = nxc.targets(donor)[0]
    target = {k: original[k] for k in ('file', 'title', 'zxdb_entry') if k in original}
    info = dict(title='Gryzor', publisher='Ocean, 1987', colours_label='Enhanced colours',
                notes='Jungle figures from the Amstrad CPC disk. Enhanced is off by default.')
    for key in ('patch_by', 'credit'):
        value = nxc.inf1_value(donor, key)
        if value:
            info[key] = value.decode('utf-8')
    blocks = nxc.blocks(donor)[1]
    patch, _ = nxc.make(str(snapshot), str(default), target, info, colours={'Enhanced': str(enhanced)},
                        trainer_blocks=[data for tag, data in blocks if tag == b'TRN1'])
    return patch, nxc.apply_menu(patch, game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('default', 'disk', 'output'):
        parser.add_argument(arg, type=Path)
    parser.add_argument('--menu', type=Path, help='also build a local menu NEX, Enhanced off by default')
    parser.add_argument('--patch', type=Path, help="published Gryzor patch with the owner's trainers")
    parser.add_argument('--snapshot', type=Path, help='original 48K Gryzor snapshot for the menu')
    parser.add_argument('--menu-stub', type=Path, help='path to the NXC firmware nxcstub.bin')
    args = parser.parse_args()
    if any((args.menu, args.patch, args.snapshot)) and not all((args.menu, args.patch, args.snapshot)):
        parser.error('--menu, --patch and --snapshot are used together')
    args.output.write_bytes(enhance(args.default.read_bytes(), args.disk.read_bytes()))
    if args.menu:
        from . import nxc
        if args.menu_stub:
            nxc.STUB = str(args.menu_stub)
        _, menu = local_menu(args.default, args.output, args.patch.read_bytes(), args.snapshot)
        args.menu.write_bytes(menu)


if __name__ == '__main__':
    main()
