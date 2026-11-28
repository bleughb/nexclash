"""Enhanced Dynamite Dan. Each room owns an 8K page, mapped only inside the hooks.
Page header: tile count, first IY low byte, group * 8 per record. At +0x100,
four groups x eight 16-byte phase descriptors. At +0x400, unshifted RGB332 tiles.
The ULA copies and shifts these same source frames in D677 / D815 at room entry.
"""
from . import dynamite_dan as dan

MENU = 48
FIRST_PAGE = 32
FIRST_PATTERN = 27
FIRST_SLOT = 11
MAX_RECORDS = 10
SITES = {0xC837: ('cdafd4', 'e_delay', 'delay'),
         0xE54D: ('fd7e00', 'e_room', 'load'),
         0xE96B: ('c5fdcb0476', 'e_enemy', 'enemy'),
         0xD2E7: ('fdcb04f6', 'e_erase', 'erase')}


def word(peek, at):
    return peek(at) | peek(at + 1) << 8


def room_info(peek, room):
    base = 0xCA3D if room == MENU else word(peek, 0x69E6 + room * 12 + 7)
    counts = [peek(base + i) for i in (4, 5)]
    return base + 6, [(peek(base + i), counts[i // 2] >> 4 if i % 2 == 0 else counts[i // 2] & 7)
                      for i in range(4)]


def geometry(peek, kind):
    a = word(peek, 0xAE60 + 2 * kind)
    return a + 1, peek(a) & 3, (peek(a) >> 2) & 3


def frames(peek):
    seen = set()
    for room in range(MENU + 1):
        _, groups = room_info(peek, room)
        for i, (kind, count) in enumerate(groups):
            if count:
                seen.update((kind, f) for f in range(2 if i < 2 else 4))
    return sorted(seen)


def pixels(peek, kind, frame):
    start, width, height = geometry(peek, kind)
    start += frame * width * height * 8
    for y in range(height * 8):
        for x in range(width * 8):
            addr = start + y * width + x // 8
            byte = peek(addr)
            bit = x % 8
            yield x, y, '%04X' % addr, bit, byte, bool(byte & (128 >> bit))


def tiles(peek, cmap, kind, frame):
    _, w, h = geometry(peek, kind)
    nx, ny = (w + 1) // 2, (h + 1) // 2
    images = [bytearray([dan.TRANSP]) * 256 for _ in range(nx * ny)]
    for x, y, key, bit, byte, ink in pixels(peek, kind, frame):
        value = dan.colour_of(cmap, key, bit, byte)
        if value != 'T' and (value or ink):
            images[y // 16 * nx + x // 16][y % 16 * 16 + x % 16] = dan.PALETTE[value or dan.DAN_DEFAULT]
    return images


def room_page(peek, cmap, room, cache):
    first, groups = room_info(peek, room)
    page = bytearray(8192)
    page[1] = first & 255
    tile_count = records = 0
    for group, (kind, count) in enumerate(groups):
        if not count:
            continue
        if records + count > MAX_RECORDS:
            raise ValueError('too many enemy records in room %d' % room)
        page[2 + records:2 + records + count] = bytes([8 * group]) * count
        records += count
        _, w, h = geometry(peek, kind)
        nx, ny = (w + 1) // 2, (h + 1) // 2
        horizontal = group >= 2
        first_pat = FIRST_PATTERN + tile_count
        for frame in range(4 if horizontal else 2):
            if (kind, frame) not in cache:
                cache[kind, frame] = tiles(peek, cmap, kind, frame)
            for tile in cache[kind, frame]:
                off = 0x400 + tile_count * 256
                if off + 256 > len(page) or FIRST_PATTERN + tile_count >= 64:
                    raise ValueError('enemy pattern budget exceeded in room %d' % room)
                page[off:off + 256] = tile
                tile_count += 1
        for phase in range(8):
            frame = phase % (4 if horizontal else 2)
            mirror = horizontal and phase >= 4
            shift = (frame + 1) * 2 if horizontal else phase * 2
            desc = bytearray([nx * ny, 8 if mirror else 0])
            for row in range(ny):
                for col in range(nx):
                    x = col * 16 + (shift if horizontal else 0)
                    if mirror:
                        x = (w + 1) * 8 - x - 16
                    y = row * 16 + (0 if horizontal else shift)
                    pat = first_pat + frame * nx * ny + row * nx + col
                    desc.extend((32 + x, 32 + y, 0x80 | pat))
            off = 0x100 + 16 * (group * 8 + phase)
            page[off:off + len(desc)] = desc
    page[12] = 32 * ((records * 20 + 16) // 32)
    page[0] = tile_count
    return bytes(page)


def banks(peek, cmap):
    cache = {}
    pages = [room_page(peek, cmap, room, cache) for room in range(MENU + 1)] + [bytes(8192)]
    return {(FIRST_PAGE + i) // 2: pages[i] + pages[i + 1] for i in range(0, len(pages), 2)}


def composites(peek):
    comps = []
    for kind, frame in frames(peek):
        _, w, h = geometry(peek, kind)
        entries, px = {}, []
        for x, y, key, bit, byte, ink in pixels(peek, kind, frame):
            entries[key] = [byte, 'g']
            px.append((x, y, key, bit, int(ink), dan.DAN_DEFAULT if ink else 0))
        part = dict(id='enemy:%02d:%d' % (kind, frame), size=1, w=w*8, h=h*8, x=0, y=0, mir=0,
                    pixels=px, entries=entries, dx=0, dy=0, dmir=0, vmir=0, group=1 + kind // 4)
        comps.append(dict(count=1, group=part['group'], parts=[part]))
    return comps


def check_picture(ns, first, x, y, w, h, get, edits):
    """Compare with the bytes actually left by E96B, including all blank padding.
    A tile wrongly positioned outside the plot rectangle is also a failure."""
    drawn = {}
    for yy in range(y, y+h):
        screen = 0x4000 + (yy & 0xc0)*32 + (yy & 7)*256 + (yy & 0x38)*4
        for xx in range(x, x+w, 8):
            byte = get(screen + xx//8)
            for k in range(8):
                if byte & (128 >> k):
                    drawn[xx+k, yy] = dan.PALETTE[dan.DAN_DEFAULT]
    for (dx, dy), (colour, ink) in edits.items():
        pos = (x+dx, y+dy)
        if ink != (pos in drawn):
            return 1, len(drawn)
        if colour is None:
            drawn.pop(pos, None)
        else:
            drawn[pos] = colour
    sprite = ns.pixels(*range(first, first+4))
    return (0 if drawn == sprite else len(drawn.items() ^ sprite.items())), len(drawn)


def frame_paint(peek, cmap, kind, group, phase):
    """Project source-pixel edits into the ULA plot box, independently of tile
    allocation, sprite mirroring, pattern numbers and the bytes uploaded."""
    horizontal = group >= 2
    frame = phase % (4 if horizontal else 2)
    _, w, _ = geometry(peek, kind)
    edits = {}
    for x, y, key, bit, byte, ink in pixels(peek, kind, frame):
        if horizontal:
            x += (frame+1)*2
            if phase >= 4:
                x = (w+1)*8 - 1 - x
        else:
            y += phase*2
        value = dan.colour_of(cmap, key, bit, byte)
        if value is not None:
            edits[x, y] = (None if value == 'T' else dan.PALETTE[value], ink)
    return edits


def unit_tests(patch, state):
    """Prepare the original game's four shift buffers in every room, then run
    its actual position/phase selection and plotter. Exercise plots at both
    screen edges, suppressed plots, erase-on-contact and both delay lengths."""
    import collections
    import copy
    from skoolkit.simulator import Simulator
    counts = collections.Counter()
    Sim = dan._rw()
    alt = dan._alt(patch)
    original = Simulator(list(state[3]))
    mem, regs = original.memory, original.registers
    ns = dan.NextState(patch.pats, patch.extra_banks)

    def start(pc, iy):
        regs[24], regs[12] = pc, 0xF800
        regs[10], regs[11] = divmod(iy, 256)
        mem[0xF800:0xF802] = [0, 0xF9]

    def run_to(stop):
        if not dan._run(original, lambda r: r[24] == stop):
            raise ValueError('original enemy routine did not reach %04X' % stop)

    def compare(kind, site, target=patch, image=alt):
        errs, _ = dan.event(target, kind, site, mem.__getitem__, regs, ns, image, Sim)
        return errs

    # Defeat the actual hide instruction. Use the broken hook with live attributes.
    broken = copy.copy(patch)
    page = bytearray(patch.page)
    pos = page.index(bytes.fromhex('ed913800'), patch.syms['e_erase'] - 0x2000)
    page[pos+3] = 128
    broken.page = bytes(page)
    broken_alt = dan._alt(broken)
    wrong_frame = copy.copy(patch)
    page = bytearray(patch.page)
    pos = page.index(bytes.fromhex('fd7e04e607'), patch.syms['e_enemy'] - 0x2000)
    page[pos+4] = 0   # AND 0 selects phase zero for every animation frame
    wrong_frame.page = bytes(page)
    wrong_alt = dan._alt(wrong_frame)
    rejected_groups = set()
    for room in range(MENU+1):
        mem[0xCFCA] = room
        first, groups = room_info(mem.__getitem__, room)
        start(0xE54D, first-6)
        if compare('load', 0xE54D):
            raise ValueError('room %d upload failed' % room)
        counts['room uploads'] += 1
        run_to(0xF900)
        record = first
        for group, (kind, count) in enumerate(groups):
            header = (0xDED8, 0xDFCA, 0xE0BC, 0xE2FE)[group]
            horiz = group >= 2
            params = 0xD72E if horiz else 0xD6BB
            mem[params:params+4] = [mem[header], mem[header+1], (header+2)&255, (header+2)>>8]
            for idx in range(count):
                slot = FIRST_SLOT + (record-first)//8*4
                for phase in range(8 if horiz else 5):
                    x = (32-mem[header+1]) if phase & 1 else 0
                    y = 18 - mem[header] if phase & 2 else 0
                    flags = phase | (128 if phase & 2 else 0)
                    mem[record:record+2] = [y,x]
                    mem[record+4] = flags
                    start(0xD7B7 if horiz else 0xD7E7, record)
                    regs[4:6] = [x,flags] if horiz else [flags,y]
                    run_to(0xE96B)
                    entry_regs = list(regs)
                    errs = compare('enemy', 0xE96B)
                    run_to(0xF900)
                    edits = frame_paint(mem.__getitem__, patch.colours, kind, group, phase)
                    mismatch, npx = check_picture(ns, slot, x*8, y*8, mem[header+1]*8, mem[header]*8,
                                                  mem.__getitem__, edits)
                    if mismatch or errs:
                        raise ValueError('room %d group %d phase %d: %d pixels, %s' % (room,group,phase,mismatch,errs))
                    if phase and group not in rejected_groups:
                        regs[:] = entry_regs
                        compare('enemy', 0xE96B, wrong_frame, wrong_alt)
                        wrong, _ = check_picture(ns, slot, x*8, y*8, mem[header+1]*8, mem[header]*8,
                                                 mem.__getitem__, edits)
                        if wrong:
                            rejected_groups.add(group)
                        compare('enemy', 0xE96B)
                    counts['plotted frames'] += 1
                    counts['painted pixels'] += npx
                start(0xD2E7, record)
                if not compare('erase', 0xD2E7, broken, broken_alt):
                    raise ValueError('missed stale sprite after erase')
                counts['stale erase detected'] += 1
                if compare('erase', 0xD2E7):
                    raise ValueError('erase failed')
                counts['erase cases'] += 1
                record += 8
    if rejected_groups != set(range(4)):
        raise ValueError('missed wrong frame in groups %s' % (set(range(4)) - rejected_groups))
    counts['wrong-frame tables detected'] = len(rejected_groups)
    for cheat in (False,True):
        mem[0xE592] = 0xC9 if cheat else 0xDD
        for bc in (1023,1024):
            start(0xC837, 0)
            regs[2:4] = divmod(bc,256)
            if compare('delay', 0xC837):
                raise ValueError('tick delay changed registers or live RAM')
            counts['tick delay cases'] += 1
    return dict(counts)
