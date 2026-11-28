"""Exercise the Gryzor CPC tables, their source and the pixel oracle on a built NEX.

python -m nexclash.gryzor_cpc_units OWNER.dsk DEFAULT.nex ENHANCED.nex c1.rzx
"""
import argparse
import ast
import collections
import json
from pathlib import Path
from struct import unpack_from
from unittest.mock import patch as replace

from .gryzor_cpc_verify import FigureCheck, boot, cpc, decode, g, recolour


def converted_literals(source, tiles):
    """Look for boot-generated nonempty tiles in literal bytes, hex strings and integer arrays."""
    hits = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            try:
                data = bytes.fromhex(node.value) if isinstance(node.value, str) else node.value
            except ValueError:
                continue
        elif isinstance(node, (ast.Tuple, ast.List)) and all(
                isinstance(a, ast.Constant) and type(a.value) is int and 0 <= a.value <= 255 for a in node.elts):
            data = bytes(a.value for a in node.elts)
        else:
            continue
        hits += sum(tile in data for tile in tiles)
    return hits


def audit(disk, default, nex, check):
    recipe = json.loads(cpc.RECIPE.read_text())
    bank = cpc.copy_bank(disk, recipe)
    assert bank == check.banks[21]
    copied = sum(r['length'] for r in recipe['runs'])
    for run in recipe['runs']:
        corrupt = bytearray(disk)
        corrupt[run['offset']] ^= 1
        try:
            cpc.copy_bank(corrupt, recipe)
        except ValueError as exc:
            assert f"offset {run['offset']}" in str(exc)
        else:
            raise AssertionError('Corrupt disk run accepted')
    assert cpc.enhance(default, disk) == nex
    # Change every Mode 0 source byte after authenticating the original. If
    # host code converted or cached any of these, another output byte differs.
    scrambled = bytearray(bank)
    for offset in range(0x1073, 0x34a5):
        scrambled[offset] ^= 0xff
    with replace.object(cpc, 'copy_bank', return_value=bytes(scrambled)):
        mutant = cpc.enhance(default, disk)
    changes = [i for i,(a,b) in enumerate(zip(nex, mutant)) if a != b]
    at = recolour.nex_offsets(nex)[21]
    assert changes == list(range(at+0x1073, at+0x34a5))
    print(f'{copied} recipe bytes in {len(recipe["runs"])} runs; 4/4 corrupt runs rejected; '
          f'{len(changes)} source pixel bytes perturbed, 0 dependent bytes outside source')

    # Search ALL starting offsets whose full 16-byte window is outside the recipe.
    words = {disk[i:i+16] for i in range(len(disk)-15)}
    first, end = at+0x83a, at+0x34a5
    offsets = [i for lo, hi in ((0, first), (end, len(nex)))
               for i in range(lo, hi-15) if nex[i:i+16] in words]
    # Compare by bank identity because the raw bank has shifted later file offsets.
    # The new bank starts zeroed. Treat that padding as newly added.
    template = bytearray(len(nex))
    template[:512] = default[:512]
    for b, source in recolour.banks(default).items():
        off = recolour.nex_offsets(nex)[b]
        template[off:off+16384] = source
    nonbaseline = [i for i in offsets if nex[i:i+16] != template[i:i+16]]
    padding = sum(at <= i and i+16 <= at+16384 for i in offsets)
    print(f'{len(offsets)} coincident 16-byte starts outside recipe; {padding} in bank 21 zero padding; '
          f'{len(nonbaseline)} differ from the aligned zero-extended default')
    for i in nonbaseline:
        print(f'Changed window at NEX {i} matches disk {disk.find(nex[i:i+16])}: {nex[i:i+16].hex()}')
    i = offsets[0]
    print(f'Example at NEX {i}, disk {disk.find(nex[i:i+16])}: {nex[i:i+16].hex()}')
    tiles = {check.patterns[i:i+128] for i in range(0,check.uploaded,128)} - {bytes(128)}
    outside = (nex[:first], nex[end:])
    assert not any(tile in region for tile in tiles for region in outside)
    source = Path(cpc.__file__).read_text()
    assert converted_literals(source, tiles) == 0
    tile = max(tiles, key=lambda t: sum(b != 0 for b in t))
    assert converted_literals(source + '\nPRECONVERTED = bytes.fromhex(' + repr(tile.hex()) + ')', tiles) == 1
    print(f'{len(tiles)} distinct nonempty tile literals checked; 0 in builder or NEX outside the source, planted tile rejected')


def anchors(check, memory):
    # The original loops write a visible pixel if it sets a black canvas bit
    # or clears a white one. This measures Spectrum feet and barrel endpoints
    # independently of the placement in the mapping table.
    cases = [(key, key[0], {3:40709, 4:40370, 5:40539}[key[1] >> 5], key[1] & 31)
             for key in check.draws if key[0] >= 0xc000 or 0x6ac8 <= key[0] <= 0x70c8]
    for key in check.draws:
        image, _ = key
        if image >> 8 == 1:
            cases.append((key, 0xd0a0+128*(image & 7), 40370, 8))
        if image >> 8 == 6:
            phase = min(3, image & 7)
            cases.append((key, 0xd800+144*phase, 40709, 12))
    barrels = 0
    for key, image, site, rows in cases:
        a,b = g.truth(memory, site, image, 0x4000+g._scr(64,12), rows)
        original = {(x,y) for y in range(2*rows) for x in range(8*g.ENTRIES[site][3])
                    if (a[g._scr(64+y,12+x//8)] | ~b[g._scr(64+y,12+x//8)]) & (128 >> (x%8))}
        shown = check.expected(check.draws[key])
        assert max(y for x,y in shown) == max(y for x,y in original), key
        if image in (0xcda0, 0xcb60, 0xda40, 0xc960):
            edge = min if image in (0xcb60, 0xc960) else max
            tip = edge(x for x,y in original)
            assert edge(x for x,y in shown) == tip
            assert any((tip,y) in original and (tip,y) in shown for y in range(2*rows))
            barrels += 1
        if image in (0xcf20, 0xcaa0):
            assert min(y for x,y in shown) == -4 and min(y for x,y in original) == 0
            assert {x for x,y in shown if y == -4} <= {x for x,y in original if y == 0}
    print(f'{len(cases)} floor-line comparisons matched; {barrels} level/prone barrel tips coincide; '
          'both overhead tips are 4 lines higher, in the original barrel columns')


def plot_units(check, recording):
    m = bytearray(g.RZ_first_snapshot(str(recording)))
    anchors(check, m)
    patch = g.GryzorPatch()
    patch.pl = b''
    patch.page = check.banks[12][:8192]
    table = bytearray(check.banks[12][8192:])
    index = patch.syms['cpc_index'] - 0x6000
    def record(image, shape):
        at = unpack_from('<H', table, index+2*(image >> 8))[0] - 0x6000
        while table[at]:
            if table[at:at+2] == bytes((shape, image & 255)):
                return at
            at += 8
        raise AssertionError((image, shape))
    errors = []
    def plot(site, image, rows):
        patch.store = {25: bytes(table)}
        eng = g.Engine(patch)
        check.start(eng)
        m[g.ROWS] = rows
        regs = g._regs(site, image, 0x4000+g._scr(72, 12), rows)
        sym, _, end, _, _ = g.ENTRIES[site]
        _, _, _, done, _ = eng.hook(m.__getitem__, regs, patch.syms[sym], end)
        assert done
        check.plot(eng, site, regs, m, 0, collections.Counter(), lambda *msg: errors.append(msg))

    cases = 0
    for direction in range(1, 7):
        for stride in range(8):
            for firing in (0, 1):
                m[0xb405], m[0xb400], m[0xb406], m[0xb3f5] = 1, direction, stride, firing
                for site, gfx in ((40370, 0xd120), (40709, 0xd4a0)):
                    plot(site, gfx, 8)
                    cases += 1
    m[0xb405] = 0
    for image, shape in check.draws:
        if image < 0x800:
            continue
        width, rows = shape >> 5, shape & 31
        plot({2:37662, 3:40709, 4:40370, 5:40539}[width], image, rows)
        cases += 1
    for facing in (0xcb, 0xcd):
        for dying in (0, 1):
            for frame in (0xd800, 0xd890, 0xd920, 0xd9b0):
                m[0xb405], m[0xb430], m[0xb3e1] = 3, facing, dying
                plot(40709, frame, 12)
                cases += 1
    assert not errors, errors[:2]
    m[0xb405] = 0
    at = record(0xcda0, g.shape_of(3,16))
    other = record(0xcf20, g.shape_of(3,16))
    for field, bad in ((2, table[other+2]), (6, table[at+6]+1)):
        old = table[at+field]
        table[at+field] = bad
        plot(40709, 0xcda0, 16)
        table[at+field] = old
        assert len(errors) == 1 and errors.pop()[0] == 'CPC pose pixels or position'
    print(f'{cases} real plot hook units passed; wrong pose and one-line foot shift both rejected')

    # The second CPC mechanism has no distinct Spectrum trigger. Run its five
    # partial descriptors through a private copy of the same boot program.
    extra = { (i,1): cpc.Draw(cpc.Pose((addr,), height), 0, 0, False)
              for i,(addr,height) in enumerate(((0x4c09,4),(0x4c09,8),(0x4c09,12),(0x4c10,16),(0x4c1a,20))) }
    raw = check.banks[21]
    templates, _ = cpc.tables(raw, extra, 0)
    setup = bytearray(check.banks[10])
    start = 4096 + len(bytes.fromhex(g.load_profile()['hooks']['cpcboot']))
    setup[start:start+len(templates)] = templates
    patterns, _ = boot({**check.banks,10:setup})
    tile = 0
    for draw in extra.values():
        left, top, cols, height = cpc.bounds(raw, draw.pose)
        expected = decode(check.section, draw.pose)
        actual = {}
        for row in range((height+15)//16):
            for col in range(cols):
                for pos in range(256):
                    byte = patterns[tile*128+pos//2]
                    pen = byte & 15 if pos & 1 else byte >> 4
                    if pen:
                        x,y = left*4+col*32+pos%16*2, top+row*16+pos//16
                        actual[x,y] = actual[x+1,y] = pen
                tile += 1
        assert expected == actual
    print('5/5 second CPC emplacement heights matched assembled boot pixels')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('disk','default','enhanced','recording'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    disk, default, nex = (p.read_bytes() for p in (args.disk, args.default, args.enhanced))
    check = FigureCheck(disk, nex)
    audit(disk, default, nex, check)
    plot_units(check, args.recording)
