"""Inferno stage 2: bank loader, original-image model and original-state-preserving capture.

Unregistered: sprite/Layer 2 rendering, recolour and continuous startup installation remain open.
--capture-check replays the original RZX and differentially runs the assembled capture hooks;
--pulse-tests uses unmodified ROM/TZX pulse timings, without byte shortcuts or accelerators.
Diagnostic NEX builds enable no replacement display layers and are not release candidates.
"""
import argparse
from collections import Counter
from functools import reduce, lru_cache
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



def actor_tiles(memory, registers):
    """Whole C100 image, before viewport clipping; original two-byte pointer wraps in C1xx."""
    ix = registers[8] * 256 + registers[9]
    image = memory[(ix + 4) & 65535]
    ptr = memory[0xC100 + image] | memory[0xC100 + ((image + 1) & 255)] << 8
    if not 0x4000 <= ptr <= 0xFFFF:
        raise ValueError('actor pointer outside RAM: %04X/%02X -> %04X' % (ix, image, ptr))
    page = memory[ptr] & 3
    pos, tiles = ptr + 1, []
    for row in range(256):
        if pos >= 65536:
            raise ValueError('actor record wraps')
        width = memory[pos]
        pos += 1
        if not width:
            return {'ix': ix, 'image': image, 'pointer': ptr, 'x': registers[11],
                    'y': memory[(ix + 2) & 65535], 'tiles': tuple(tiles)}
        if width > 128 or pos + width + 2 > 65536:
            raise ValueError('invalid actor run at %04X' % (pos - 1))
        dx, dy = memory[pos:pos + 2]
        dx, dy = (dx - 256 if dx > 127 else dx), (dy - 256 if dy > 127 else dy)
        pos += 2
        tiles.extend((dx + j, dy, memory[pos + j] + 256 * page) for j in range(width))
        pos += width
    raise ValueError('unterminated actor record')


@lru_cache(maxsize=32768)
def tile_pixels(raw):
    """Original tile pixels, Spectrum colour index; both black brightnesses normalize to zero."""
    attr = raw[8]
    bright = (attr >> 3) & 8
    ink, paper = (attr & 7) | bright, ((attr >> 3) & 7) | bright
    ink = ink if ink & 7 else 0
    paper = paper if paper & 7 else 0
    return bytes(ink if row & (128 >> x) else paper for row in raw[:8] for x in range(8))


def raw_tile(memory, tile):
    return bytes(memory[0xDC00 + 8 * tile:0xDC08 + 8 * tile]) + bytes((memory[0xFC00 + tile],))


@lru_cache(maxsize=4096)
def solid_image(tiles):
    """Approved B: nonblack ink plus enclosed black interiors, exterior transparent.

    Input includes source bytes, not just pointers. Fill before clipping the whole image.
    Palette index 0 is transparent, 1 black, 2..8 normal colours, 9..15 bright colours.
    """
    if not tiles:
        return 0, 0, 0, 0, b''
    left = min(x for x, y, raw in tiles) * 8
    top = min(y for x, y, raw in tiles) * 8
    width = (max(x for x, y, raw in tiles) + 1) * 8 - left
    height = (max(y for x, y, raw in tiles) + 1) * 8 - top
    if width * height > 65536:
        raise ValueError('actor canvas exceeds scratch capacity')
    pixels = bytearray(width * height)
    for x, y, raw in tiles:
        data = tile_pixels(raw)
        for row in range(8):
            at = ((y * 8 - top + row) * width) + x * 8 - left
            pixels[at:at + 8] = bytes(c + 1 if 0 < c < 8 else c for c in data[row * 8:row * 8 + 8])
    outside = bytearray(len(pixels))
    todo = list(range(width)) + list(range((height - 1) * width, height * width))
    todo.extend(y * width + x for y in range(height) for x in (0, width - 1))
    while todo:
        at = todo.pop()
        if outside[at] or pixels[at]:
            continue
        outside[at] = 1
        x = at % width
        if x:
            todo.append(at - 1)
        if x + 1 < width:
            todo.append(at + 1)
        if at >= width:
            todo.append(at - width)
        if at + width < len(pixels):
            todo.append(at + width)
    for i, p in enumerate(pixels):
        if not p and not outside[i]:
            pixels[i] = 1
    return left, top, width, height, bytes(pixels)


def visible_patterns(actor, memory):
    """4-bit 16x16 chunks in original object coordinates; only viewport-visible chunks count."""
    key = tuple((dx, dy, raw_tile(memory, t)) for dx, dy, t in actor['tiles'])
    left, top, w, h, pixels = solid_image(key)
    chunks = {}
    for cy in range(0, h, 16):
        for cx in range(0, w, 16):
            pattern = bytearray(128)
            visible = False
            for y in range(16):
                if cy + y >= h:
                    break
                local_y = top + cy + y
                world_y = ((actor['y'] + local_y // 8) & 255) * 8 + local_y % 8
                for x in range(16):
                    if cx + x >= w:
                        break
                    c = pixels[(cy + y) * w + cx + x]
                    if not c:
                        continue
                    pattern[y * 8 + x // 2] |= c << (4 if not x & 1 else 0)
                    local_x = left + cx + x
                    world_x = ((actor['x'] + local_x // 8) & 255) * 8 + local_x % 8
                    visible |= 0 <= world_x < 256 and 0 <= world_y < 144
            if visible:
                chunks[cx, cy] = bytes(pattern)
    return chunks



def render_model_units():
    """Whole-image B silhouettes, content-key changes, palette and clip/wrap controls."""
    counts = Counter()
    def check(name, condition):
        counts[name] += 1
        if not condition:
            counts[name + '!'] += 1
    closed = bytes((0x7E, 0x42, 0x42, 0x42, 0x42, 0x7E, 0, 0, 7))
    opened = bytes((0x6E,)) + closed[1:]
    _, _, w, h, solid = solid_image(((0, 0, closed),))
    _, _, _, _, hollow = solid_image(((0, 0, opened),))
    check('closed interior', solid[2 * w + 3] == 1)
    check('exterior transparent', solid[7 * w] == 0)
    check('original ink colour', solid[1] == 8)
    check('open interior', hollow[2 * w + 3] == 0)
    check('source-content cache', solid != hollow)
    check('overwrite order', solid_image(((0, 0, closed), (0, 0, opened)))[4] == hollow)
    left = bytes((0x7F, 0x40, 0x40, 0x40, 0x40, 0x7F, 0, 0, 7))
    right = bytes((0xFE, 2, 2, 2, 2, 0xFE, 0, 0, 7))
    x, y, wide, tall, pixels = solid_image(((-1, 0, left), (0, 0, right)))
    check('fill across tile seam', x == -8 and pixels[2 * wide + 7:2 * wide + 9] == b'\1\1')
    bright = solid_image(((0, 0, closed[:-1] + b'\x47'),))[4]
    check('bright palette', bright[1] == 15 and bright[2 * w + 3] == 1)
    # An ink-only broken builder must disagree at an enclosed black pixel.
    check('missing-fill control detected', tile_pixels(closed)[2 * w + 3] == 0 and solid[2 * w + 3] == 1)
    memory = [0] * 65536
    memory[0xDC08:0xDC10], memory[0xFC01] = closed[:8], closed[8]
    for bx, by, dx, dy, visible in ((255, 0, 1, 0, True), (31, 0, 1, 0, False),
                                    (0, 0, -1, 0, False), (0, 255, 0, 1, True),
                                    (0, 17, 0, 1, False)):
        a = {'x': bx, 'y': by, 'tiles': ((dx, dy, 1),)}
        check('viewport wrap/clip', bool(visible_patterns(a, memory)) == visible)
    return {'counts': dict(counts), 'scope': 'software B silhouette/palette/resource model; no runtime sprite rasterizer'}


def map_tiles(memory):
    return tuple(memory[a] | (memory[a + 1] & 3) << 8 for a in range(0x9B00, 0x9F80, 2))


def compose_tiles(base, actors, wrap=True):
    result = list(base)
    for a in actors:
        for dx, dy, tile in a['tiles']:
            x, y = a['x'] + dx, (a['y'] + dy) & 255
            if wrap:
                x &= 255
            if 0 <= x < 32 and 0 <= y < 18:
                result[y * 32 + x] = tile
    return tuple(result)


def ula_matches(memory, tiles):
    """Visible-colour equality; hidden stale bitmap bytes are intentionally retained."""
    mismatches = 0
    for y in range(18):
        sy = y * 8 + 48
        for x in range(32):
            expected = tile_pixels(raw_tile(memory, tiles[y * 32 + x]))
            attr = memory[0x5800 + (sy // 8) * 32 + x]
            for row in range(8):
                py = sy + row
                addr = 0x4000 + ((py & 0xC0) << 5) + ((py & 7) << 8) + ((py & 0x38) << 2) + x
                actual = tile_pixels(bytes((memory[addr],)) * 8 + bytes((attr,)))[:8]
                if actual != expected[row * 8:row * 8 + 8]:
                    mismatches += sum(a != b for a, b in zip(actual, expected[row * 8:row * 8 + 8]))
    return mismatches


def scenery_delta(old, new):
    """Minimum dirty cells after a one-cell hardware scroll; exposed edges always dirty."""
    if old is None:
        return 576, (0, 0)
    best = (577, (0, 0))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            dirty = sum(not (0 <= x + dx < 32 and 0 <= y + dy < 18)
                        or new[y * 32 + x] != old[(y + dy) * 32 + x + dx]
                        for y in range(18) for x in range(32))
            if dirty < best[0]:
                best = dirty, (dx, dy)
    return best


def model_verify(path, stop=2000, capture=False):
    """Original-image reconstruction and resource census, NOT a sprite hook verifier.

    C replay is only the source machine. Process live producer events immediately, keeping
    bounded examples; never retain per-frame 64K snapshots. A dropped-writer negative control
    must be informative. Desync, malformed records and mismatches fail explicitly.
    """
    import skoolkit.rzxplay as rp
    from skoolkit import SkoolKitError
    from skoolkit.snapshot import Snapshot
    from types import SimpleNamespace
    from hashlib import sha256
    from .rzx import parse_rzx, InputRecording
    blocks = parse_rzx(str(path))
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    ctx.total_frames = min(stop, sum(len(b.obj.frames) for b in blocks if isinstance(b.obj, InputRecording)))
    class Sink:
        def write(self, text):
            pass
    ctx.tracefile = Sink()
    counts, errors, dirty_counts, shifts, graphics = Counter(), [], Counter(), Counter(), set()
    kernel = CapturePatch() if capture else None
    interiors = ({a + j for a, (old, new) in kernel.sites.items() for j in range(1, len(old))} if kernel else set())
    private = bytearray(8192)
    tests = {}
    st = {'base': None, 'actors': [], 'tiles': None, 'previous': None, 'patterns': set(), 'chunks': 0, 'previous_patterns': set()}
    def fail(kind, detail):
        counts[kind + '!'] += 1
        if len(errors) < 5:
            errors.append([ctx.frame_count, kind, detail])
    def event(tf, context, fc, pc):
        if kernel and pc in interiors:
            fail('instruction interior entry', '%04X' % pc)
        if pc not in (0x8F7C, 0x959B, 0x96A1, 0x8F92, 0x8F95):
            return
        sim = context.simulator
        m, r = sim.memory, sim.registers
        try:
            nonlocal private
            if kernel and pc in kernel.sites and (pc == 0x8F7C or st['base'] is not None):
                private, cost, steps = run_capture(kernel, m, list(r), private, pc)
                counts['kernel events'] += 1
                counts['kernel instructions'] += steps
                if pc == 0x8F7C:
                    st['capture_cost'] = 0
                st['capture_cost'] = st.get('capture_cost', 0) + cost
                if pc in (0x959B, 0x96A1) and cost > 2000:
                    fail('capture bookkeeping budget', cost)
                if pc == 0x8F92:
                    counts['max capture tick cost'] = max(counts['max capture tick cost'], st['capture_cost'])
                counts['max kernel cost %04X' % pc] = max(counts['max kernel cost %04X' % pc], cost)
                if pc not in tests:
                    tests[pc] = (list(m), list(r), bytearray(private))
            if pc == 0x8F7C:
                base = map_tiles(m)
                dirty, shift = scenery_delta(st['previous'], base)
                if st['previous'] is not None:
                    dirty_counts[dirty] += 1
                    shifts[str(shift)] += 1
                st.update(base=base, previous=base, actors=[], tiles=None, chunks=0, patterns=set())
                graphics.add(sha256(bytes(m[0xDC00:0x10000])).hexdigest())
                counts['scenery events'] += 1
            elif pc in (0x959B, 0x96A1) and st['base'] is not None:
                a = actor_tiles(m, r)
                st['actors'].append(a)
                pats = visible_patterns(a, m)
                st['chunks'] += len(pats)
                st['patterns'].update(pats.values())
                counts['actor events'] += 1
                counts['wrapped path' if pc == 0x96A1 else 'normal path'] += 1
            elif pc == 0x8F92 and st['base'] is not None:
                actual = map_tiles(m)
                if kernel:
                    logged = capture_log(private)
                    key = lambda a: (a['ix'], a['x'], a['y'], a['image'], a['tiles'])
                    if [key(a) for a in logged] != [key(a) for a in st['actors']]:
                        fail('captured actor log', 'records differ from live original events')
                    raw_map = bytes(private[0x400:0x880])
                    stored = tuple(raw_map[i] | (raw_map[i + 1] & 3) << 8 for i in range(0, len(raw_map), 2))
                    if stored != st['base'] or private[0x3F6] != 2:
                        fail('captured scenery/phase', 'base image or commit phase differs')
                expected = compose_tiles(st['base'], st['actors'])
                if actual != expected:
                    fail('tile reconstruction', {'cells': [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b][:8], 'actors': [(a['ix'], a['image'], a['pointer'], a['x'], a['y'], len(a['tiles'])) for a in st['actors']]})
                elif st['actors'] and compose_tiles(st['base'], st['actors'][:-1]) != actual:
                    counts['dropped writer detected'] += 1
                if compose_tiles(st['base'], st['actors'], wrap=False) != actual:
                    counts['coordinate control detected'] += 1
                st['tiles'] = expected
                counts['max image calls'] = max(counts['max image calls'], len(st['actors']))
                counts['max visible chunks'] = max(counts['max visible chunks'], st['chunks'])
                counts['max unique patterns'] = max(counts['max unique patterns'], len(st['patterns']))
                counts['max pending pattern union'] = max(counts['max pending pattern union'], len(st['patterns'] | st['previous_patterns']))
                st['previous_patterns'] = set(st['patterns'])
                counts['tile checks'] += 1
            elif pc == 0x8F95 and st['tiles'] is not None:
                differences = ula_matches(m, st['tiles'])
                if differences:
                    fail('ULA reconstruction', differences)
                counts['ULA checks'] += 1
                st['base'] = st['tiles'] = None
        except (ValueError, IndexError, AssertionError) as e:
            fail('decode', str(e))
            st['base'] = st['tiles'] = None
    old = rp.trace_exec
    rp.trace_exec = event
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop, force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            if ctx.stop:
                break
    except SkoolKitError as e:
        fail('desync', str(e))
    finally:
        rp.trace_exec = old
    if not counts['tile checks'] or not counts['ULA checks'] or not counts['dropped writer detected']:
        fail('coverage', 'missing complete image or informative dropped-writer control')
    if kernel:
        if set(tests) != set(kernel.sites):
            fail('kernel coverage', 'missing site states')
        counts.update(capture_units(kernel, tests))
        counts.update(capture_irq_units(kernel, tests))
        # Broken DI uses the very same page, log and source state as the good kernel.
        if 0x8F7C in tests:
            mem0, r0, state0 = tests[0x8F7C]
            broken = bytearray(kernel.code)
            broken[0] = 0
            try:
                run_capture(CapturePatch(broken), mem0, r0, state0, 0x8F7C)
            except AssertionError:
                counts['unsafe DI control detected'] += 1
            else:
                fail('unsafe DI control', 'missing DI was not detected')
            if 0x959B in tests:
                nmem, nregs, nstate = tests[0x959B]
                broken = bytearray(kernel.code)
                off = broken.index(bytes.fromhex('C39E95'))
                broken[off + 1] = 0x9C   # illegal entry into the replaced IX-indexed instruction
                try:
                    run_capture(CapturePatch(broken), nmem, nregs, nstate, 0x959B)
                except AssertionError as e:
                    if 'instruction interior' in str(e):
                        counts['interior jump control detected'] += 1
                    else:
                        fail('interior jump control', str(e))
                else:
                    fail('interior jump control', 'interior/padding jump was not detected')
            # Scribble a live game byte with the entry A, retaining the broken kernel's own
            # private page and tables. This specifically exercises the whole-RAM comparator.
            bad_address = next(a for a in range(16384, 65536) if a not in kernel.site_bytes and mem0[a] != r0[0])
            broken = bytearray(kernel.code)
            off = broken.index(bytes.fromhex('21009B'))
            broken[off:off + 3] = b'\x32' + bad_address.to_bytes(2, 'little')
            try:
                run_capture(CapturePatch(broken), mem0, r0, state0, 0x8F7C)
            except AssertionError as e:
                if 'capture touched game RAM' in str(e):
                    counts['game RAM control detected'] += 1
                else:
                    fail('game RAM control', str(e))
            else:
                fail('game RAM control', 'live game byte corruption was not detected')
    return {'frames': ctx.frame_count, 'counts': dict(counts), 'examples': errors,
            'scenery_dirty_histogram': dict(sorted(dirty_counts.items())), 'scenery_shifts': dict(shifts),
            'graphics_content_versions': len(graphics),
            'scope': ('capture kernel + original reconstruction; no display layer, loader integration or total-render timing' if capture else 'original reconstruction/resource census; no sprite hooks or timings')}



def capture_all(reference, folder, stop=2000, progress=None):
    """All six quick capture checks in one process, including cross-level simulator/cache reuse."""
    reference, folder = Path(reference), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    counts, cases, frames = Counter(), [], 0
    for level in range(1, 7):
        result = model_verify(reference / ('Inferno%d.rzx' % level), stop, capture=True)
        filename = 'capture%d.json' % level
        (folder / filename).write_text(json.dumps(result, indent=2) + '\n')
        bad = {k: v for k, v in result['counts'].items() if k.endswith('!') and v}
        for k, v in result['counts'].items():
            counts[k] = max(counts[k], v) if k.startswith('max ') else counts[k] + v
        frames += result['frames']
        cases.append({'level': level, 'file': filename, 'failures': bad})
        if progress:
            progress('Capture level %d: %s (%d frames)' % (level, 'FAIL' if bad else 'PASS', result['frames']))
    return {'frames': frames, 'counts': dict(counts), 'cases': cases,
            'scope': 'capture/model/invariant checks only; no sprite/Layer 2 renderer or continuous release'}


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




class CapturePatch:
    """Capture-only runtime. No sprite or Layer 2 registers are enabled by these hooks."""
    def __init__(self, code=None):
        prof = load_profile()
        self.syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
        self.code = code if code is not None else bytes.fromhex(prof['hooks']['capture'])
        self.rom = loader_rom()
        org = self.syms['cap_scene']
        if org + len(self.code) >= 0x3D00 or any(v != 255 for v in self.rom[org:org + len(self.code)]):
            raise ValueError('capture code overlaps live ROM')
        self.rom[org:org + len(self.code)] = self.code
        self.sites, self.stops = {}, {}
        for address, spec in prof['capture_sites'].items():
            a = int(address, 16)
            old = bytes.fromhex(spec['original'])
            new = b'\xC3' + self.syms[spec['symbol']].to_bytes(2, 'little') + bytes(len(old) - 3)
            self.sites[a] = old, new
            self.stops[a] = int(spec['stop'], 16)
        self.site_bytes = {a + j for a, (old, new) in self.sites.items() for j in range(len(old))}

    def apply_memory(self, memory):
        ram = list(memory)
        for a, (old, new) in self.sites.items():
            if bytes(ram[a:a + len(old)]) != old:
                raise ValueError('unexpected capture site bytes at %04X' % a)
            ram[a:a + len(new)] = new
        return ram


class CaptureMemory(LoaderMemory):
    def __init__(self, ram, state, patch):
        self.ram, self.rom = ram, patch.rom
        self.pages = {STATE_PAGE: bytearray(state)}
        self.mmu0, self.speed = 255, 0
        self.writes, self.maps, self.fast_reads = [], [], 0

    def __getitem__(self, a):
        if self.speed == 3 and isinstance(a, int):
            self.fast_reads += 1
        return super().__getitem__(a)

    def nextreg(self, reg, value):
        if reg == 0x07:
            if value not in (0, 3):
                raise AssertionError('unexpected CPU speed')
            self.speed = value
        elif reg == 0x50 and value in (255, STATE_PAGE):
            self.mmu0 = value
            self.maps.append(value)
        else:
            raise AssertionError('capture changed an unowned register/page')


def run_capture(patch, memory, registers, state, site):
    """Differential instruction test through the displaced original instruction(s).

    No game-RAM exclusions except the checked patch bytes; even original CALL stack bytes must
    match. All temporary stack/register storage is in page 68. At every interrupt-enabled
    boundary, mapping/speed and original register/stack state must be safe for the game ISR.
    """
    from skoolkit.simulator import Simulator
    from .dizzy6 import _rw_simulator
    from . import z80n, simpool
    source = list(memory)
    if registers[24] != site:
        raise AssertionError('capture state is not at the requested site')
    patched_ram = patch.apply_memory(source)
    original = simpool.machine(Simulator, source, registers, 'inferno.capture.original', copy=True)
    end = patch.stops[site]
    while original.registers[24] != end:
        original.opcodes[original.memory[original.registers[24]]]()
    mem = CaptureMemory(patched_ram, state, patch)
    sim = simpool.machine(_rw_simulator(), mem, registers, 'inferno.capture.patched')
    r = sim.registers
    if r[26] != 1 or r[27] != 2:
        raise AssertionError('capture entry is not the proved IFF=1/IM2 gameplay domain')
    if site in (0x959B, 0x96A1) and r[6] != 0xC1:
        raise AssertionError('actor lookup does not use the C100 table')
    z80n.install(sim, mem.nextreg)
    elapsed, steps = 0.0, 0
    safe = [i for i in CMP if i != 24]
    while r[24] != end:
        if steps >= 10000:
            raise AssertionError('capture did not return')
        if r[24] in patch.site_bytes and r[24] not in patch.sites:
            raise AssertionError('capture jumped into a patched instruction interior')
        # Fetching the opcode is a real memory read too; charge the extra 28MHz wait below.
        before, speed, reads = r[25], mem.speed, mem.fast_reads
        opcode = mem[r[24]]
        sim.opcodes[opcode]()
        # Transition instructions charged at 3.5MHz is a conservative bound.
        elapsed += (r[25] - before + (mem.fast_reads - reads if speed == 3 else 0)) / (8 if speed == 3 and mem.speed == 3 else 1)
        if r[26]:
            if mem.mmu0 != 255 or mem.speed != 0:
                raise AssertionError('interrupt-enabled scratch mapping/fast beeper')
            if not (all(r[i] == registers[i] for i in safe) or
                    all(r[i] == original.registers[i] for i in safe)):
                raise AssertionError('interrupt-enabled intermediate register/stack state')
        steps += 1
    diffs = [i for i in CMP if r[i] != original.registers[i]]
    if diffs:
        raise AssertionError('capture registers differ: ' + str(diffs))
    expected_ram = original.memory[16384:]
    for a, (old, new) in patch.sites.items():
        expected_ram[a - 16384:a - 16384 + len(new)] = new
    actual_ram = mem.ram[16384:]
    if actual_ram != expected_ram:
        diffs = [i + 16384 for i, (a, b) in enumerate(zip(actual_ram, expected_ram)) if a != b]
        raise AssertionError('capture touched game RAM: ' + str(diffs[:8]))
    if mem.pages[STATE_PAGE][:0x3F0] != state[:0x3F0]:
        raise AssertionError('capture touched loader descriptors/cursor')
    added = elapsed - (original.registers[25] - registers[25])
    return mem.pages[STATE_PAGE], added, steps




def capture_irq_units(patch, tests):
    """Run vector trampoline FFFF/FFF4, then actual ISR, including its stack-unwind path.

    Only IRQ's dead saved-PC pair can differ after the handler; register state and every other
    RAM byte must agree. The forced-flag case uses the captured stack table, never good tables
    restored over a broken build. DI/clock/mapping invariants cover every hook instruction.
    """
    from skoolkit.simulator import Simulator
    from . import simpool
    counts = Counter()
    for site, (source, regs, private) in tests.items():
        for force_unwind in (False, True):
            reference = list(source)
            if force_unwind:
                reference[0x998E] = 1
            original = simpool.machine(Simulator, reference, regs, 'inferno.irq.original', copy=True)
            mem = patch.apply_memory(reference)
            mem[:16384] = patch.rom
            candidate = simpool.machine(Simulator, mem, regs, 'inferno.irq.candidate', copy=True)
            target = int.from_bytes(patch.sites[site][1][1:3], 'little')
            candidate.registers[24] = target
            for sim in (original, candidate):
                if not sim.accept_interrupt(sim.registers, sim.memory, 0):
                    raise AssertionError('ISR unit did not accept interrupt')
                seen_handler, returned = False, False
                for step in range(100):
                    pc = sim.registers[24]
                    in_handler = 0x998B <= pc < 0x99BC
                    seen_handler |= in_handler
                    op = sim.memory[pc]
                    sim.opcodes[op]()
                    if in_handler and op == 0xC9:
                        returned = True
                        break
                if not seen_handler or not returned:
                    raise AssertionError('ISR trampoline/handler did not reach its RET')
            normal = original.registers[24] == site and candidate.registers[24] == target
            regdiff = [i for i in CMP if i != 24 and original.registers[i] != candidate.registers[i]]
            sp = regs[12]
            allowed = {(sp - 2) & 65535, (sp - 1) & 65535} | patch.site_bytes
            memdiff = [a for a in range(16384, 65536) if a not in allowed and original.memory[a] != candidate.memory[a]]
            if regdiff or memdiff or (not normal and original.registers[24] != candidate.registers[24]):
                raise AssertionError('ISR sees hook entry differently: ' + str([regdiff, memdiff[:8]]))
            if force_unwind and normal:
                raise AssertionError('forced ISR unwind case returned normally')
            counts['ISR forced unwind unit' if force_unwind else 'ISR entry unit'] += 1
    return counts


def capture_units(patch, tests):
    """Unreached log states and position edges, using the good/broken kernel's own page data."""
    counts = Counter()
    for site in (0x959B, 0x96A1):
        if site not in tests:
            counts['unit state missing!'] += 1
            continue
        mem0, regs0, state0 = tests[site]
        ix = regs0[8] * 256 + regs0[9]
        # Cross only x/y: these are the interacting wrap/clip fields, not a graphics catalogue.
        for x in (0, 31, 32, 224, 255):
            for y in (0, 17, 18, 255):
                mem, regs, state = list(mem0), list(regs0), bytearray(state0)
                regs[11], mem[(ix + 2) & 65535] = x, y
                state[0x3F2:0x3F7] = bytes((0, 9, 0, 0, 1))
                result, cost, steps = run_capture(patch, mem, regs, state, site)
                logged = capture_log(result)
                expected = actor_tiles(mem, regs)
                key = lambda a: (a['ix'], a['x'], a['y'], a['image'], a['tiles'])
                counts['position unit'] += 1
                if len(logged) != 1 or key(logged[0]) != key(expected):
                    counts['position capture!'] += 1
        for phase in (0, 2):
            state = bytearray(state0)
            state[0x3F6] = phase
            result, cost, steps = run_capture(patch, mem0, regs0, state, site)
            counts['inactive unit'] += 1
            if result[0x3F2:0x3F7] != state[0x3F2:0x3F7]:
                counts['inactive capture!'] += 1
        state = bytearray(state0)
        state[0x3F2:0x3F7] = bytes((0, 0x1B, 0, 0, 1))
        result, cost, steps = run_capture(patch, mem0, regs0, state, site)
        counts['full log unit'] += 1
        if result[0x3F5] != 1 or result[0x3F2:0x3F5] != state[0x3F2:0x3F5]:
            counts['full log guard!'] += 1
        skipped, cost, steps = run_capture(patch, mem0, regs0, result, site)
        counts['overflow skip unit'] += 1
        if skipped[0x3F2:0x3F7] != result[0x3F2:0x3F7]:
            counts['overflow skip!'] += 1
        state = bytearray(state0)
        state[0x3F2:0x3F7] = bytes((0, 9, 255, 0, 1))
        result, cost, steps = run_capture(patch, mem0, regs0, state, site)
        counts['ordinal full unit'] += 1
        if result[0x3F5] != 1 or result[0x3F4] != 255:
            counts['ordinal full guard!'] += 1
    if 0x8F92 in tests:
        mem, regs, state0 = tests[0x8F92]
        for phase, over, expected in ((0, 0, 0), (1, 1, 0), (1, 0, 2)):
            state = bytearray(state0)
            state[0x3F6], state[0x3F5] = phase, over
            result, cost, steps = run_capture(patch, mem, regs, state, 0x8F92)
            counts['commit phase unit'] += 1
            if result[0x3F6] != expected:
                counts['commit phase!'] += 1
    # Snapshot/site refusal must run before trying to execute the corrupted bytes.
    if 0x8F7C in tests:
        mem, regs, state = tests[0x8F7C]
        for site in patch.sites:
            bad = list(mem)
            bad[site] ^= 1
            counts['site refusal unit'] += 1
            try:
                run_capture(patch, bad, regs, state, 0x8F7C)
            except ValueError:
                pass
            else:
                counts['site refusal!'] += 1
    return counts


def capture_log(state):
    """Decode the kernel's retained run lists independently of their original memory pointers."""
    if state[0x3F5]:
        raise ValueError('capture log overflow')
    count = state[0x3F4]
    end = int.from_bytes(state[0x3F2:0x3F4], 'little')
    at, records = 0x900, []
    for i in range(count):
        ix = state[at] | state[at + 1] << 8
        x, y, image, page = state[at + 2:at + 6]
        at += 6
        tiles = []
        while True:
            width = state[at]
            at += 1
            if not width:
                break
            dx, dy = state[at:at + 2]
            dx, dy = dx - 256 if dx > 127 else dx, dy - 256 if dy > 127 else dy
            at += 2
            tiles.extend((dx + j, dy, state[at + j] + 256 * (page & 3)) for j in range(width))
            at += width
        records.append({'ix': ix, 'x': x, 'y': y, 'image': image, 'tiles': tuple(tiles)})
    if at != end:
        raise ValueError('capture length/count disagreement')
    return records


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



class CaptureSnapshotPatch(BootstrapPatch):
    """Software diagnostic from level 1: capture hooks + bank loader, NO replacement display.

    A continuous release still needs original-BASIC startup installation and level-reload checks.
    This snapshot diagnostic is deliberately not exposed through the engine registry.
    """
    name = 'Inferno capture diagnostic (no sprite/Layer 2 display; not a release)'
    tail_addr, max_tail = 0x9A80, 128

    def __init__(self, blocks):
        super().__init__(blocks)
        self.capture = CapturePatch()
        self.page = bytes(self.capture.rom[8192:])
        self.extra_banks[12] = self.page + bytes(8192)
        self.sites = [(a, old, new) for a, (old, new) in self.capture.sites.items()]

    def apply(self, snap):
        if snap.is128:
            raise ValueError('capture diagnostic expects original 48K Inferno')
        source = [0] * 16384 + list(snap.banks[5] + snap.banks[2] + snap.banks[0])
        ram = self.capture.apply_memory(source)[16384:]
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])


def capture_build(reference, folder):
    from . import z80tonex, nextboot
    from .build import rom48
    from hashlib import md5
    reference, folder = Path(reference), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = reference / 'Inferno.z80'
    patch = CaptureSnapshotPatch(tape_blocks(reference / 'Inferno.tzx'))
    nex = folder / 'Inferno_capture_diagnostic.nex'
    _, tail, data, _ = z80tonex.convert(str(snapshot), str(nex), quiet=True, patch=patch)
    checks = {}
    for name, foreign in [('Sinclair', None), ('foreign ROM3', bytes(v ^ 0xA5 for v in rom48()))]:
        checks[name] = nextboot.check(str(nex), str(snapshot), patch, (tail, tail + len(data)),
                                      nexload=True, sysrom=foreign)
    return {'boot_checks': checks, 'tail': [tail, tail + len(data)],
            'nex_md5': md5(nex.read_bytes()).hexdigest(),
            'scope': 'level-1 snapshot capture diagnostic; no display layers; not continuous release or hardware candidate'}


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
    from . import z80n, simpool
    mem = LoaderMemory(ram, pages, code)
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.loader')
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

    Entry is after INC D / EX AF / DEC D / DI. Model the tape's clean byte boundary, C=7E,
    B=B0, at 05D8. Missing bytes take the edge-timeout return (XOR A canonical failure).
    Memory below the returned SP is dead stack; compare it only when callers have converged.
    """
    from skoolkit.simulator import Simulator
    from .build import rom48
    mem = list(rom48()) + list(ram[16384:])
    from . import simpool
    sim = simpool.machine(Simulator, mem, regs, 'inferno.byte_oracle', copy=True)
    mem, R = sim.memory, sim.registers
    sp = R[12]
    ret = mem[sp] | mem[(sp + 1) & 65535] << 8
    R[6], R[2], R[3], R[26] = 0, 176, 0x7E, 0
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


def loader_fixture(blocks, index, length, flag=255, verify=False, dest=0xA000, corrupt_verify=False):
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
    return ram, regs, block


def _case(blocks, index, length, flag=255, verify=False, code=None, dest=0xA000, corrupt_verify=False):
    ram, regs, block = loader_fixture(blocks, index, length, flag, verify, dest, corrupt_verify)
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




def pulse_rom_oracle(ram, regs, block):
    """Execute the unmodified ROM against actual TZX EAR pulse timings, with NO fast load.

    The C simulator models the same original Z80 instructions; tape acquisition is not replaced
    by bytes and no pulse-loop accelerator is installed. Return C/AF' can depend on EAR phase.
    """
    import contextlib
    import io
    from skoolkit import CSimulator
    from skoolkit.loadtracer import LoadTracer
    from .build import rom48
    memory = list(rom48()) + list(ram[16384:])
    from array import array
    sim = CSimulator(memory)
    sim.registers[:] = array('Q', regs)
    sim.registers[25] = 0
    sp = regs[12]
    ret = memory[sp] | memory[(sp + 1) & 65535] << 8
    block.keys = None
    config = {'accelerate_dec_a': 0, 'accelerators': [], 'byte_fmt': '02X', 'fast_load': False,
              'finish_tape': False, 'first_edge': 0, 'in_min_addr': 0,
              'list_accelerators': False, 'pause': False, 'polarity': 0, 'prefix': '$',
              'stop': ret, 'timeout': 20_000_000_000, 'tracefile': None,
              'trace_line': '', 'word_fmt': '04X'}
    tracer = LoadTracer(sim, [block], config, None)
    sim.set_tracer(tracer, False, False)
    with contextlib.redirect_stdout(io.StringIO()):
        tracer.run(0, 0, 0, [0] * 16, 0)
    if sim.registers[24] != ret or sim.registers[12] != (sp + 2) & 65535:
        raise AssertionError('physical ROM did not return')
    return sim



def pulse_tests(path):
    """Real pulse/reference return registers, valid/error blocks; strict CMP with no C/AF' exemption."""
    import copy
    from skoolkit.tape import parse_tzx
    blocks = tape_blocks(path)
    timed = [b for b in parse_tzx(str(path), timings=True).blocks if b.data]
    counts, examples = Counter(), []
    def case(index, verify=False, checksum=False, wrong_flag=False, mismatch=False):
        bs = list(blocks)
        tb = copy.copy(timed[index])
        if checksum:
            bs[index] = bs[index][:-1] + bytes((bs[index][-1] ^ 1,))
            tb.data = bs[index]
        h = blocks[index - 1] if index & 1 else None
        dest = (int.from_bytes(h[14:16], 'little') if h[1] == 3 else 23755) if h else 0xA000
        flag = bs[index][0] ^ (255 if wrong_flag else 0)
        n = len(bs[index]) - 2
        ram, regs, block = loader_fixture(bs, index, n, flag, verify, dest, mismatch)
        physical = pulse_rom_oracle(ram, regs, tb)
        bank, mem, steps = run_loader(ram, regs, packed_tape(bs, index))
        differences = [i for i in CMP if physical.registers[i] != bank.registers[i]]
        memory = [a for a in range(16384, 65536) if not 0x5B68 <= a < 0x5B80 and mem.ram[a] != physical.memory[a]]
        counts['pulse verify' if verify else 'pulse load'] += 1
        if differences or memory:
            counts['physical return!'] += 1
            if len(examples) < 5:
                examples.append([index, verify, [(i, physical.registers[i], bank.registers[i]) for i in differences], memory[:8]])
    for i in range(len(blocks)):
        case(i)
        case(i, verify=True)
    case(5, checksum=True)
    case(4, wrong_flag=True)
    case(5, verify=True, mismatch=True)
    return {'counts': dict(counts), 'examples': examples,
            'scope': 'unmodified ROM, actual TZX pulses, polarity 0, no fast load/accelerators; strict CMP/live RAM; short-tape timeout and other EAR polarities not proved'}


def continuation_case(snapshot, blocks, level, limit=2_000_000, pulse_blocks=None):
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

    from . import simpool
    original = simpool.machine(Simulator, Watch(oo, False), regs, 'inferno.continuation.original')
    patched = simpool.machine(Simulator, Watch(po, True), regs, 'inferno.continuation.patched')
    traces = [Tracer(), Tracer()]
    for sim, tracer in zip((original, patched), traces):
        sim.registers[:] = regs
        sim.set_tracer(tracer)
    calls, steps = 0, 0
    refresh_reads = Counter()
    convergences, pending = [], False
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
            orig = (pulse_rom_oracle(oo.ram, original.registers, pulse_blocks[original_cursor]) if pulse_blocks is not None
                    else rom_byte_oracle(oo.ram, original.registers, block))
            pending = pulse_blocks is not None
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
        differences = [i for i in CMP if patched.registers[i] != original.registers[i]]
        if differences:
            raise AssertionError('continuation register difference after %04X: %s' %
                                 (pc, [(i, original.registers[i], patched.registers[i]) for i in differences]))
        if pending:
            convergences.append('%04X' % patched.registers[24])
            pending = False
        steps += 1
    if any(patched.registers[i] != original.registers[i] for i in CMP):
        raise AssertionError('physical return registers did not converge at Nb handoff')
    differences = {a for a in range(16384, 65536) if po.ram[a] != oo.ram[a]} - dead
    if differences:
        raise AssertionError('physical continuation RAM did not converge: ' + str(sorted(differences)[:8]))
    if calls != 4 or po.pages[STATE_PAGE][0] != cursor + 4:
        raise AssertionError('did not consume both header/data pairs')
    if traces[0].outputs != traces[1].outputs:
        raise AssertionError('continuation I/O differs')
    return {'io_writes': len(traces[0].outputs), 'level': level, 'calls': calls, 'instructions': steps, 'unread_dead_stack': len(dead),
            'next_block': po.pages[STATE_PAGE][0], 'handoff_sp': patched.registers[12], 'handoff_pc': patched.registers[24],
            'synchronized_refresh_reads': dict(refresh_reads),
            'physical_return_convergences': convergences}


def continuation_tests(folder, pulse=False):
    folder = Path(folder)
    blocks = tape_blocks(folder / 'Inferno.tzx')
    results = []
    timed = None
    if pulse:
        from skoolkit.tape import parse_tzx
        timed = [b for b in parse_tzx(str(folder / 'Inferno.tzx'), timings=True).blocks if b.data]
    for level in range(7):
        # Every pair loads from the live level-1 state; no independent target-level restore.
        results.append(continuation_case(folder / 'Inferno.z80', blocks, level, pulse_blocks=timed))
    return {'cases': results, 'scope': ('actual TZX pulses versus bank loader to 718C; equal R inputs; Nb not executed' if pulse else 'crafted 7131 invocations to 718C; Na executed, Nb loaded but not executed; canonical bytes/equal R inputs')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument('--render-model-units', action='store_true')
    action.add_argument('--capture-all', type=Path)
    action.add_argument('--capture-build', type=Path)
    action.add_argument('--capture-check', type=Path)
    action.add_argument('--model-check', type=Path)
    ap.add_argument('--quick', type=int, default=2000)
    action.add_argument('--loader-tests', type=Path)
    action.add_argument('--bootstrap', type=Path)
    action.add_argument('--continuation-tests', type=Path)
    action.add_argument('--pulse-continuation', type=Path)
    action.add_argument('--pulse-tests', type=Path)
    ap.add_argument('--out', type=Path, default=Path('work/inferno'))
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    if (a.model_check or a.capture_check or a.capture_all) and a.quick <= 0:
        ap.error('--quick must be positive')
    if a.capture_all:
        result = capture_all(a.capture_all, a.out, a.quick, progress=print)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.render_model_units:
        result = render_model_units()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.capture_build:
        result = capture_build(a.capture_build, a.out)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(result['boot_checks'].values()))
    if a.pulse_tests:
        result = pulse_tests(a.pulse_tests)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.model_check or a.capture_check:
        result = model_verify(a.model_check or a.capture_check, a.quick, capture=bool(a.capture_check))
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.continuation_tests or a.pulse_continuation:
        result = continuation_tests(a.continuation_tests or a.pulse_continuation, pulse=bool(a.pulse_continuation))
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
        ap.error('no check/build action selected')
    counts, examples = loader_tests(a.loader_tests)
    result = {'counts': dict(counts), 'examples': examples,
              'scope': 'byte decoder only; no pulse timing, bootstrap or full-game proof'}
    if a.json:
        a.json.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(any(v for k, v in counts.items() if k.endswith('!')))


if __name__ == '__main__':
    raise SystemExit(main())
