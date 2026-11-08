"""Inferno stage 2: bank loader, capture kernel and assembled scenery baseline.

Unregistered: budgeted frame integration, sprites, recolour and continuous startup remain open.
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
    return dict(actor_descriptor(memory, image), ix=ix, x=registers[11],
                y=memory[(ix + 2) & 65535])


def actor_descriptor(memory, image):
    """Read a candidate from the live original table; positions/owners are not asset keys."""
    ptr = memory[0xC100 + image] | memory[0xC100 + ((image + 1) & 255)] << 8
    if not 0x4000 <= ptr <= 0xFFFF:
        raise ValueError('actor pointer outside RAM: %02X -> %04X' % (image, ptr))
    page = memory[ptr] & 3
    pos, tiles = ptr + 1, []
    for row in range(256):
        if pos >= 65536:
            raise ValueError('actor record wraps')
        width = memory[pos]
        pos += 1
        if not width:
            return {'image': image, 'pointer': ptr, 'tiles': tuple(tiles)}
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



def canvas_visible(actor, left, top, width, height):
    """Conservative whole-canvas visibility, including gaps that B may fill black.

    Geometry is tile-aligned and wraps in the original unsigned 8-bit tile space.
    This is a census model, not an installed runtime culling hook.
    """
    def axis(origin, offset, length, limit):
        start = (origin + offset//8) & 255
        count = length//8
        return count > 0 and (count >= 256 or start < limit or start+count > 256)
    return axis(actor['x'],left,width,32) and axis(actor['y'],top,height,18)


def live_actor_candidates(memory):
    """Speculative live-table scan. Invalid/oversize entries never imply absent draw assets.

    All 256 indices are tried, including the wrapped second pointer byte. A caller must still
    compare the complete live key at use. This host census is not a runtime prewarm scheduler.
    """
    keys = set()
    for image in range(256):
        try:
            tiles = actor_descriptor(memory,image)['tiles']
            if not tiles:
                continue
            width = (max(x for x,y,t in tiles)-min(x for x,y,t in tiles)+1)*8
            height = (max(y for x,y,t in tiles)-min(y for x,y,t in tiles)+1)*8
            if width > 1024 or width*height > 65536:
                continue
            keys.add(tuple((x,y,t,raw_tile(memory,t)) for x,y,t in tiles))
        except (ValueError,IndexError):
            continue
    return keys


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


def model_verify(path, stop=2000, capture=False, scenery=False, frame=False, pack=False, loading=False):
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
    actor_cache, visible_cache = {}, set()
    actor_jobs = {}
    update_timings, pre_window = [], []
    loading_result = loading_store = None
    prewarm_seen,prewarm_first_use,prewarm_frame = {},[],None
    kernel = CapturePatch() if capture else None
    frame_patch, frame_pages = FramePatch() if frame else None, None
    frame_state = None
    interiors = ({a + j for a, (old, new) in kernel.sites.items() for j in range(1, len(old))} if kernel else set())
    private = bytearray(8192)
    display_pages, scene_number = None, 0
    tests = {}
    st = {'base': None, 'actors': [], 'tiles': None, 'previous': None, 'patterns': set(), 'chunks': 0, 'previous_patterns': set()}
    def fail(kind, detail):
        counts[kind + '!'] += 1
        if len(errors) < 5:
            errors.append([ctx.frame_count, kind, detail])
    def event(tf, context, fc, pc):
        nonlocal prewarm_frame
        if pack and prewarm_frame != context.frame_count:
            prewarm_frame = context.frame_count
            candidates = live_actor_candidates(context.simulator.memory)
            counts['live table scans (host prewarm census)'] += 1
            counts['max live table candidates (host prewarm census)'] = max(
                counts['max live table candidates (host prewarm census)'],len(candidates))
            counts['max live candidate source bytes (host prewarm census)'] = max(
                counts['max live candidate source bytes (host prewarm census)'],sum(15*len(k) for k in candidates))
            for key in candidates:
                prewarm_seen.setdefault(key,(context.frame_count,pc))
        if kernel and pc in interiors:
            fail('instruction interior entry', '%04X' % pc)
        if pc not in (0x8EF9, 0x8F7C, 0x959B, 0x96A1, 0x8F92, 0x8F95):
            return
        sim = context.simulator
        m, r = sim.memory, sim.registers
        try:
            nonlocal private, display_pages, scene_number, frame_pages, frame_state, loading_result, loading_store, actor_cache, actor_jobs
            if loading and pc == 0x8EF9 and loading_result is None:
                if bytes(m[pc:pc+3]) != bytes.fromhex('329891') or r[26] or r[27] != 1:
                    raise AssertionError('loading entry is not original DI/IM1 initialization boundary')
                for name,value in loading_pause_checks(m,list(r)).items():
                    counts[name] += value
                actor_cache,actor_jobs,loading_result,loading_store = prepare_loading_cache(m)
                loading_result.update(frame=context.frame_count,pc='8EF9',iff=r[26],im=r[27])
                counts['loading prepared images (host selected)'] = len(actor_cache)
            if pc == 0x8EF9:
                return
            if kernel and pc in kernel.sites and (pc == 0x8F7C or st['base'] is not None):
                private, cost, steps = run_capture(kernel, m, list(r), private, pc)
                counts['kernel events'] += 1
                counts['kernel instructions'] += steps
                if pc == 0x8F7C:
                    st['capture_cost'] = 0
                    st['capture_components'] = Counter()
                st['capture_cost'] = st.get('capture_cost', 0) + cost
                st['capture_components']['capture_%04X' % pc] += cost
                if pc in (0x959B, 0x96A1) and cost > 2000:
                    fail('capture bookkeeping budget', cost)
                if pc == 0x8F92:
                    counts['max capture tick cost'] = max(counts['max capture tick cost'], st['capture_cost'])
                    pre_window.append(st['capture_cost'] - cost)   # copier window X (8F7C/959B/96A1)
                counts['max kernel cost %04X' % pc] = max(counts['max kernel cost %04X' % pc], cost)
                if pc not in tests:
                    tests[pc] = (list(m), list(r), bytearray(private))
            if pc == 0x8F7C:
                if loading and loading_result is None:
                    raise AssertionError('loading initialization boundary not reached before gameplay')
                st['pack_cost'] = st['culled_pack_cost'] = 0
                st['fill_cost'] = st['snapshot_cost'] = 0
                st['job_components'] = Counter()
                st['dispatch_cost'] = 0
                st['source_calls'] = Counter()
                st['repeated_source_cost'] = 0
                base = map_tiles(m)
                dirty, shift = scenery_delta(st['previous'], base)
                if st['previous'] is not None:
                    dirty_counts[dirty] += 1
                    shifts[str(shift)] += 1
                if scenery and not frame:
                    bank = 31 if scene_number % 2 == 0 else 28
                    if scenery == 'textmap':
                        rendered = run_render_textmap(m, half=scene_number % 2,
                                                      previous=display_pages)
                        counts['max textmap distinct sources'] = max(counts['max textmap distinct sources'], rendered['sources'])
                    else:
                        rendered = run_render_scene(m, bank=bank, front=59-bank, previous=display_pages)
                    if rendered['error']:
                        raise AssertionError('valid captured scene was rejected')
                    display_pages = rendered['pages']
                    scene_number += 1
                    counts['assembled scenery images'] += 1
                    counts['scenery viewport pixels compared'] += 36864
                    counts['scenery changed cells'] += rendered['changed']
                    counts['max scenery worker equivalent T'] = max(counts['max scenery worker equivalent T'], rendered['equivalent_T'])
                    st['scenery_cost'] = rendered['equivalent_T']
                    if rendered['changed'] == 0:
                        counts['unchanged scenery images'] += 1
                        counts['max unchanged scenery equivalent T'] = max(counts['max unchanged scenery equivalent T'], rendered['equivalent_T'])
                st.update(base=base, previous=base, actors=[], tiles=None, chunks=0, patterns=set())
                if scenery == 'textmap':
                    st['scenery_sources'] = {tile:raw_tile(m, tile) for tile in set(base)}
                    st['actor_sources'] = []
                graphics.add(sha256(bytes(m[0xDC00:0x10000])).hexdigest())
                counts['scenery events'] += 1
            elif pc in (0x959B, 0x96A1) and st['base'] is not None:
                a = actor_tiles(m, r)
                st['actors'].append(a)
                if scenery == 'textmap':
                    st['actor_sources'].append({tile:raw_tile(m, tile) for dx,dy,tile in a['tiles']})
                pats = visible_patterns(a, m)
                image_key = tuple((dx,dy,t,raw_tile(m,t)) for dx,dy,t in a['tiles'])
                left,top,width,height,pixels = solid_image(tuple((dx,dy,raw) for dx,dy,t,raw in image_key))
                identity = image_key  # Exact bytes/geometry; never accept a hash-only match.
                owned_view = {}
                if loading_store and identity in loading_store[1]:
                    start,size = loading_store[1][identity]
                    packed_image = loading_store[0][start:start+size]
                    cached_pixels = bytes(c for b in packed_image for c in (b >> 4,b & 15))
                    if cached_pixels != pixels:
                        raise AssertionError('loading cache image differs at actual draw')
                    counts['loading prepared pixels checked at draw'] += len(pixels)
                    selected = loading_store[3][identity]
                    dispatched = run_owned_cache(previous=loading_store[2],op=2,image=selected)
                    if dispatched['error'] or not dispatched['found']:
                        raise AssertionError('owned prepared candidate dispatch rejected')
                    e = dispatched['entry']
                    packed = owned_payload(dispatched['pages'],e[6],int.from_bytes(e[7:9],'little'),int.from_bytes(e[9:11],'little'))
                    if packed != packed_image:
                        raise AssertionError('owned high-RAM canvas differs')
                    owned_view = dict(bank=e[1],offset=int.from_bytes(e[2:4],'little'),owned=dispatched['pages'])
                    st['snapshot_cost'] += dispatched['equivalent_T']
                    st['dispatch_cost'] += dispatched['equivalent_T']
                    counts['assembled owned candidate dispatches'] += 1
                    counts['max owned candidate dispatch equivalent T'] = max(counts['max owned candidate dispatch equivalent T'],dispatched['equivalent_T'])
                if pack:
                    previous_job = actor_jobs.get(identity)
                    snapshot = run_actor_job(m,op=2 if previous_job else 0,image=a['image'],previous=previous_job,**owned_view)
                    if snapshot['error'] or (not snapshot['match'] if previous_job else not snapshot['done']):
                        raise AssertionError('observed live snapshot capture/validation rejected')
                    if actor_job_tiles(snapshot['stream']) != image_key:
                        raise AssertionError('assembled source snapshot differs from original live draw')
                    actor_jobs[identity] = {p:snapshot['pages'][p] for p in (78,122)}
                    st['snapshot_cost'] += snapshot['equivalent_T']
                    st['job_components'].update(snapshot['cost_components_T'])
                    if previous_job and st['source_calls'][snapshot['stream']]:
                        st['repeated_source_cost'] += snapshot['equivalent_T']
                    st['source_calls'][snapshot['stream']] += 1
                    counts['assembled exact live job validations' if previous_job else 'assembled immutable live job captures'] += 1
                    counts['max live job call equivalent T'] = max(counts['max live job call equivalent T'],snapshot['equivalent_T'])
                    counts['max job source bytes'] = max(counts['max job source bytes'],snapshot['size'])
                counts['max actor canvas width'] = max(counts['max actor canvas width'],width)
                counts['max actor canvas height'] = max(counts['max actor canvas height'],height)
                counts['max actor canvas pixels'] = max(counts['max actor canvas pixels'],width*height)
                if identity in actor_cache:
                    counts['actor content cache hits (model)'] += 1
                else:
                    actor_cache[identity] = 0
                    counts['actor content cache misses (model)'] += 1
                    counts['actor content cache bytes (model)'] += len(image_key)*15+(width*height+1)//2
                    if pack:
                        seen,seen_pc = prewarm_seen.get(identity,(None,None))
                        lead = None if seen is None else context.frame_count-seen
                        prewarm_first_use.append({'image':a['image'],'first_use_frame':context.frame_count,
                                                  'earliest_sampled_live_frame':seen,'lead_frames':lead,
                                                  'earliest_sampled_pc':None if seen_pc is None else '%04X' % seen_pc,
                                                  'tiles':len(image_key),'canvas_pixels':width*height})
                        counts['first-use content available in earlier sampled frame (host census)' if lead else
                               'first-use content without sampled preparation lead (host census)'] += 1
                        canvas = bytes(32768)
                        for dx,dy,t,raw in actor_job_tiles(snapshot['stream']):
                            dest = ((dy*8-top)*width+dx*8-left)//2
                            packed = run_actor_pack(m,t,dest,width//2,canvas=canvas,raw=raw)
                            canvas = packed['canvas']
                            if not packed['valid']:
                                raise AssertionError('observed actor tile rejected by packer')
                            st['pack_cost'] += packed['equivalent_T']
                            actor_cache[identity] += packed['equivalent_T']
                            counts['assembled actor tiles on model cache misses'] += 1
                        if width and height:
                            filled = run_actor_fill(canvas,width//2,width*height//2)
                            actual = bytes(c for n in filled['canvas'][:width*height//2] for c in (n >> 4,n & 15))
                            if actual != pixels:
                                raise AssertionError('assembled whole-image B differs from original-source model')
                            st['fill_cost'] += filled['equivalent_T']
                            counts['assembled whole actor B fills on model misses'] += 1
                            counts['assembled whole actor B pixels'] += width*height
                            counts['max actor B fill sweep pairs'] = max(counts['max actor B fill sweep pairs'],filled['sweep_pairs'])
                            prewarm_first_use[-1]['colour_and_fill_added_ms'] = (actor_cache[identity]+filled['equivalent_T'])/3500
                            prewarm_first_use[-1]['fill_service_calls'] = filled['service_calls']
                            prewarm_first_use[-1]['max_fill_service_added_ms'] = filled['max_service_ms']
                        counts['max cold B fill tick equivalent T'] = max(
                            counts['max cold B fill tick equivalent T'],st['fill_cost'])
                        counts['max cold colour expansion tick equivalent T'] = max(
                            counts['max cold colour expansion tick equivalent T'],st['pack_cost'])
                if pack:
                    if not canvas_visible(a,left,top,width,height):
                        if pats:
                            raise AssertionError('bounding cull removed visible pixels')
                        counts['wholly offscreen actor calls (model)'] += 1
                    elif identity not in visible_cache:
                        visible_cache.add(identity)
                        st['culled_pack_cost'] += actor_cache[identity]
                        counts['visible content cache misses (model)'] += 1
                    counts['max culled cold colour expansion tick equivalent T'] = max(
                        counts['max culled cold colour expansion tick equivalent T'],st['culled_pack_cost'])
                st['chunks'] += len(pats)
                st['patterns'].update(pats.values())
                counts['actor events'] += 1
                counts['wrapped path' if pc == 0x96A1 else 'normal path'] += 1
            elif pc == 0x8F92 and st['base'] is not None:
                if scenery and not frame:
                    counts['max capture plus scenery equivalent T'] = max(
                        counts['max capture plus scenery equivalent T'], st['capture_cost'] + st['scenery_cost'])
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
                if scenery == 'textmap':
                    for kind, sources in [('scenery', st['scenery_sources'])] + [('actor', s) for s in st['actor_sources']]:
                        if any(raw_tile(m, tile) != raw for tile,raw in sources.items()):
                            fail('post-copy ' + kind + ' source lifetime', 'live graphics changed since capture')
                        else:
                            counts['post-copy ' + kind + ' source lifetime'] += 1
                if frame:
                    if frame_state is None:
                        frame_state = (list(m), list(r), bytes(private))
                    result = run_frame(frame_patch, m, list(r), private, frame_pages)
                    frame_pages = result['pages']
                    private = bytearray(frame_pages[68])
                    if not result['ready']:
                        raise AssertionError('valid replay frame was not prepared')
                    counts['post-copy assembled frame hooks'] += 1
                    counts['scenery viewport pixels compared'] += 36864
                    counts['max post-copy frame hook equivalent T'] = max(counts['max post-copy frame hook equivalent T'], result['equivalent_T'])
                    counts['max capture plus frame hook equivalent T'] = max(counts['max capture plus frame hook equivalent T'], st['capture_cost'] + result['equivalent_T'])
                    if pack:
                        components = dict(st['capture_components'])
                        components.update(result['cost_components_T'])
                        components.update({'source_'+k:v for k,v in st['job_components'].items()})
                        components.update(candidate_dispatch=st['dispatch_cost'],
                                          cold_colour=st['pack_cost'], cold_fill=st['fill_cost'])
                        total = st['capture_cost']+result['equivalent_T']+st['snapshot_cost']+st['pack_cost']+st['fill_cost']
                        if abs(sum(components.values())-total) > 1e-6:
                            raise AssertionError('per-update timing attribution does not reconcile')
                        update_timings.append({'update':len(update_timings), 'frame':context.frame_count,
                                               'actors':len(st['actors']), 'total_ms':total/3500,
                                               'distinct_source_streams':len(st['source_calls']),
                                               'repeated_source_calls':sum(n-1 for n in st['source_calls'].values()),
                                               'repeated_source_ms':st['repeated_source_cost']/3500,
                                               'components_ms':{k:v/3500 for k,v in components.items()}})
                        counts['max live job tick equivalent T'] = max(
                            counts['max live job tick equivalent T'],st['snapshot_cost'])
                        counts['max capture scenery snapshot cold colour and B fill equivalent T'] = max(
                            counts['max capture scenery snapshot cold colour and B fill equivalent T'],
                            st['capture_cost']+result['equivalent_T']+st['snapshot_cost']+st['pack_cost']+st['fill_cost'])
                        counts['max capture scenery cold colour and B fill equivalent T'] = max(
                            counts['max capture scenery cold colour and B fill equivalent T'],
                            st['capture_cost']+result['equivalent_T']+st['pack_cost']+st['fill_cost'])
                        counts['max capture scenery and cold colour expansion equivalent T'] = max(
                            counts['max capture scenery and cold colour expansion equivalent T'],
                            st['capture_cost']+result['equivalent_T']+st['pack_cost'])
                        counts['max capture scenery and culled cold expansion equivalent T'] = max(
                            counts['max capture scenery and culled cold expansion equivalent T'],
                            st['capture_cost']+result['equivalent_T']+st['culled_pack_cost'])
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
            off = broken.index(bytes.fromhex('210009'))   # LD HL,CAP_LOG (the map copy is DMA since m3)
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
    if frame:
        if frame_state is None:
            fail('frame coverage', 'no original post-copy state')
        else:
            counts.update(frame_units(frame_patch, frame_state))
    result = {'frames': ctx.frame_count, 'counts': dict(counts), 'examples': errors,
            'prewarm_first_uses_host_census':prewarm_first_use,
            'scenery_dirty_histogram': dict(sorted(dirty_counts.items())), 'scenery_shifts': dict(shifts),
            'graphics_content_versions': len(graphics),
            'scope': ('capture kernel + offline complete scenery worker; no frame hook/commit/sprites or total-render timing' if scenery else 'capture kernel + original reconstruction; no display layer, loader integration or total-render timing' if capture else 'original reconstruction/resource census; no sprite hooks or timings')}
    if loading:
        result['loading_preparation'] = loading_result
    if capture:
        result['capture_pre_window_T'] = pre_window
    if pack:
        if frame and len(update_timings) != counts['post-copy assembled frame hooks']:
            raise AssertionError('missing per-update timing records')
        result['update_timings'] = update_timings
        result['timing_attribution'] = {
            'units':'ms at modeled 28 MHz, with existing per-read allowance',
            'method':'instruction PC ranges for source/scenery; full differential capture/frame hook costs',
            'repeated_sources':'identical complete streams within one update; diagnostic only, every draw still validates',
            'scope':'executed assembly CPU model; host work and physical waits are not timed'}
        result['scope'] = 'original frame preservation plus standalone assembled live-source snapshots/exact validations and pinned colour/B construction on host-model cache misses; no installed cache/scheduler/uploads/display'
        cold = counts['max capture scenery cold colour and B fill equivalent T']/3500
        result['timing_gate'] = {'target_total_added_ms':10,'cold_capture_scenery_colour_fill_max_ms':cold,
                                'cold_with_snapshot_validation_max_ms':counts['max capture scenery snapshot cold colour and B fill equivalent T']/3500,
                                'live_snapshot_validation_tick_max_ms':counts['max live job tick equivalent T']/3500,
                                'status':'FAIL' if max(cold,counts['max capture scenery snapshot cold colour and B fill equivalent T']/3500) > 10 else 'UNPROVED',
                                'excluded':'runtime scan/selection, source/dispatch external wrappers, uploads, queue and physical waits; capture/frame hooks and loading candidate dispatch included',
                                'hardware_proof':False}
    return result



def capture_all(reference, folder, stop=2000, progress=None, scenery=False, frame=False, pack=False, loading=False):
    """All six quick capture checks in one process, including cross-level simulator/cache reuse."""
    reference, folder = Path(reference), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    counts, cases, frames = Counter(), [], 0
    for level in range(1, 7):
        result = model_verify(reference / ('Inferno%d.rzx' % level), stop, capture=True, scenery=scenery, frame=frame, pack=pack,loading=loading)
        filename = ('loading_prep%d.json' if loading else 'actor_pack%d.json' if pack else 'frame%d.json' if frame else 'textmap%d.json' if scenery == 'textmap' else 'scenery%d.json' if scenery else 'capture%d.json') % level
        (folder / filename).write_text(json.dumps(result, indent=2) + '\n')
        bad = {k: v for k, v in result['counts'].items() if k.endswith('!') and v}
        for k, v in result['counts'].items():
            counts[k] = max(counts[k], v) if k.startswith('max ') else counts[k] + v
        frames += result['frames']
        cases.append({'level': level, 'file': filename, 'failures': bad})
        if progress:
            progress('%s level %d: %s (%d frames)' % ('Scenery/capture' if scenery else 'Capture', level, 'FAIL' if bad else 'PASS', result['frames']))
    return {'frames': frames, 'counts': dict(counts), 'cases': cases,
            'scope': ('initialization-boundary experiment; assembled pause gate, owned high-RAM store/dispatch and direct exact checks; host scan/content selection; no connected loading driver or display' if loading else 'standalone assembled snapshots/exact validations/pinned B construction plus frame preservation; host cache/census only, no installed scheduler/cache/display' if pack else 'capture plus offline assembled scenery worker; host alternates target banks, no runtime commit, sprite display or continuous release' if scenery else 'capture/model/invariant checks only; no sprite/Layer 2 renderer or continuous release')}


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





class Layer2Memory:
    """Renderer execution model: code page 69 and shadow write-only L2 paging, not a video model."""
    def __init__(self, ram, code, tile, x, y, bank, flash, visible, cache=None, front=28):
        from .build import rom48
        self.ram, self.rom = list(ram), rom48()
        self.pages = {p: bytearray([0xE3] * 8192) for p in range(56, 68)}
        self.pages[68], self.pages[69] = bytearray(8192), bytearray(8192)
        self.pages[70], self.pages[71] = bytearray(8192), bytearray(8192)
        self.pages[72], self.pages[73] = bytearray(8192), bytearray(cache) if cache is not None else bytearray(8192)
        self.mmu1 = 68
        self.pages[69][:len(code)] = code
        self.pages[69][0x1E00:0x1E07] = tile.to_bytes(2, 'little') + bytes((y, x, 0, bank, flash))
        self.pages[69][0x1FF0:0x1FF2] = b'\x00\x1D'
        self.nr, self.selected = {0x07: 3, 0x12: front, 0x13: 31, 0x69: 0x80 if visible else 0}, 0
        self.access, self.visible = 2 if visible else 0, visible
        self.reads, self.pixels, self.game_writes, self.ports = 0, 0, [], []

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        self.reads += 1
        if a < 8192:
            return self.pages[69][a]
        if a < 16384:
            return self.pages[self.mmu1][a - 8192]
        return self.ram[a]

    def __setitem__(self, a, v):
        if a < 16384 and self.access & 1:
            section = self.access >> 6
            if section > 2:
                raise AssertionError('unsupported all-48K paging')
            bank = self.nr[0x13 if self.access & 8 else 0x12]
            if self.visible and bank == self.nr[0x12]:
                raise AssertionError('renderer wrote displayed front buffer')
            page = 2 * bank + 2 * section + (a >> 13)
            if not (56 <= page <= 67 or page in (72, 73)):
                raise AssertionError('renderer wrote an unallocated page')
            self.pages[page][a & 8191] = v
            self.pixels += 1
        elif a < 8192:
            self.pages[69][a] = v
        elif a < 16384:
            self.pages[self.mmu1][a - 8192] = v
        else:
            self.game_writes.append(a)
            self.ram[a] = v

    def nextreg(self, reg, value):
        if reg == 0x51 and value in (68, 70, 71, 73):
            self.mmu1 = value
        elif reg != 0x13:
            raise AssertionError('tile routine changed an unowned NextReg')
        self.nr[reg] = value

    def read_port(self, regs, port):
        if port != 0x253B:
            raise AssertionError('unexpected renderer port read')
        return self.nr.get(self.selected, 0)

    def write_port(self, regs, port, value, *args):
        self.ports.append((port, value))
        if port == 0x243B:
            self.selected = value
        elif port == 0x123B:
            if value & 4:
                raise AssertionError('renderer enabled L2 read paging over its code')
            if bool(value & 2) != self.visible:
                raise AssertionError('renderer changed old-image visibility')
            self.access = value
        else:
            raise AssertionError('unexpected renderer port write')


def expected_tile(memory, tile, flash=0):
    """Independent pixel truth, including both ULA FLASH phases and bright black normalization."""
    a = memory[0xFC00 + tile]
    bright = 8 if a & 64 else 0
    ink, paper = (a & 7) | bright, ((a >> 3) & 7) | bright
    if a & 128 and flash:
        ink, paper = paper, ink
    ink, paper = ink if ink & 7 else 0, paper if paper & 7 else 0
    return bytes(ink if memory[0xDC00 + tile * 8 + row] & (128 >> x) else paper
                 for row in range(8) for x in range(8))


def run_render_tile(ram, tile=0, x=0, y=48, bank=31, flash=0, visible=True, code=None, cached=False, cache=None):
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    profile = load_profile()
    if code is None:
        code = bytes.fromhex(profile['hooks']['tile'])
        if cached:
            entry = int(profile['hooks']['syms']['render_cached_tile'], 16)
            code = code.ljust(entry, b'\0') + bytes.fromhex(profile['hooks']['tilecache'])
    else:
        code = bytes(code)
    entry = int(profile['hooks']['syms']['render_cached_tile'], 16) if cached else 0
    mem = Layer2Memory(ram, code, tile, x, y, bank, flash, visible, cache)
    before = {p: bytes(data) for p, data in mem.pages.items()}
    regs = [0] * 30
    regs[12], regs[14], regs[27], regs[24] = 0x1FF0, 0xFE, 2, entry
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.render.tile')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x1D00:
        if steps >= 5000:
            raise AssertionError('tile renderer did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('renderer left the protected DI/28MHz domain')
        steps += 1
    error = mem.pages[69][0x1E04]
    if mem.access != (2 if visible else 0) or r[12] != 0x1FF2 or mem.mmu1 != 68:
        raise AssertionError('renderer did not restore paging/private stack')
    if mem.game_writes or mem.ram != list(ram):
        raise AssertionError('renderer wrote original game RAM')
    if mem.pages[68] != before[68] or mem.pages[69][:len(code)] != before[69][:len(code)]:
        raise AssertionError('renderer changed capture data or its code')
    expected = {p: bytearray(before[p]) for p in (*range(56, 68), 72, 73)}
    if not error:
        pixels = expected_tile(ram, tile, flash)
        for row in range(8):
            for col in range(8):
                offset = (y + row) * 256 + x + col
                expected[2 * bank + offset // 8192][offset & 8191] = pixels[row * 8 + col]
        expected_writes = 64
        if cached:
            slot = tile & 63
            meta = slot * 16
            key = bytes(ram[0xDC00 + 8 * tile:0xDC08 + 8 * tile]) + bytes((ram[0xFC00 + tile],))
            old = before[73]
            hit = old[meta] == 0xA5 and old[meta + 1:meta + 3] == tile.to_bytes(2, 'little') and old[meta + 3:meta + 12] == key
            hit = hit and (not key[8] & 128 or old[meta + 12] == flash)
            if mem.pages[69][0x1E1A] != int(hit):
                raise AssertionError('cache key reuse disagrees with live source')
            if not hit:
                expected_writes += 64
                expected[73][meta:meta + 13] = b'\xA5' + tile.to_bytes(2, 'little') + key + bytes((flash,))
                cx, cy = (slot & 31) * 8, 48 + (slot >> 5) * 8
                for row in range(8):
                    for col in range(8):
                        offset = (cy + row) * 256 + cx + col
                        expected[72 + offset // 8192][offset & 8191] = pixels[row * 8 + col]
        if mem.pixels != expected_writes:
            raise AssertionError('tile renderer emitted the wrong pixel count')
    elif mem.pixels:
        raise AssertionError('rejected tile changed VRAM')
    if any(mem.pages[p] != expected[p] for p in expected):
        raise AssertionError('rendered Layer 2 pixels or preserved buffer differ')
    return {'error': error, 'instructions': steps, 'equivalent_T': (r[25] + mem.reads) / 8,
            'hit': mem.pages[69][0x1E1A], 'cache_data': bytes(mem.pages[73])}


def tile_renderer_units():
    counts, examples = Counter(), []
    memory = [0] * 65536
    rows = bytes((0x80, 0x01, 0xA6, 0x59, 0xFF, 0, 0x18, 0x7E))
    memory[0xDC00:0xDC08] = rows
    def check(name, **kw):
        try:
            result = run_render_tile(memory, **kw)
            counts[name] += 1
            counts['max uncached tile equivalent T'] = max(counts['max uncached tile equivalent T'], result['equivalent_T'])
            return result
        except AssertionError as e:
            counts[name + '!'] += 1
            if len(examples) < 5:
                examples.append([name, str(e)])
            return None
    for attr in range(256):
        memory[0xFC00] = attr
        for flash in ((0, 1) if attr & 128 else (0,)):
            r = check('colour/flash', flash=flash)
            if r and r['error']:
                counts['valid colour rejected!'] += 1
    for bitmap in (0, 255):
        memory[0xDC00:0xDC08] = [bitmap] * 8
        check('uniform bitmap timing edge')
    memory[0xDC00:0xDC08] = rows
    memory[0xFC00] = 0x47
    for tile, x, y in ((0, 0, 48), (127, 248, 56), (128, 0, 64), (511, 248, 120),
                       (512, 0, 128), (1023, 248, 184)):
        memory[0xDC00 + 8 * tile:0xDC08 + 8 * tile] = rows
        memory[0xFC00 + tile] = 0x47
        for visible, bank in ((True, 31), (False, 28)):
            r = check('paging edge', tile=tile, x=x, y=y, visible=visible, bank=bank)
            if r and r['error']:
                counts['valid position rejected!'] += 1
    for kw in ({'tile':1024}, {'x':1}, {'y':47}, {'y':49}, {'y':192}, {'bank':29}, {'flash':2}, {'bank':28}):
        r = check('invalid/front guard', **kw)
        if r and not r['error']:
            counts['invalid input accepted!'] += 1
    memory[0xDC00] ^= 0xFF
    check('live source mutation')
    code = bytearray.fromhex(load_profile()['hooks']['tile'])
    broken = bytearray(code)
    off = broken.index(b'\xF6\x09')
    broken[off + 1] = 1
    try:
        run_render_tile(memory, code=broken)
    except AssertionError as e:
        if 'displayed front' in str(e):
            counts['front-write control detected'] += 1
        else:
            counts['front-write control!'] += 1
    else:
        counts['front-write control!'] += 1
    broken = bytearray(code)
    off = broken.index(bytes.fromhex('3A121EB032131E'))
    broken[off:off + 3] = b'\xAF\x00\x00'
    try:
        run_render_tile(memory, code=broken)
    except AssertionError as e:
        if 'visibility' in str(e):
            counts['visibility control detected'] += 1
        else:
            counts['visibility control!'] += 1
    else:
        counts['visibility control!'] += 1
    return {'counts': dict(counts), 'examples': examples,
            'scope': 'assembled uncached L2 tile primitive; no frame scheduler, sprites, palette setup or display commit'}



def tile_cache_units():
    counts, examples = Counter(), []
    memory = [0] * 65536
    rows = bytes((128, 1, 166, 89, 255, 0, 24, 126))
    memory[0xDC00:0xDC08] = rows
    cache = None
    for attr in range(256):
        memory[0xFC00] = attr
        for flash in ((0, 1) if attr & 128 else (0,)):
            first = run_render_tile(memory, cached=True, cache=cache, flash=flash)
            second = run_render_tile(memory, cached=True, cache=first['cache_data'], flash=flash)
            counts['colour/flash miss'] += 1
            counts['colour/flash hit'] += 1
            if first['error'] or second['error'] or first['hit'] or not second['hit']:
                counts['cache roundtrip!'] += 1
            counts['max miss equivalent T'] = max(counts['max miss equivalent T'], first['equivalent_T'])
            counts['max hit equivalent T'] = max(counts['max hit equivalent T'], second['equivalent_T'])
            cache = second['cache_data']
    for bitmap in (0, 255):
        memory[0xDC00:0xDC08] = [bitmap] * 8
        a = run_render_tile(memory, cached=True)
        b = run_render_tile(memory, cached=True, cache=a['cache_data'])
        counts['uniform bitmap timing edge'] += 1
        counts['max miss equivalent T'] = max(counts['max miss equivalent T'], a['equivalent_T'])
        counts['max hit equivalent T'] = max(counts['max hit equivalent T'], b['equivalent_T'])
    memory[0xDC00:0xDC08] = rows
    for tile, x, y in ((63, 248, 56), (64, 0, 64), (127, 248, 120),
                       (128, 0, 128), (1023, 248, 184)):
        memory[0xDC00 + 8 * tile:0xDC08 + 8 * tile] = rows
        memory[0xFC00 + tile] = 0x47
        a = run_render_tile(memory, tile, x, y, cached=True, cache=cache)
        b = run_render_tile(memory, tile, x, y, cached=True, cache=a['cache_data'])
        counts['cache/VRAM edge'] += 1
        if a['error'] or b['error'] or not b['hit']:
            counts['cache edge!'] += 1
        cache = b['cache_data']
    for kw in ({'tile':1024}, {'x':1}, {'y':47}, {'y':49}, {'y':192}, {'bank':29}, {'bank':36}, {'flash':2}, {'bank':28}):
        r = run_render_tile(memory, cached=True, cache=cache, **kw)
        counts['cache input/front guard'] += 1
        if not r['error'] or r['cache_data'] != cache:
            counts['cache guard!'] += 1
    memory[0xFC00] = 0x47
    good = run_render_tile(memory, cached=True)
    memory[0xDC00] ^= 0xFF
    changed = run_render_tile(memory, cached=True, cache=good['cache_data'])
    counts['source mutation'] += 1
    if changed['hit']:
        counts['stale source!'] += 1
    profile = load_profile()
    entry = int(profile['hooks']['syms']['render_cached_tile'], 16)
    code = bytearray(bytes.fromhex(profile['hooks']['tile']).ljust(entry, b'\0') + bytes.fromhex(profile['hooks']['tilecache']))
    broken = bytearray(code)
    off = broken.index(bytes.fromhex('1ABE20'), entry)
    broken[off + 2:off + 4] = b'\0\0'  # omit raw source-byte mismatch branch
    try:
        run_render_tile(memory, cached=True, cache=good['cache_data'], code=broken)
    except AssertionError as e:
        if 'cache key reuse' in str(e):
            counts['stale-key control detected'] += 1
        else:
            counts['stale-key control!'] += 1
            examples.append(str(e))
    else:
        counts['stale-key control!'] += 1
    # Different IDs with identical source bytes collide in slot 0. ID remains part of the key.
    memory[0xDE00:0xDE08], memory[0xFC40] = memory[0xDC00:0xDC08], memory[0xFC00]
    first = run_render_tile(memory, cached=True)
    other = run_render_tile(memory, tile=64, cached=True, cache=first['cache_data'])
    counts['colliding ID'] += 1
    if other['hit']:
        counts['colliding ID!'] += 1
    return {'counts': dict(counts), 'examples': examples,
            'scope': 'assembled 64-slot content-checked background cache and inactive L2 blit; no scheduler or sprites'}


def run_render_batch(jobs, cache, bank=31, visible=True, code=None, count=None):
    """Execute the prepared-cache blitter; the caller owns live-key validation/scheduling."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    profile = load_profile()['hooks']
    entry = int(profile['syms']['render_batch'], 16)
    if code is None:
        code = bytes(entry) + bytes.fromhex(profile['tilebatch'])
    mem = Layer2Memory([0] * 65536, code, 0, 0, 48, bank, 0, visible, cache)
    data = bytes(v for job in jobs for v in job)
    mem.pages[69][0x1000:0x1000 + len(data)] = data
    mem.pages[69][0x1E30:0x1E34] = (len(jobs) if count is None else count).to_bytes(2, 'little') + bytes((bank, 0))
    before = {p: bytes(data) for p, data in mem.pages.items()}
    regs = [0] * 30
    regs[12], regs[14], regs[27], regs[24] = 0x1FF0, 0xFE, 2, entry
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.render.batch')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x1D00:
        if steps >= 500_000:
            raise AssertionError('batch renderer did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('batch left the DI/28MHz domain')
        steps += 1
    error = mem.pages[69][0x1E33]
    if mem.access != (2 if visible else 0) or r[12] != 0x1FF2 or mem.mmu1 != 68:
        raise AssertionError('batch did not restore paging/private stack')
    if mem.game_writes or any(mem.ram):
        raise AssertionError('batch wrote original game RAM')
    if mem.pages[68] != before[68] or mem.pages[69][:len(code)] != before[69][:len(code)]:
        raise AssertionError('batch changed capture data or code')
    if mem.pages[69][0x1000:0x1000 + len(data)] != data:
        raise AssertionError('batch changed its job list')
    expected = {p: bytearray(before[p]) for p in (*range(56, 68), 72, 73)}
    if not error:
        for x, y, slot in jobs:
            for row in range(8):
                for col in range(8):
                    src = 4096 + (slot >> 5) * 2048 + row * 256 + (slot & 31) * 8 + col
                    dest = (y + row) * 256 + x + col
                    expected[2 * bank + dest // 8192][dest & 8191] = cache[src]
    if mem.pixels != (0 if error else 64 * len(jobs)):
        raise AssertionError('batch emitted wrong pixel count or wrote before rejecting')
    if any(mem.pages[p] != expected[p] for p in expected):
        raise AssertionError('batch pixels/cache/preserved buffer differ')
    return {'error': error, 'instructions': steps, 'equivalent_T': (r[25] + mem.reads) / 8}


def tile_batch_units():
    counts, examples = Counter(), []
    cache = bytearray(8192)
    for slot in range(64):
        cache[slot * 16] = 0xA5
        for row in range(8):
            for col in range(8):
                cache[4096 + (slot >> 5) * 2048 + row * 256 + (slot & 31) * 8 + col] = (slot * 13 + row * 7 + col * 3) & 255
    def check(name, jobs, **kw):
        try:
            result = run_render_batch(jobs, cache, **kw)
            counts[name] += 1
            return result
        except AssertionError as e:
            counts[name + '!'] += 1
            if len(examples) < 5:
                examples.append([name, str(e)])
    for visible, bank in ((True, 31), (False, 28), (False, 31)):
        for jobs in ([], [(248, 184, 63)], [(x * 8, y * 8, (x + 32 * y) & 63) for y in range(6, 24) for x in range(32)]):
            r = check('empty/edge/full viewport', jobs, bank=bank, visible=visible)
            if r and r['error']:
                counts['valid batch rejected!'] += 1
            if r and len(jobs) == 576:
                counts['full viewport equivalent T'] = max(counts['full viewport equivalent T'], r['equivalent_T'])
                counts['full viewport per tile equivalent T'] = r['equivalent_T'] / 576
    good = [(0, 48, 0), (248, 184, 63)]
    for bad in ((1, 48, 0), (0, 47, 0), (0, 49, 0), (0, 192, 0), (0, 48, 64)):
        r = check('late invalid job atomic rejection', good + [bad])
        if r and not r['error']:
            counts['invalid job accepted!'] += 1
    for kw in ({'bank':28}, {'bank':29}, {'count':577}):
        r = check('bank/count guard', good, **kw)
        if r and not r['error']:
            counts['batch guard!'] += 1
    cache[63 * 16] = 0
    r = check('invalid cache atomic rejection', good)
    if r and not r['error']:
        counts['invalid cache accepted!'] += 1
    cache[63 * 16] = 0xA5
    h = load_profile()['hooks']
    entry = int(h['syms']['render_batch'], 16)
    broken = bytearray(bytes(entry) + bytes.fromhex(h['tilebatch']))
    off = broken.index(bytes.fromhex('F609'), entry)
    broken[off + 1] = 1  # wrong target: write front instead of shadow
    try:
        run_render_batch(good, cache, code=broken)
    except AssertionError as e:
        if 'front buffer' in str(e):
            counts['wrong-buffer control detected'] += 1
        else:
            counts['wrong-buffer control!'] += 1
            examples.append(str(e))
    else:
        counts['wrong-buffer control!'] += 1
    return {'counts': dict(counts), 'examples': examples,
            'scope': 'assembled prepared-cache batch L2 writes; live-key validation, cache preparation and frame scheduling excluded from timing'}


def scenery_code():
    h = load_profile()['hooks']
    code = bytearray()
    for block, symbol in (('tile', 'render_tile'), ('tilecache', 'render_cached_tile'),
                          ('scene', 'render_scene'), ('tilequiet', 'render_quiet')):
        entry = int(h['syms'][symbol], 16)
        code.extend(bytes(entry - len(code)))
        code.extend(bytes.fromhex(h[block]))
    return bytes(code)


def run_render_scene(ram, bank=31, flash=0, visible=True, previous=None, code=None, front=28):
    """Complete assembled clean-map worker, independent RGB/key and preservation checks."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    h = load_profile()['hooks']
    entry = int(h['syms']['render_scene'], 16)
    if code is None:
        code = scenery_code()
    mem = Layer2Memory(ram, code, 0, 0, 48, bank, flash, visible, front=front)
    if previous:
        for p, data in previous.items():
            if p == 69:
                mem.pages[p][0x1000:0x1E00] = data[0x1000:0x1E00]
            else:
                mem.pages[p][:] = data
    mem.pages[68][0x400:0x880] = bytes(ram[0x9B00:0x9F80])
    before = {p: bytes(data) for p, data in mem.pages.items()}
    regs = [0] * 30
    regs[12], regs[14], regs[27], regs[24] = 0x1FF0, 0xFE, 2, entry
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.render.scene')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x1D00:
        if steps >= 2_000_000:
            raise AssertionError('scene renderer did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('scene left the DI/28MHz domain')
        steps += 1
    error = mem.pages[69][0x1E04]
    if mem.access != (2 if visible else 0) or r[12] != 0x1FF2 or mem.mmu1 != 68:
        raise AssertionError('scene did not restore paging/private stack')
    if mem.game_writes or mem.ram != list(ram):
        raise AssertionError('scene wrote original game RAM')
    if mem.pages[68] != before[68] or mem.pages[69][:len(code)] != before[69][:len(code)]:
        raise AssertionError('scene changed capture data or code')
    expected = {p: bytearray(before[p]) for p in range(56, 68)}
    changed = 0
    if not error:
        keypage = 70 if bank == 28 else 71
        keys = bytearray(before[keypage])
        for cell, tile in enumerate(map_tiles(ram)):
            offset = cell * 13
            key = tile.to_bytes(2, 'little') + raw_tile(ram, tile)
            old = keys[offset:offset + 13]
            hit = old[0] == 0xA5 and old[1:12] == key and (not key[10] & 128 or old[12] == flash)
            if not hit:
                changed += 1
                keys[offset:offset + 13] = b'\xA5' + key + bytes((flash,))
            pixels = expected_tile(ram, tile, flash)
            x, y = (cell % 32) * 8, 48 + (cell // 32) * 8
            for row in range(8):
                for col in range(8):
                    dest = (y + row) * 256 + x + col
                    expected[2 * bank + dest // 8192][dest & 8191] = pixels[row * 8 + col]
        if mem.pages[keypage] != keys or mem.pages[141 - keypage] != before[141 - keypage]:
            raise AssertionError('scene per-buffer source keys differ')
        actual_changed = int.from_bytes(mem.pages[69][0x1E45:0x1E47], 'little')
        if actual_changed != changed:
            raise AssertionError('scene dirty count disagrees with live content')
    elif any(mem.pages[p] != before[p] for p in (70, 71, 72, 73)) or mem.pixels:
        raise AssertionError('rejected scene changed cache/VRAM')
    if any(mem.pages[p] != expected[p] for p in expected):
        raise AssertionError('complete scenery pixels or preserved front/HUD differ')
    return {'error': error, 'changed': changed, 'instructions': steps,
            'equivalent_T': (r[25] + mem.reads) / 8, 'pixel_writes': mem.pixels,
            'pages': {p: bytes(data) for p, data in mem.pages.items()}}


def scene_renderer_checks(reference, folder):
    """Bounded six-level source captures; includes cold, unchanged and same-ID mutation."""
    import gzip
    from PIL import Image
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    counts, cases = Counter(), []
    palette = [(0, 0, 0)] + [tuple(205 if c & bit else 0 for bit in (2, 4, 1)) for c in range(1, 8)]
    palette += [(0, 0, 0)] + [tuple(255 if c & bit else 0 for bit in (2, 4, 1)) for c in range(1, 8)]
    for level in range(1, 7):
        captures = json.loads(gzip.open(Path(reference) / 'design' / ('scene%d.json.gz' % level), 'rt').read())
        source = next(s for s in captures['samples'] if s['pc'] == 0x8F7C)
        ram = [0] * 16384 + source['memory']['16384']
        cold = run_render_scene(ram)
        steady = run_render_scene(ram, previous=cold['pages'])
        tile = map_tiles(ram)[0]
        ram[0xDC00 + tile * 8] ^= 255
        mutated = run_render_scene(ram, previous=steady['pages'])
        if cold['error'] or steady['error'] or mutated['error'] or steady['changed'] or steady['pixel_writes'] or not mutated['changed']:
            raise AssertionError('scene roundtrip/unchanged/source mutation failed')
        counts['cold complete scene'] += 1
        counts['unchanged no-write scene'] += 1
        counts['same-ID graphics mutation scene'] += 1
        counts['viewport pixels compared'] += 3 * 36864
        counts['max cold equivalent T'] = max(counts['max cold equivalent T'], cold['equivalent_T'])
        counts['max unchanged equivalent T'] = max(counts['max unchanged equivalent T'], steady['equivalent_T'])
        counts['max mutated equivalent T'] = max(counts['max mutated equivalent T'], mutated['equivalent_T'])
        item = {'level': level, 'frame': source['frame']}
        for name, result in (('cold', cold), ('unchanged', steady), ('mutated', mutated)):
            item[name] = {k: v for k, v in result.items() if k != 'pages'}
        cases.append(item)
        rgb = b''.join(cold['pages'][p] for p in range(62, 68))
        image = Image.new('RGB', (256, 192))
        image.putdata([palette[p] if p < 16 else (227, 0, 227) for p in rgb])
        image.crop((0, 48, 256, 192)).save(folder / ('scenery%d.png' % level))
        print('Scenery level %d: PASS cold/unchanged/live mutation' % level, flush=True)
    # Both buffer-key pages must remain independent, and hidden startup may draw bank 28.
    first = run_render_scene(ram, bank=28, visible=False)
    second = run_render_scene(ram, bank=31, previous=first['pages'])
    if first['changed'] != 576 or second['changed'] != 576:
        raise AssertionError('one buffer incorrectly validated the other')
    counts['independent buffer scene'] += 2
    for kw in ({'bank':28}, {'bank':29}, {'flash':2}):
        rejected = run_render_scene(ram, previous=second['pages'], **kw)
        if not rejected['error']:
            raise AssertionError('scene input/front guard accepted invalid target')
        counts['scene input/front guard'] += 1
    warm = run_render_scene(ram, previous=second['pages'])
    # Break source comparison while retaining the good worker's actual buffer/cache pages.
    h = load_profile()['hooks']
    entry = int(h['syms']['render_scene'], 16)
    code = scenery_code()
    broken = bytearray(code)
    off = broken.index(bytes.fromhex('1ABE20'), entry)
    broken[off + 2:off + 4] = b'\0\0'
    ram[0xDC00 + tile * 8] ^= 255
    try:
        run_render_scene(ram, previous=warm['pages'], code=broken)
    except AssertionError as e:
        if 'dirty count' not in str(e) and 'scenery pixels' not in str(e) and 'source keys' not in str(e):
            raise
        counts['stale-scene control detected'] += 1
    else:
        raise AssertionError('stale-scene control was not detected')
    # Scratch survives real calls: forgetting to clear per-image validation flags must fail.
    broken = bytearray(code)
    off = int(h['syms']['rs_clear_flags'], 16)
    end = int(h['syms']['rs_flags_cleared'], 16)
    broken[off:end] = bytes(end - off)
    try:
        run_render_scene(ram, previous=warm['pages'], code=broken)
    except AssertionError as e:
        if 'dirty count' not in str(e) and 'scenery pixels' not in str(e) and 'source keys' not in str(e):
            raise
        counts['retained-validation control detected'] += 1
    else:
        raise AssertionError('retained-validation control was not detected')
    synthetic = [0] * 65536
    synthetic[0xDC00:0xDC08] = [128, 1, 170, 85, 255, 0, 24, 126]
    synthetic[0xFC00] = 0x87
    current = run_render_scene(synthetic)
    flashed = run_render_scene(synthetic, flash=1, previous=current['pages'])
    if flashed['changed'] != 576:
        raise AssertionError('scene FLASH phase did not invalidate all cells')
    counts['whole-scene FLASH phase'] += 1
    synthetic[0xFC00] = 0x42
    recoloured = run_render_scene(synthetic, previous=flashed['pages'])
    if recoloured['changed'] != 576:
        raise AssertionError('same-ID attribute change did not invalidate all cells')
    counts['whole-scene live attribute'] += 1
    synthetic[0xDE00:0xDE08] = synthetic[0xDC00:0xDC08]
    synthetic[0xFC40] = synthetic[0xFC00]
    synthetic[0x9B00] = 64
    remapped = run_render_scene(synthetic, previous=recoloured['pages'])
    if remapped['changed'] != 1:
        raise AssertionError('one-cell map change dirtied the wrong cells')
    counts['one-cell colliding map ID'] += 1
    # Direct BC flag addressing must cover all four pages, including their boundaries.
    edges = [0, 255, 256, 511, 512, 767, 768, 1023]
    for cell in range(576):
        tile = edges[cell % len(edges)]
        synthetic[0x9B00 + 2 * cell:0x9B02 + 2 * cell] = [tile & 255, tile >> 8]
        synthetic[0xFC00 + tile] = 7
    edge_cold = run_render_scene(synthetic)
    edge_warm = run_render_scene(synthetic, previous=edge_cold['pages'])
    if edge_warm['changed'] or edge_warm['pixel_writes']:
        raise AssertionError('flag-page boundary validation missed a clean source')
    for tile in edges:
        synthetic[0xDC00 + 8 * tile] ^= 255
    edge_dirty = run_render_scene(synthetic, previous=edge_warm['pages'])
    if edge_dirty['changed'] != 576:
        raise AssertionError('flag-page boundary validation missed a changed source')
    counts['validation flag page boundaries'] += len(edges)
    return {'counts': dict(counts), 'cases': cases,
            'scope': 'assembled complete scenery baseline on bounded stage-1 captures, not a frame hook, budgeted renderer, sprite display or hardware proof'}


class TextMapMemory(Layer2Memory):
    """Private text-mode back maps/definitions in physical page 14; no video emulation."""
    def __init__(self, ram, half, flash, front, previous, code):
        super().__init__(ram, code, 0, 0, 48, 31, 0, False)
        self.pages[14] = bytearray(previous[14]) if previous else bytearray([0xE3] * 8192)
        if previous and 69 in previous:
            self.pages[69][0x800:0x1800] = previous[69][0x800:0x1800]
        self.mmu2 = 10
        self.half, self.front, self.text_writes = half, front, set()
        self.pages[69][0x1E80:0x1E83] = bytes((half, flash, front))
        self.pages[68][0x400:0x880] = bytes(ram[0x9B00:0x9F80])
        # Immutable bytecode lookup data, initialized once by a future boot hook.
        for phase in range(2):
            for attr in range(256):
                pair = attr & 127
                if phase and attr & 128:
                    pair = (pair & 64) | ((pair & 7) << 3) | ((pair >> 3) & 7)
                self.pages[69][0x400 + 256 * phase + attr] = pair * 2

    def nextreg(self, reg, value):
        if reg != 0x52 or value not in (14, 10):
            raise AssertionError('textmap changed an unowned register')
        self.mmu2 = value

    def __getitem__(self, a):
        if not isinstance(a, slice) and 0x4000 <= a < 0x6000 and self.mmu2 == 14:
            self.reads += 1
            return self.pages[14][a - 0x4000]
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if 0x4000 <= a < 0x6000 and self.mmu2 == 14:
            off = a - 0x4000
            if self.front in (0, 1) and (self.front * 0x600 <= off < self.front * 0x600 + 0x600
                    or 0xC00 + self.front * 0x800 <= off < 0x1400 + self.front * 0x800):
                raise AssertionError('textmap wrote visible map or definitions')
            self.text_writes.add(off)
            self.pages[14][off] = v
            return
        super().__setitem__(a, v)

    def write_port(self, *args):
        raise AssertionError('textmap worker changed a display port')


def run_render_textmap(ram, half=0, flash=0, previous=None, front=None, code=None):
    """Execute fresh-source 1-bit map construction; compare every pixel independently."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    code = bytes.fromhex(load_profile()['hooks']['textmap']) if code is None else code
    front = 1 - half if front is None else front
    mem = TextMapMemory(ram, half, flash, front, previous, code)
    before = {p: bytes(data) for p, data in mem.pages.items()}
    regs = [0] * 30
    regs[12], regs[14], regs[27] = 0x1FF0, 0xFE, 2
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.render.textmap')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x1D00:
        if steps >= 200000:
            raise AssertionError('textmap did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('textmap left DI/28MHz domain')
        steps += 1
    error = mem.pages[69][0x1E83]
    sources = int.from_bytes(mem.pages[69][0x1E84:0x1E86], 'little')
    if r[12] != 0x1FF2 or mem.mmu1 != 68 or mem.mmu2 != 10 or mem.game_writes or mem.ram != list(ram):
        raise AssertionError('textmap changed game RAM or failed stack/mapping restore')
    if mem.pages[68] != before[68] or mem.pages[69][:0x600] != before[69][:0x600]:
        raise AssertionError('textmap changed capture/code/lookup tables')
    if any(mem.pages[p] != before[p] for p in mem.pages if p not in (14, 69)):
        raise AssertionError('textmap wrote an unowned page')
    if not error:
        allowed = set(range(0xC00 + half * 0x800, 0xC00 + half * 0x800 + sources * 8))
        data = mem.pages[14]
        for cell, tile in enumerate(map_tiles(ram)):
            offset = half * 0x600 + (cell // 32) * 80 + (cell % 32) * 2
            allowed.update((offset, offset + 1))
            slot = data[offset] + ((data[offset + 1] & 1) << 8)
            pair = data[offset + 1] >> 1
            bright = 8 if pair & 64 else 0
            ink, paper = (pair & 7) | bright, ((pair >> 3) & 7) | bright
            ink, paper = ink if ink & 7 else 0, paper if paper & 7 else 0
            bitmap = data[0xC00 + slot * 8:0xC08 + slot * 8]
            pixels = bytes(ink if row & (128 >> x) else paper for row in bitmap for x in range(8))
            if pixels != expected_tile(ram, tile, flash):
                raise AssertionError('textmap pixel mismatch at cell %d' % cell)
        if not mem.text_writes <= allowed:
            raise AssertionError('textmap wrote outside back map/used definitions')
    return {'error': error, 'sources': sources, 'changed': 576 if not error else 0,
            'instructions': steps, 'equivalent_T': (r[25] + mem.reads) / 8,
            'pixel_writes': 0, 'bytes_written': len(mem.text_writes),
            'pages': {p: bytes(mem.pages[p]) for p in (14, 69)}}


def textmap_checks(reference):
    """Six bounded scenes, palette/FLASH closure, buffer and capacity boundaries."""
    import gzip
    counts, cases = Counter(), []
    for level in range(1, 7):
        captures = json.loads(gzip.open(Path(reference) / 'design' / ('scene%d.json.gz' % level), 'rt').read())
        source = next(s for s in captures['samples'] if s['pc'] == 0x8F7C)
        ram = [0] * 16384 + source['memory']['16384']
        first = run_render_textmap(ram)
        second = run_render_textmap(ram, half=1, previous=first['pages'])
        if first['error'] or second['error']:
            raise AssertionError('bounded textmap scene rejected')
        counts['bounded scenes both buffers'] += 2
        counts['viewport pixels compared'] += 2 * 36864
        counts['max scene equivalent T'] = max(counts['max scene equivalent T'], first['equivalent_T'])
        cases.append({'level': level, **{k:v for k,v in first.items() if k != 'pages'}})
    ram = [0] * 65536
    # All 256 attributes and both FLASH phases in one scene; exactly full 256-slot half.
    for cell in range(576):
        tile = cell % 256
        ram[0x9B00 + 2 * cell:0x9B02 + 2 * cell] = [tile, 3]
        ram[0xFC00 + 768 + tile] = tile
        ram[0xDC00 + 8 * (768 + tile):0xDC08 + 8 * (768 + tile)] = [tile ^ (1 << b) for b in range(8)]
    first = run_render_textmap(ram)
    for phase in (0, 1):
        result = run_render_textmap(ram, half=1, flash=phase, previous=first['pages'])
        if result['error'] or result['sources'] != 256:
            raise AssertionError('full textmap half rejected')
        counts['attribute/FLASH cases'] += 256
        counts['max full-half equivalent T'] = max(counts['max full-half equivalent T'], result['equivalent_T'])
    for kw in ({'half':0,'front':0}, {'half':2,'front':0}, {'flash':2}):
        result = run_render_textmap(ram, **kw)
        if result['error'] != 1 or result['bytes_written']:
            raise AssertionError('textmap front/input guard failed')
        counts['input/front guard'] += 1
    ram[0x9B00 + 512:0x9B02 + 512] = [0, 0]
    result = run_render_textmap(ram, half=1, previous=first['pages'])
    if result['error'] != 2:
        raise AssertionError('textmap source overflow not rejected')
    counts['257-source rejection with preserved front'] += 1
    # The old frame's actual scratch survives; missing reset must not reuse stale content.
    code = bytes.fromhex(load_profile()['hooks']['textmap'])
    ram[0x9B00 + 512:0x9B02 + 512] = [0, 3]
    for tile in range(768, 1024):
        ram[0xDC00 + tile * 8] ^= 255
    rebuilt = run_render_textmap(ram, previous=first['pages'])
    if rebuilt['error']:
        raise AssertionError('same-ID live mutation was rejected')
    counts['same-ID live mutation with retained scratch'] += 1
    broken = bytearray(code)
    off = broken.index(bytes([0xC5]) * 16)
    broken[off:off + 16] = bytes(16)
    try:
        run_render_textmap(ram, previous=first['pages'], code=broken)
    except AssertionError as e:
        if 'pixel mismatch' not in str(e):
            raise
        counts['stale-source control detected'] += 1
    else:
        raise AssertionError('textmap stale-source control not detected')
    broken = bytearray(code)
    off = broken.index(bytes.fromhex('110046'))
    broken[off + 1:off + 3] = bytes.fromhex('0040')
    try:
        run_render_textmap(ram, half=1, previous=first['pages'], code=broken)
    except AssertionError as e:
        if 'visible map' not in str(e):
            raise
        counts['front-write control detected'] += 1
    else:
        raise AssertionError('textmap front-write control not detected')
    # A single-bit display error must fail independently of the compiler's tables.
    broken = bytearray(code)
    # Omit one bitmap-row inversion; FLASH pixels must disagree.
    off = broken.index(bytes.fromhex('7E2F77'))
    broken[off + 1] = 0
    try:
        run_render_textmap(ram, flash=1, code=broken)
    except AssertionError as e:
        if 'pixel mismatch' not in str(e):
            raise
        counts['FLASH control detected'] += 1
    else:
        raise AssertionError('textmap FLASH control not detected')
    return {'counts': dict(counts), 'cases': cases,
            'scope': 'assembled textmap construction only; no display setup, frame commit, sprite renderer or raster proof'}


@lru_cache(maxsize=1)
def actor_row_lookup():
    """128KiB immutable row decoder; no game assets or silhouette decisions."""
    data = bytearray()
    for attr in range(128):
        bright = 8 if attr & 64 else 0
        ink, paper = attr & 7, (attr >> 3) & 7
        ink = (ink | bright) if bright and ink else ink + 1 if ink else 0
        paper = (paper | bright) if bright and paper else paper + 1 if paper else 0
        for row in range(256):
            for shift in (6, 4, 2, 0):
                pair = (row >> shift) & 3
                data.append(((ink if pair & 2 else paper) << 4) | (ink if pair & 1 else paper))
    return bytes(data)


class ActorPackMemory(TextMapMemory):
    """Execute the packed tile worker with guarded expanded-memory mappings."""
    def __init__(self, ram, tile, dest, stride, flash, code, canvas=None, raw=None):
        super().__init__(ram, 0, 0, 1, None, code)
        # The inherited worker array represents physical page 75, not page 69.
        self.pages[75] = self.pages.pop(69)
        table = actor_row_lookup()
        self.pages.update({p: bytearray(table[(p-96)*8192:(p-95)*8192]) for p in range(96,112)})
        canvas = bytes([0xE3])*32768 if canvas is None else canvas
        if len(canvas) != 32768:
            raise ValueError('actor canvas must contain exactly 32768 bytes')
        self.pages.update({p: bytearray(canvas[(p-112)*8192:(p-111)*8192]) for p in range(112,116)})
        self.pages[75][0x1ED0:0x1ED7] = (tile.to_bytes(2,'little') + dest.to_bytes(2,'little')
                                               + stride.to_bytes(2,'little') + bytes((flash,)))
        self.pinned = raw is not None
        self.pages[75][0x1EDB] = int(self.pinned)
        if self.pinned:
            if len(raw) != 9:
                raise ValueError('pinned tile must contain bitmap and attribute')
            self.pages[75][0x1EC0:0x1EC9] = raw
        self.canvas_writes = set()

    def __getitem__(self, a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        self.reads += 1
        if a < 0x2000:
            return self.pages[75][a]
        if a < 0x4000:
            return self.pages[self.mmu1][a & 8191]
        if a < 0x6000 and self.mmu2 != 10:
            return self.pages[self.mmu2][a & 8191]
        if self.pinned and a >= 0xDC00:
            raise AssertionError('pinned pack read original live graphics')
        return self.ram[a]

    def __setitem__(self, a, v):
        if a < 0x2000:
            if not (0x1ED0 <= a < 0x1EE0 or 0x1FE0 <= a < 0x1FF0):
                raise AssertionError('actor pack changed code or unowned state')
            self.pages[75][a] = v
        elif 0x2000 <= a < 0x4000 and 112 <= self.mmu1 <= 115:
            self.canvas_writes.add((self.mmu1-112)*8192+(a & 8191))
            self.pages[self.mmu1][a & 8191] = v
        else:
            raise AssertionError('actor pack wrote game RAM, capture or lookup')

    def nextreg(self, reg, value):
        if reg == 0x51 and value in (68,112,113,114,115):
            self.mmu1 = value
        elif reg == 0x52 and (value == 10 or 96 <= value <= 111):
            self.mmu2 = value
        else:
            raise AssertionError('actor pack changed an unowned register')


def run_actor_pack(ram, tile=0, dest=0, stride=4, flash=0, code=None, canvas=None, raw=None):
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    code = bytes.fromhex(load_profile()['hooks']['pack']) if code is None else code
    mem = ActorPackMemory(ram,tile,dest,stride,flash,code,canvas,raw)
    initial = b''.join(mem.pages[p] for p in range(112,116))
    regs = [0]*30
    regs[12],regs[14],regs[27] = 0x1FF0,0xFE,2
    sim = simpool.machine(_rw_simulator(),mem,regs,'inferno.actor.pack')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    r,steps = sim.registers,0
    while r[24] != 0x1D00:
        if steps >= 2000:
            raise AssertionError('actor pack failed to return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('actor pack left DI/28MHz domain')
        steps += 1
    if r[12] != 0x1FF2 or mem.mmu1 != 68 or mem.mmu2 != 10 or mem.ram != list(ram):
        raise AssertionError('actor pack did not restore mapping/stack/game RAM')
    canvas = b''.join(mem.pages[p] for p in range(112,116))
    expected = bytearray(initial)
    valid = tile < 1024 and flash < 2 and 4 <= stride <= 512 and not (stride & 3 or dest & 3) and dest+7*stride+3 < 32768
    if bool(mem.pages[75][0x1ED7]) == valid:
        raise AssertionError('actor pack guard disagrees')
    allowed = set()
    if valid:
        source = list(ram)
        if raw is not None:
            source[0xDC00+8*tile:0xDC08+8*tile] = raw[:8]
            source[0xFC00+tile] = raw[8]
        pixels = expected_tile(source,tile,flash)
        for y in range(8):
            for x in range(0,8,2):
                a,b = pixels[y*8+x:y*8+x+2]
                a = a+1 if 0 < a < 8 else a
                b = b+1 if 0 < b < 8 else b
                off = dest+y*stride+x//2
                expected[off] = a*16+b
                allowed.add(off)
    if canvas != expected or mem.canvas_writes != allowed:
        raise AssertionError('actor packed pixels or write footprint differ')
    return {'instructions':steps,'equivalent_T':(r[25]+mem.reads)/8,'valid':valid,'canvas':canvas}


class ActorJobMemory(Layer2Memory):
    """Single owned immutable source slot; writes to pinned bytes fail immediately."""
    def __init__(self, ram, op, image, flash, paint, previous, code, bank=122, offset=0, owned=None):
        super().__init__(ram,code,0,0,0,31,0,False)
        self.pages[78] = self.pages.pop(69)
        self.pages[122] = bytearray([0xE3]*8192)
        if previous:
            self.pages[78][0x1E85:0x1E93] = previous[78][0x1E85:0x1E93]
            self.pages[122][:] = previous[122]
        self.pages[78][0x1E80:0x1E85] = bytes((op,image,flash))+paint.to_bytes(2,'little')
        if owned is not None:
            if op != 2 or not 136 <= bank < 216 or not previous or offset+int.from_bytes(previous[78][0x1E89:0x1E8B],'little')>8192:
                raise ValueError('invalid owned source view')
            self.pages[bank] = bytearray(owned[bank])
        elif bank != 122 or offset:
            raise ValueError('unowned source view')
        self.bank = bank
        self.pages[78][0x1E93:0x1E96] = bytes((bank,))+(0x2000+offset).to_bytes(2,'little')
        self.pinned = bool(self.pages[78][0x1E85])
        self.snapshot_writes = set()

    def __getitem__(self, a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        self.reads += 1
        return self.pages[78][a] if a < 8192 else self.pages[self.mmu1][a & 8191] if a < 16384 else self.ram[a]

    def __setitem__(self, a, v):
        if a < 8192 and (0x1E85 <= a < 0x1E93 or 0x1F00 <= a < 0x1FF0):
            self.pages[78][a] = v
        elif 8192 <= a < 16384 and self.mmu1 == 122 and not self.pinned:
            self.pages[122][a & 8191] = v
            self.snapshot_writes.add(a & 8191)
        else:
            raise AssertionError('job wrote pinned bytes, code, game RAM or unowned state')

    def nextreg(self, reg, value):
        if reg != 0x51 or value not in (68,self.bank):
            raise AssertionError('job changed unowned mapping/display register')
        self.mmu1 = value

    def write_port(self, *args):
        raise AssertionError('job changed display/IO')


def run_actor_job(ram, op=0, image=0, flash=0, paint=0, previous=None, code=None, bank=122, offset=0, owned=None):
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    code = bytes.fromhex(load_profile()['hooks']['job']) if code is None else code
    mem = ActorJobMemory(ram,op,image,flash,paint,previous,code,bank,offset,owned)
    regs = [0]*30
    regs[12],regs[14],regs[27] = 0x1FF0,0xFE,2
    sim = simpool.machine(_rw_simulator(),mem,regs,'inferno.actor.job')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    r,steps = sim.registers,0
    syms = {k:int(v,16) for k,v in load_profile()['hooks']['syms'].items()}
    costs = Counter()
    while r[24] != 0x1D00:
        if steps >= 400000:
            raise AssertionError('job failed to return')
        pc,before,reads = r[24],r[25],mem.reads
        sim.opcodes[mem[pc]]()
        kind = ('capture_release' if op != 2 else
                'bitmap_compare' if syms['job_exact_bitmap'] <= pc < syms['job_exact_bitmap_done'] else
                'tile_address_attribute' if syms['job_exact_tile'] <= pc < syms['job_address'] else
                'geometry_parse_compare' if syms['job_exact_walk'] <= pc < syms['job_exact_tile'] or syms['job_address'] <= pc < syms['job_complete'] else
                'setup_finish')
        costs[kind] += (r[25]-before+mem.reads-reads)/8
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('job left DI/28MHz domain')
        steps += 1
    if r[12] != 0x1FF2 or mem.mmu1 != 68 or mem.ram != list(ram):
        raise AssertionError('job did not restore mapping/stack/game RAM')
    state = mem.pages[78]
    size = int.from_bytes(state[0x1E89:0x1E8B],'little')
    if sum(costs.values()) != (r[25]+mem.reads)/8:
        raise AssertionError('source timing attribution does not reconcile')
    return {'pages':mem.pages,'active':state[0x1E85],'done':state[0x1E86],
            'error':state[0x1E87],'match':state[0x1E88],'size':size,
            'stream':bytes(mem.pages[bank][offset:offset+size]),'writes':len(mem.snapshot_writes),
            'equivalent_T':(r[25]+mem.reads)/8,'instructions':steps,
            'cost_components_T':dict(costs)}


def actor_job_tiles(stream):
    """Decode owned serialized bytes, never consult original RAM across a yield."""
    pos,tiles = 1,[]
    page = stream[0] & 3
    while True:
        width = stream[pos]
        pos += 1
        if not width:
            if pos != len(stream):
                raise ValueError('snapshot trailing bytes')
            return tuple(tiles)
        dx,dy = stream[pos:pos+2]
        dx,dy = dx-256 if dx > 127 else dx,dy-256 if dy > 127 else dy
        pos += 2
        for j in range(width):
            tile,raw = stream[pos],bytes(stream[pos+1:pos+10])
            if len(raw) != 9:
                raise ValueError('short snapshot tile')
            tiles.append((dx+j,dy,tile+page*256,raw))
            pos += 10


def prepare_loading_cache(ram):
    """Frozen-live-RAM loading experiment; host scan/selection, assembled workers and owned store.

    No RZX-derived catalogue. Every possible C100 index is scanned at this instant.
    The pause gate is checked separately; a runtime scan/worker driver is still required.
    """
    cache,jobs,contents,locations = {},{},bytearray(80*8192),{}
    owned = run_owned_cache()['pages']
    owned_slots = {}
    owned_cost = 0
    used,cost,tiles_count,pixels_count = 0,0,0,0
    rejected = Counter()
    for image in range(256):
        try:
            actor = actor_descriptor(ram,image)
            key = tuple((x,y,t,raw_tile(ram,t)) for x,y,t in actor['tiles'])
            if not key or key in cache:
                continue
            left,top,width,height,pixels = solid_image(tuple((x,y,raw) for x,y,t,raw in key))
            if width > 1024:
                raise ValueError('canvas stride')
        except (ValueError,IndexError):
            rejected['malformed/unsupported live candidate'] += 1
            continue
        job = run_actor_job(ram,image=image)
        cost += job['equivalent_T']
        if not job['done'] or job['error']:
            rejected['snapshot capacity/record refusal'] += 1
            continue
        if actor_job_tiles(job['stream']) != key:
            raise AssertionError('loading snapshot differs from original')
        size = width*height//2
        needed = len(job['stream'])+size
        if used+needed > len(contents):
            rejected['expanded cache capacity'] += 1
            continue
        canvas = bytes(32768)
        for x,y,t,raw in actor_job_tiles(job['stream']):
            dest = ((y*8-top)*width+x*8-left)//2
            result = run_actor_pack(ram,t,dest,width//2,raw=raw,canvas=canvas)
            if not result['valid']:
                raise AssertionError('loading tile rejected')
            canvas = result['canvas']
            cost += result['equivalent_T']
            tiles_count += 1
        filled = run_actor_fill(canvas,width//2,size)
        cost += filled['equivalent_T']
        actual = bytes(c for b in filled['canvas'][:size] for c in (b >> 4,b & 15))
        if actual != pixels:
            raise AssertionError('loading B pixels differ')
        payload = job['stream']+filled['canvas'][:size]
        stored = run_owned_cache(job['stream'],filled['canvas'][:size],owned,op=1,image=image)
        if stored['error'] or not stored['found']:
            rejected['owned cache capacity/entry refusal'] += 1
            continue
        owned = stored['pages']
        owned_slots[key] = image
        owned_cost += stored['equivalent_T']
        contents[used:used+needed] = payload
        # Host packing of complete owned images in proposed pages 136..215.
        # No display/pattern allocation or runtime readiness flag is published.
        cache[key] = 0
        jobs[key] = {p:job['pages'][p] for p in (78,122)}
        locations[key] = (used+len(job['stream']),size)
        used += needed
        pixels_count += len(pixels)
    return cache,jobs,{'prepared_images':len(cache),'packed_source_and_canvas_bytes':used,
                      'cache_capacity_bytes':len(contents),'assembled_tiles':tiles_count,
                      'assembled_B_pixels':pixels_count,'preparation_cpu_ms':cost/3500,
                      'owned_store_cpu_ms':owned_cost/3500,
                      'rejected':dict(rejected),
                      'scope':'frozen live-table loading experiment with assembled snapshot/colour/B and owned high-RAM store/candidate dispatch; host scan/content selection; excludes scan, zeroing, external wrappers and hardware stalls'},(bytes(contents[:used]),locations,owned,owned_slots)


class OwnedCacheMemory:
    """Physical high-RAM store; candidate dispatch never means exact-valid or display-ready."""
    def __init__(self, source, canvas, previous, code, op, image, flash, paint, current, pending):
        self.pages = ({p:bytearray(v) for p,v in previous.items()} if previous else
                      {p:bytearray(8192) for p in (79,122,112,113,114,115,*range(136,216))})
        self.pages[79][:len(code)] = code
        self.pages[79][0x1FF0:0x1FF2] = b'\x00\x1D'
        self.pages[122][:] = source.ljust(8192,b'\0')
        for i in range(4):
            self.pages[112+i][:] = canvas[i*8192:(i+1)*8192].ljust(8192,b'\0')
        self.pages[79][0x1E80:0x1E8B] = (bytes((op,image,flash))+paint.to_bytes(2,'little')+
                len(source).to_bytes(2,'little')+len(canvas).to_bytes(2,'little')+bytes((current,pending)))
        self.mmu1,self.mmu2,self.reads = 68,10,0
        self.writes,self.maps = [],[]

    def __getitem__(self,a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        self.reads += 1
        if a < 8192:
            return self.pages[79][a]
        if a < 16384:
            return self.pages[self.mmu1][a & 8191]
        if a < 24576:
            return self.pages[self.mmu2][a & 8191]
        raise AssertionError('owned cache read original RAM')

    def __setitem__(self,a,v):
        if a < 8192 and (0x800 <= a < 0x1800 or 0x1E8B <= a < 0x1EA0 or 0x1F00 <= a < 0x1FF0):
            self.pages[79][a] = v
        elif 16384 <= a < 24576 and 136 <= self.mmu2 < 216:
            self.pages[self.mmu2][a & 8191] = v
        else:
            raise AssertionError('owned cache wrote source/game/code/staging RAM')
        self.writes.append((a,v,self.mmu2))

    def nextreg(self,reg,value):
        if reg == 0x51 and value in (68,122,112,113,114,115):
            self.mmu1 = value
        elif reg == 0x52 and (value == 10 or 136 <= value < 216):
            self.mmu2 = value
        else:
            raise AssertionError('owned cache changed unowned register/mapping')
        self.maps.append((reg,value))

    def read_port(self,*args):
        raise AssertionError('owned cache read IO')

    def write_port(self,*args):
        raise AssertionError('owned cache wrote IO')


def run_owned_cache(source=b'',canvas=b'',previous=None,op=0,image=0,flash=0,paint=0,current=0,pending=0,code=None):
    from . import simpool,z80n
    from .dizzy6 import _rw_simulator
    if len(source)>8192 or len(canvas)>32768:
        raise ValueError('owned input capacity')
    code = bytes.fromhex(load_profile()['hooks']['owned']) if code is None else code
    mem = OwnedCacheMemory(source,canvas,previous,code,op,image,flash,paint,current,pending)
    regs = [0]*30
    regs[12],regs[14],regs[27] = 0x1FF0,0xFE,2
    sim = simpool.machine(_rw_simulator(),mem,regs,'inferno.owned.cache')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    steps = 0
    while sim.registers[24] != 0x1D00:
        if steps > 1000000:
            raise AssertionError('owned cache failed to return')
        sim.opcodes[mem[sim.registers[24]]]()
        if sim.registers[26]:
            raise AssertionError('owned cache enabled interrupts')
        steps += 1
    if sim.registers[12] != 0x1FF2 or (mem.mmu1,mem.mmu2) != (68,10):
        raise AssertionError('owned cache failed to restore stack/mappings')
    state = mem.pages[79]
    entry = bytes(state[0x800+16*image:0x810+16*image])
    return {'pages':mem.pages,'error':state[0x1E8B],'found':state[0x1E8C],
            'entry':entry,'writes':mem.writes,'maps':mem.maps,
            'equivalent_T':(sim.registers[25]+mem.reads)/8}


def owned_payload(pages,page,offset,size):
    result = bytearray()
    while size:
        count = min(size,8192-offset)
        result += pages[page][offset:offset+count]
        page,offset,size = page+1,0,size-count
    return bytes(result)


def owned_cache_checks():
    counts = Counter()
    reset = run_owned_cache()
    source,canvas = bytes(range(256))*3,bytes(range(255,-1,-1))*128
    first = run_owned_cache(source,canvas,reset['pages'],op=1,image=255,flash=1,paint=513)
    assert first['found'] and not first['error']
    def payloads(result):
        e = result['entry']
        return (owned_payload(result['pages'],e[1],int.from_bytes(e[2:4],'little'),int.from_bytes(e[4:6],'little')),
                owned_payload(result['pages'],e[6],int.from_bytes(e[7:9],'little'),int.from_bytes(e[9:11],'little')))
    assert payloads(first) == (source,canvas)
    counts['source and full canvas exact across page boundaries'] += 1
    payload_writes = [i for i,(a,v,p) in enumerate(first['writes']) if a>=16384]
    publication = [i for i,(a,v,p) in enumerate(first['writes']) if a==0x17F0 and v==1]
    assert len(publication)==1 and publication[0]>max(payload_writes)
    counts['valid published after complete payload'] += 1
    for kw in ({'flash':0,'paint':513},{'flash':1,'paint':512},{'flash':1,'paint':257}):
        miss=run_owned_cache(previous=first['pages'],op=2,image=255,**kw)
        assert not miss['found'] and not miss['error']
        assert miss['pages'][79][0x800:0x1800] == first['pages'][79][0x800:0x1800]
        counts['phase/paint candidate rejection'] += 1
    hit=run_owned_cache(previous=first['pages'],op=2,image=255,flash=1,paint=513)
    assert hit['found'] and not hit['error'] and payloads(hit)==(source,canvas)
    counts['immutable dispatch after scratch mutation'] += 1
    for owners in ({'current':1},{'pending':1}):
        denied=run_owned_cache(previous=first['pages'],image=255,**owners)
        assert denied['error'] and payloads(denied)==(source,canvas)
        counts['owned reset rejected'] += 1
    denied=run_owned_cache(b'x',b'y',first['pages'],op=1,image=255)
    assert denied['error'] and payloads(denied)==(source,canvas)
    counts['immutable entry overwrite rejected'] += 1
    # Exact final-byte capacity and refusal retain metadata/payload/cursor.
    edge={p:bytearray(v) for p,v in reset['pages'].items()}
    edge[79][0x1E8D:0x1E90]=bytes((215,0,0))
    full=run_owned_cache(bytes(8192),previous=edge,op=1)
    assert full['found'] and not full['error']
    assert full['pages'][79][0x1E8D:0x1E90]==bytes((216,0,0))
    refused=run_owned_cache(b'x',previous=full['pages'],op=1,image=1)
    assert refused['error'] and not refused['entry'][0]
    assert refused['pages'][79][0x800:0x1800]==full['pages'][79][0x800:0x1800]
    assert not any(a>=16384 for a,v,p in refused['writes'])
    counts['exact cache capacity and unpublished overflow'] += 1
    # Force alignment to keep the exact source stream within one mapped page.
    edge={p:bytearray(v) for p,v in reset['pages'].items()}
    edge[79][0x1E8D:0x1E90]=bytes((136,255,31))
    aligned=run_owned_cache(b'ab',b'cd',edge,op=1)
    assert aligned['entry'][1:4]==bytes((137,0,0)) and payloads(aligned)==(b'ab',b'cd')
    counts['single-page source alignment'] += 1
    for kw in ({'op':3},{'op':1},{'op':1,'source':b'x','flash':2}):
        denied=run_owned_cache(previous=reset['pages'],**kw)
        assert denied['error'] and not any(a>=16384 for a,v,p in denied['writes'])
        counts['invalid request unpublished'] += 1
    # Missing final publication and missing phase check must be observable.
    code=bytes.fromhex(load_profile()['hooks']['owned'])
    publish=bytes.fromhex('3601C3')
    assert code.count(publish)==1
    broken=run_owned_cache(b'a',b'b',reset['pages'],op=1,code=code.replace(publish,bytes.fromhex('3600C3')))
    assert not broken['found']
    counts['missing publication control detected'] += 1
    return {'counts':dict(counts),'dispatch_ms':hit['equivalent_T']/3500,
            'loading_store_ms':first['equivalent_T']/3500,'capacity_bytes':80*8192,
            'scope':'assembled owned high-RAM append/store and candidate dispatch; exact live validation required separately; no game wrapper, loading UI, pattern ownership integration or display readiness'}


def actor_job_checks():
    counts,peaks = Counter(),Counter()
    ram = [0]*65536
    ram[0xC100:0xC102] = [0,0xD0]
    # Overwrite order, negative offsets, width one, repeated tile, FLASH bitmap.
    ram[0xD000:0xD00C] = [3,2,255,254,0,1,1,0,254,0,0,0]
    for t in (768,769):
        ram[0xDC00+8*t:0xDC08+8*t] = [255,129,129,129,129,129,129,255]
        ram[0xFC00+t] = 0xC2+t%2
    def capture(source=ram, **kw):
        result = run_actor_job(source,**kw)
        assert result['done'] == result['active'] == 1 and not result['error']
        peaks['capture_ms'] = max(peaks['capture_ms'],result['equivalent_T']/3500)
        return result
    job = capture()
    want = tuple((x,y,t,raw_tile(ram,t)) for x,y,t in actor_descriptor(ram,0)['tiles'])
    assert actor_job_tiles(job['stream']) == want
    # Validate straight from a nonzero-offset owned high page, after scratch changes.
    empty = run_owned_cache()['pages']
    prefix = run_owned_cache(b'prefix',b'canvas',empty,op=1,image=1)
    stored = run_owned_cache(job['stream'],b'pixels',prefix['pages'],op=1)
    entry = stored['entry']
    owned_view = dict(bank=entry[1],offset=int.from_bytes(entry[2:4],'little'),owned=stored['pages'])
    assert owned_view['offset'] > 0
    direct = run_actor_job(ram,op=2,previous=job['pages'],**owned_view)
    assert direct['match'] and direct['stream']==job['stream'] and not direct['writes']
    for address in (0xD002,0xDC00+8*768,0xFC00+768):
        changed = list(ram)
        changed[address] ^= 1
        assert not run_actor_job(changed,op=2,previous=job['pages'],**owned_view)['match']
    counts['direct owned high-RAM exact validation and live mutations'] += 4
    counts['ordered live geometry/bitmap/attribute capture'] += 1
    # Pinned worker consumes only copied raw bytes after all original sources change.
    changed = [v ^ 255 for v in ram]
    for x,y,t,raw in want:
        run_actor_pack(changed,t,raw=raw)
        counts['pinned assembled tile after original mutation'] += 1
    for op in (0,3,255):
        rejected = run_actor_job(ram,op=op,previous=job['pages'])
        assert rejected['error'] and rejected['done'] and rejected['active'] and not rejected['writes']
        assert rejected['stream'] == job['stream']
        counts['pinned/invalid operation rejection'] += 1
    matched = run_actor_job(ram,op=2,previous=job['pages'])
    assert matched['match'] and not matched['error'] and not matched['writes']
    peaks['exact_hit_ms'] = matched['equivalent_T']/3500
    # Every serialized byte matters, including same-address source mutations and terminator.
    addresses = [0xD000+i for i in range(11)] + [0xDC00+8*t+i for t in (768,769) for i in range(8)] + [0xFC00+768,0xFC00+769]
    for addr in addresses:
        source = list(ram)
        source[addr] ^= 1
        miss = run_actor_job(source,op=2,previous=job['pages'])
        assert not miss['match'] and not miss['writes'] and miss['stream'] == job['stream']
        counts['live content mutation rejected'] += 1
    for kw in ({'flash':1},{'paint':1},{'paint':256}):
        miss = run_actor_job(ram,op=2,previous=job['pages'],**kw)
        assert not miss['match'] and not miss['writes']
        counts['phase/paint generation rejected'] += 1
    # Different pointer/image is fine only when complete contents are identical.
    source = list(ram)
    source[0xD100:0xD10C] = source[0xD000:0xD00C]
    source[0xC1FF],source[0xC100] = 0,0xD1
    assert run_actor_job(source,op=2,image=255,previous=job['pages'])['match']
    counts['relocated content and C1FF wrap'] += 1
    release = run_actor_job(ram,op=1,previous=job['pages'])
    assert not release['active'] and not release['done'] and not release['writes']
    assert capture(previous=release['pages'])['stream'] == job['stream']
    counts['release and recapture'] += 1
    malformed = []
    for pointer in (0,0x3FFF,0xFFFF):
        source = list(ram)
        source[0xC100:0xC102] = [pointer & 255,pointer >> 8]
        malformed.append(source)
    source = list(ram)
    source[0xD001] = 129
    malformed.append(source)
    source = list(ram)
    body = [0]+[v for row in range(256) for v in (1,0,0,0)]+[0]
    source[0xD000:0xD000+len(body)] = body
    malformed.append(source)
    for source in malformed:
        bad = run_actor_job(source)
        assert bad['error'] and not bad['done'] and not bad['active']
        counts['malformed unpublished'] += 1
    for kw in ({'flash':2},{'op':2}):
        bad = run_actor_job(ram,**kw)
        assert bad['error'] and not bad['done'] and not bad['writes']
        counts['invalid phase/inactive validation'] += 1
    # Header + 816 ten-byte tile payloads + ten three-byte rows + zero = 8192.
    source = list(ram)
    body = [0]
    remaining = 816
    for row in range(10):
        width = min(128,remaining-(9-row))
        body += [width,0,row]+[0]*width
        remaining -= width
    body += [0]
    source[0xD000:0xD000+len(body)] = body
    edge = capture(source)
    assert edge['size'] == 8192 and edge['writes'] == 8192
    assert run_actor_job(source,op=2,previous=edge['pages'])['match']
    peaks['capacity_exact_hit_ms'] = run_actor_job(source,op=2,previous=edge['pages'])['equivalent_T']/3500
    counts['exact 8K snapshot boundary'] += 1
    capacity_source = source
    # Row spans ending at the last RAM byte and stored page boundary. Relocation
    # may wrap midway through geometry/IDs; reject it without accepting a prefix.
    for width in (1,2,16,128):
        body = [0,width,0,0]+[0]*width+[0]
        source = list(ram)
        pointer = 65536-len(body)
        source[pointer:] = body
        source[0xC100:0xC102] = [pointer & 255,pointer >> 8]
        boundary = run_actor_job(source)
        assert boundary['done'] and not boundary['error']
        offset = 8192-boundary['size']
        owned = {136:bytearray([0xE3]*8192)}
        owned[136][offset:] = boundary['stream']
        exact = run_actor_job(source,op=2,previous=boundary['pages'],bank=136,offset=offset,owned=owned)
        assert exact['match'] and not exact['error'] and not exact['writes']
        for shift in (1,2,3):
            wrapped = list(source)
            wrapped[pointer+shift:] = body[:-shift]
            wrapped[0xC100:0xC102] = [(pointer+shift)&255,(pointer+shift)>>8]
            miss = run_actor_job(wrapped,op=2,previous=boundary['pages'],bank=136,offset=offset,owned=owned)
            assert not miss['match'] and not miss['writes']
        counts['row spans at RAM/store end and wrapped relocations'] += 4
    # Restore the capacity case after the independent row-boundary fixtures.
    source = capacity_source
    source[0xD001] += 1
    overflow = run_actor_job(source)
    assert overflow['error'] and not overflow['done'] and not overflow['active']
    counts['overflow unpublished'] += 1
    code = bytes.fromhex(load_profile()['hooks']['job'])
    # Skip byte comparison: own pinned tables remain intact, live mutation must then be missed.
    old = bytes.fromhex('B9 C2')
    assert code.count(old) == 7
    broken = code.replace(old,bytes.fromhex('BF C2'))
    source = list(ram)
    source[0xD002] ^= 1
    assert run_actor_job(source,op=2,previous=job['pages'],code=broken)['match']
    old_block = bytes.fromhex('1ABE C2')
    assert code.count(old_block) == 16
    broken_block = code.replace(old_block,bytes.fromhex('1ABF C2'))
    for row in range(8):
        source = list(ram)
        source[0xDC00+8*768+row] ^= 1
        assert run_actor_job(source,op=2,previous=job['pages'],code=broken_block)['match']
        counts['missing bitmap comparison control detected'] += 1
    counts['missing exact comparison control detected'] += 1
    return {'counts':dict(counts),'timing':dict(peaks),'snapshot_capacity':8192,
            'scope':'assembled standalone pinned snapshot/exact validation and pinned tile consumer; no installed cache, scheduler, wrapper or display; software timings only'}


@lru_cache(maxsize=1)
def actor_fill_lookup():
    """Generic zero-pixel flags, final colouring and eight-pixel horizontal closure."""
    flags = bytes((2 if n >> 4 == 0 else 0) | (1 if n & 15 == 0 else 0) for n in range(256))
    finish,reach = bytearray(),bytearray()
    for exterior in range(4):
        for n in range(256):
            a,b = n >> 4,n & 15
            finish.append((a if a or exterior & 2 else 1)*16+(b if b or exterior & 1 else 1))
    for passable in range(256):
        for seeds in range(256):
            value = seeds & passable
            while True:
                new = (value | value << 1 | value >> 1) & passable
                if new == value:
                    break
                value = new
            reach.append(value)
    return flags,bytes(finish),bytes(reach)


class ActorFillMemory(ActorPackMemory):
    """Private worker page 76; no hardware pattern or display ownership."""
    def __init__(self, canvas, stride, size, done, code, budget):
        super().__init__([0]*65536,0,0,4,0,code,canvas)
        self.pages[76] = self.pages.pop(75)
        # This worker owns 0000..05FF; inherited textmap tables at 0400 do not apply.
        self.pages[76][:len(code)] = code
        flags,finish,reach = actor_fill_lookup()
        self.pages[76][0x600:0x700] = flags
        self.pages[76][0x800:0xC00] = finish
        self.pages.update({p:bytearray(reach[(p-128)*8192:(p-127)*8192]) for p in range(128,136)})
        self.pages.update({p:bytearray([0xE3])*8192 for p in (116,117)})
        self.mmu3,self.mask_writes = 11,set()
        self.pages[76][0x1E90:0x1E95] = stride.to_bytes(2,'little')+size.to_bytes(2,'little')+bytes((done,))
        self.pages[76][0x1EA1] = budget

    def __getitem__(self, a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        if a < 0x2000:
            self.reads += 1
            return self.pages[76][a]
        if 0x6000 <= a < 0x8000 and self.mmu3 != 11:
            self.reads += 1
            return self.pages[self.mmu3][a & 8191]
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if a < 0x2000:
            if not (0x1E90 <= a < 0x1EAA or 0x1FC0 <= a < 0x1FF0):
                raise AssertionError('actor fill changed code, table or unowned state at %04X' % a)
            self.pages[76][a] = v
        elif 0x4000 <= a < 0x6000 and self.mmu2 in (116,117):
            self.mask_writes.add((self.mmu2,a & 8191))
            self.pages[self.mmu2][a & 8191] = v
        else:
            super().__setitem__(a,v)

    def nextreg(self, reg, value):
        if reg == 0x52 and value in (116,117):
            self.mmu2 = value
        elif reg == 0x51 and value == 116:
            self.mmu1 = value
        elif reg == 0x53 and (value == 11 or 128 <= value <= 135):
            self.mmu3 = value
        else:
            super().nextreg(reg,value)


def run_actor_fill(canvas, stride, size, code=None, done=0, budget=4, command=0):
    """Run assembled whole-image classifier; pixel flood oracle uses independent traversal."""
    from . import simpool,z80n
    from .dizzy6 import _rw_simulator
    code = bytes.fromhex(load_profile()['hooks']['fill']) if code is None else code
    mem = ActorFillMemory(canvas,stride,size,done,code,budget)
    regs = [0]*30
    regs[12],regs[14],regs[27] = 0x1FF0,0xFE,2
    sim = simpool.machine(_rw_simulator(),mem,regs,'inferno.actor.fill')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    r,steps,calls,peak = sim.registers,0,0,0
    worker = mem.pages[76]
    worker[0x1EA0] = command
    while True:
        # Deliberately destroy the previous call's registers. Only the owned coroutine
        # context may survive a yield; a real wrapper restores the game's registers.
        for index in range(12):
            r[index] = (calls*37+index*13) & 255
        r[12],r[24] = 0x1FF0,0x400
        before = r[25]+mem.reads
        while r[24] != 0x1D00:
            if steps >= 60_000_000:
                raise AssertionError('actor fill failed to converge')
            sim.opcodes[mem[r[24]]]()
            if r[26] or mem.nr[0x07] != 3:
                raise AssertionError('actor fill left DI/28MHz domain')
            steps += 1
        peak = max(peak,(r[25]+mem.reads-before)/8)
        calls += 1
        if r[12] != 0x1FF2 or mem.mmu1 != 68 or mem.mmu2 != 10 or mem.mmu3 != 11:
            raise AssertionError('actor fill failed stack/mapping/game RAM restore')
        if worker[0x1E94] or worker[0x1E95]:
            break
        if worker[0x1EA3] != 1:
            raise AssertionError('actor fill yielded without a private active job')
        worker[0x1EA0] = 1
    valid = command == 0 and not done and 1 <= budget <= 16 and 4 <= stride <= 512 and not stride & 3 and 0 < size <= 32768 and not size % stride
    if any(mem.ram):
        raise AssertionError('actor fill touched original game RAM')
    if bool(worker[0x1E95]) == valid or bool(worker[0x1E94]) != bool(valid or done):
        raise AssertionError('actor fill guard/readiness disagrees')
    actual = b''.join(mem.pages[p] for p in range(112,116))
    expected = bytearray(canvas)
    if valid:
        pixels = bytearray(c for n in canvas[:size] for c in (n >> 4,n & 15))
        if 1 in pixels:
            raise AssertionError('unclassified canvas contains reserved colour 1')
        width = stride*2
        todo = list(range(width))+list(range(len(pixels)-width,len(pixels)))
        todo.extend(y*width+x for y in range(size//stride) for x in (0,width-1))
        outside = set()
        while todo:
            at = todo.pop()
            if pixels[at] or at in outside:
                continue
            outside.add(at)
            x = at % width
            if x:
                todo.append(at-1)
            if x+1 < width:
                todo.append(at+1)
            if at >= width:
                todo.append(at-width)
            if at+width < len(pixels):
                todo.append(at+width)
        for i,c in enumerate(pixels):
            if not c and i not in outside:
                pixels[i] = 1
        expected[:size] = bytes(pixels[i]*16+pixels[i+1] for i in range(0,len(pixels),2))
        if mem.canvas_writes != set(range(size)):
            raise AssertionError('actor fill did not cover exactly the whole canvas')
        if mem.mask_writes != {(p,a) for p in (116,117) for a in range(size//4)}:
            raise AssertionError('actor fill changed unowned mask bytes')
    elif mem.canvas_writes or mem.mask_writes:
        raise AssertionError('actor fill rejected after canvas writes')
    if actual != expected:
        raise AssertionError('actor whole-image fill pixels differ')
    return {'valid':valid,'canvas':actual,'instructions':steps,'equivalent_T':(r[25]+mem.reads)/8,
            'service_calls':calls,'max_service_ms':peak/3500,
            'sweep_pairs':int.from_bytes(worker[0x1E9E:0x1EA0],'little')}


def actor_pack_checks():
    counts,peak = Counter(),0
    ram = [0]*65536
    # Every attribute/phase in assembled code, including both black brightnesses.
    for attr in range(256):
        tile = (attr*37) & 1023
        ram[0xDC00+tile*8:0xDC08+tile*8] = [0,255,85,170,129,126,24,231]
        ram[0xFC00+tile] = attr
        for phase in (0,1):
            result = run_actor_pack(ram,tile,8188,132,phase)
            peak = max(peak,result['equivalent_T'])
            pinned = run_actor_pack([0]*65536,tile,8188,132,phase,raw=raw_tile(ram,tile))
            assert pinned['canvas'] == result['canvas']
            counts['assembled pinned attribute/phase cases'] += 1
            counts['assembled attribute/phase cases'] += 1
    # Every bitmap value and colour pair against independent original-tile pixels.
    table = actor_row_lookup()
    for attr in range(128):
        for row in range(256):
            pixel = tile_pixels(bytes([row]*8+[attr]))[:8]
            pixel = bytes(c+1 if 0<c<8 else c for c in pixel)
            want = bytes(pixel[i]*16+pixel[i+1] for i in range(0,8,2))
            off = attr*1024+row*4
            assert table[off:off+4] == want
            counts['lookup rows'] += 1
    for tile,dest,stride in ((0,0,4),(1023,32736,4),(512,24572,512),(1,16380,4)):
        result = run_actor_pack(ram,tile,dest,stride)
        peak = max(peak,result['equivalent_T'])
        counts['source/canvas boundary cases'] += 1
    for kw in ({'tile':1024},{'tile':65535},{'dest':32740},{'dest':65532},
               {'dest':2},{'stride':0},{'stride':3},{'stride':513},{'stride':65532},{'flash':2}):
        assert not run_actor_pack(ram,**kw)['valid']
        counts['rejected before canvas writes'] += 1
    for origin in range(256):
        for length in (0,1,2,18,32,128,255,256,383):
            for limit in (18,32):
                want = any(((origin+x)&255) < limit for x in range(length))
                actor = {'x':origin if limit == 32 else 0,'y':origin if limit == 18 else 0}
                got = canvas_visible(actor,0,0,length*8 if limit == 32 else 8,length*8 if limit == 18 else 8)
                assert got == want
                counts['conservative wrapped bounds cases (model)'] += 1
    code = bytes.fromhex(load_profile()['hooks']['pack'])
    ram[0xDC00:0xDC08],ram[0xFC00] = [129]*8,0xC7
    for old,new in ((bytes.fromhex('C660ED9252'),bytes.fromhex('C661ED9252')),
                    (bytes.fromhex('ED44A107ED44'),bytes.fromhex('ED44A107AF00')),
                    (bytes.fromhex('ED915144'),bytes.fromhex('ED915170'))):
        assert code.count(old) == 1
        try:
            run_actor_pack(ram,flash=1,code=code.replace(old,new))
        except AssertionError:
            counts['negative controls detected'] += 1
        else:
            raise AssertionError('actor pack negative control passed')
    return {'counts':dict(counts),'max_equivalent_T':peak,'max_ms':peak/3500,
            'lookup_bytes':len(table),'canvas_bytes':32768,
            'scope':'assembled colour expansion only; whole-image fill/cache/uploads and frame integration remain open'}


def actor_fill_checks():
    """Boundary, seams, winding exterior paths and one-shot classification guards."""
    import random
    counts,peak,passes,service_peak = Counter(),0,0,0
    reach = actor_fill_lookup()[2]
    for passable in range(256):
        for seeds in range(256):
            todo = [x for x in range(8) if seeds & (128 >> x)]
            seen = set()
            while todo:
                x = todo.pop()
                if x in seen or not passable & (128 >> x):
                    continue
                seen.add(x)
                todo.extend(n for n in (x-1,x+1) if 0 <= n < 8)
            assert reach[passable*256+seeds] == sum(128 >> x for x in seen)
            counts['independent horizontal connectivity entries'] += 1
    cases = []
    def add(name,width,height,pixels):
        data = bytes(pixels[i]*16+pixels[i+1] for i in range(0,len(pixels),2))
        cases.append((name,width//2,len(data),data+bytes([0xE3])*(32768-len(data))))
    for width,height in ((8,1),(16,16),(136,80),(8,8192),(1024,64)):
        for colour in (0,7):
            add('uniform',width,height,bytes([colour])*(width*height))
    for width,height in ((16,16),(32,24),(136,80)):
        pixels = bytearray(width*height)
        for y in range(1,height-1):
            for x in range(1,width-1):
                if x in (1,width-2) or y in (1,height-2):
                    pixels[y*width+x] = 14
        add('closed seam',width,height,pixels)
        pixels[width+width//2] = 0
        add('open seam',width,height,pixels)
    width,height = 32,32
    pixels = bytearray([9])*(width*height)
    pixels[1] = 0
    for y in range(1,height-1,2):
        for x in range(1,width-1):
            pixels[y*width+x] = 0
        if y+1 < height-1:
            pixels[(y+1)*width+(width-2 if (y//2)%2 == 0 else 1)] = 0
    add('winding exterior',width,height,pixels)
    rng = random.Random(0xB1AC)
    for n in range(12):
        width,height = 8*(1+n%4),8*(1+n%3)
        add('random',width,height,[rng.choice((0,0,0,2,3,8,9,15)) for _ in range(width*height)])
    fixture = None
    measurements = []
    for name,stride,size,canvas in cases:
        result = run_actor_fill(canvas,stride,size)
        peak,passes = max(peak,result['equivalent_T']),max(passes,result['sweep_pairs'])
        service_peak = max(service_peak,result['max_service_ms'])
        counts[name] += 1
        measurements.append({'case':name,'width':stride*2,'height':size//stride,
                             'added_ms':result['equivalent_T']/3500,'sweep_pairs':result['sweep_pairs'],
                             'service_calls':result['service_calls'],'max_service_ms':result['max_service_ms']})
        if name == 'winding exterior':
            fixture = (canvas,stride,size)
            assert result['sweep_pairs'] > 2
        if name == 'closed seam' and size == 128:
            assert result['canvas'][3*stride+3] == 0x11
    canvas = bytes([0xE3])*32768
    for stride,size,done in ((0,128,0),(3,128,0),(516,128,0),(4,0,0),
                             (4,32769,0),(12,128,0),(4,128,1)):
        assert not run_actor_fill(canvas,stride,size,done=done)['valid']
        counts['reject before writes'] += 1
    for budget in (0,17,255):
        assert not run_actor_fill(canvas,4,32,budget=budget)['valid']
        counts['quota rejects before writes'] += 1
    for command in (1,2,255):
        assert not run_actor_fill(canvas,4,32,command=command)['valid']
        counts['inactive/invalid resume rejects'] += 1
    for budget in (1,2,8,16):
        result = run_actor_fill(*fixture,budget=budget)
        counts['quota / clobbered-register resume cases'] += 1
        assert result['max_service_ms'] < 0.1+0.075*budget
    code = bytes.fromhex(load_profile()['hooks']['fill'])
    # Each mutation uses the broken worker's own lookup/scratch, never restores good state.
    for old,new in ((bytes.fromhex('3EFF'),bytes.fromhex('3E00')),
                    (bytes.fromhex('FE01'),bytes.fromhex('FE02')),
                    (bytes.fromhex('ED915144'),bytes.fromhex('ED915170')),
                    (bytes.fromhex('FDE1DDE1E1D1C1F1C9'),bytes.fromhex('FDE1DDE1E1D1C100C9'))):
        assert old in code
        try:
            run_actor_fill(*fixture,code=code.replace(old,new,1))
        except AssertionError:
            counts['negative controls detected'] += 1
        else:
            raise AssertionError('actor fill negative control passed')
    assert service_peak < 0.35
    return {'counts':dict(counts),'max_ms':peak/3500,'max_sweep_pairs':passes,
            'four_unit_service_max_ms':service_peak,'cases':measurements,
            'lookup_bytes':65536+1024+256,'mask_bytes':16384,
            'scope':'assembled resumable whole-image B fill in private page 76/canvas; fixed work quota; no installed scheduler/cache/uploads/display or hardware timing'}


class ActorPhysicalRAM:
    """SRAM physical aperture; explicitly excludes firmware and BRAM aliases."""
    def __init__(self, owner, source_page, dest_page):
        self.owner,self.source,self.dest = owner,source_page,dest_page

    def __len__(self):
        return 0x200000

    def __getitem__(self, address):
        page,off = divmod(address-0x40000,8192)
        if page != self.source or not 136 <= page <= 223:
            raise AssertionError('physical read outside owned high source')
        return self.owner.pages[page][off]

    def __setitem__(self, address, value):
        page,off = divmod(address-0x40000,8192)
        if page != self.dest or not 216 <= page <= 223:
            raise AssertionError('physical write outside owned high staging')
        self.owner.pages[page][off] = value
        self.owner.writes.add(off)


class ActorBlitMemory:
    """Guarded Inferno MMU/pattern adapter for the shared synchronous DMA model."""
    def __init__(self, code, job, core, hwim2, source, current, pending):
        from .dma import DMA
        self.pages = {68:bytearray(8192),77:bytearray(8192)}
        self.pages[77][:len(code)] = code
        self.pages[77][0x1FF0:0x1FF2] = b'\x00\x1D'
        self.pages[77][0x1F00:0x1F10] = current.to_bytes(8,'little')+pending.to_bytes(8,'little')
        self.pages[job['source_page']] = bytearray(source)
        self.pages[job['dest_page']] = bytearray([0xE3])*8192
        data = bytes((job['source_page'],job['dest_page']))
        data += b''.join(job[k].to_bytes(2,'little') for k in ('source','dest','width','astride','bstride'))
        data += bytes(job[k] for k in ('rows','op','slot','owned','policy'))
        self.pages[77][0x1E00:0x1E11] = data
        self.mmu1,self.mmu2,self.selected = 68,10,0
        self.nr = {1:core,0xC0:hwim2,7:3}
        self.reads,self.in_dma,self.writes = 0,False,set()
        self.patterns,self.pattern_at,self.pattern_writes = bytearray([0xE3])*16384,0,[]
        self.current,self.pending = current,pending
        syms = load_profile()['hooks']['syms']
        self.mutable = {int(syms['hlib_dma_policy'],16),int(syms['hlib_dma_cap'],16)}
        for key in ('sp_src','row_src','row_len','row_dst','rect_src','rect_dst','rect_width',
                    'rect_rows','rect_astride','rect_bstride'):
            off = int(syms['hlib_dma_'+key],16)
            self.mutable.update((off,off+1))
        for key in ('src','dst','ahi','bhi','width','rows','astride','bstride'):
            off = int(syms['blit_phys_'+key],16)
            self.mutable.add(off)
            if key not in ('ahi','bhi'):
                self.mutable.add(off+1)
        self.dma = DMA(self.__getitem__,self.__setitem__,self.pattern_out,blitter=0x33 <= core < 0xFF,
                       physical=ActorPhysicalRAM(self,job['source_page'],job['dest_page']))

    def __getitem__(self, a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        if not self.in_dma:
            self.reads += 1
        if a < 8192:
            return self.pages[77][a]
        if a < 16384:
            return self.pages[self.mmu1][a & 8191]
        if a < 24576 and self.mmu2 != 10:
            return self.pages[self.mmu2][a & 8191]
        return 0

    def __setitem__(self, a, v):
        if a < 8192 and (a in self.mutable or 0x1E11 <= a < 0x1E18 or 0x1FC0 <= a < 0x1FF0):
            self.pages[77][a] = v
        elif 0x4000 <= a < 0x6000 and self.mmu2 in (*range(112,116),*range(118,122),*range(216,224)):
            self.pages[self.mmu2][a & 8191] = v
            self.writes.add(a & 8191)
        else:
            raise AssertionError('actor blit wrote source, game RAM, code or unowned storage')

    def nextreg(self, reg, value):
        if reg == 0x51 and (value == 68 or 112 <= value <= 115 or 136 <= value <= 223):
            self.mmu1 = value
        elif reg == 0x52 and value in (10,*range(112,116),*range(118,122),*range(216,224)):
            self.mmu2 = value
        else:
            raise AssertionError('actor blit changed unowned Next register')

    def read_port(self, regs, port):
        if port != 0x253B or self.selected not in self.nr:
            raise AssertionError('actor blit read an unowned port')
        return self.nr[self.selected]

    def pattern_out(self, port, value):
        if port & 255 != 0x5B:
            raise AssertionError('actor blit wrote non-pattern I/O')
        pair = self.pattern_at//256
        if pair >= 64 or (self.current | self.pending) & (1 << pair):
            raise AssertionError('actor blit overwrote current/pending hardware patterns')
        self.patterns[self.pattern_at] = value
        self.pattern_writes.append(self.pattern_at)
        self.pattern_at += 1

    def write_port(self, regs, port, value, *args):
        if port == 0x243B:
            self.selected = value
        elif port == 0x303B:
            self.pattern_at = (value & 63)*256+(128 if value & 128 else 0)
        elif port & 255 == 0x5B:
            self.pattern_out(port,value)
        elif port & 255 == 0x6B:
            self.in_dma = True
            try:
                self.dma.feed(value)
            finally:
                self.in_dma = False
        else:
            raise AssertionError('actor blit changed unowned I/O')


def run_actor_blit(core=0x33, hwim2=0, current=0, pending=0, code=None, **kw):
    from . import simpool,z80n
    from .dizzy6 import _rw_simulator
    job = dict(source_page=136,dest_page=118,source=3,dest=819,width=8,astride=8,
               bstride=80,rows=16,op=0,slot=7,owned=1,policy=2)
    job.update(kw)
    code = bytes.fromhex(load_profile()['hooks']['blit']) if code is None else code
    source = bytes((i*37+(i >> 8)) & 255 for i in range(8192))
    mem = ActorBlitMemory(code,job,core,hwim2,source,current,pending)
    regs = [0]*30
    regs[12],regs[14],regs[24],regs[27] = 0x1FF0,0xFE,0x800,2
    sim = simpool.machine(_rw_simulator(),mem,regs,'inferno.actor.blit')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    r,steps = sim.registers,0
    while r[24] != 0x1D00:
        if steps >= 100000:
            raise AssertionError('actor blit did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[7] != 3:
            raise AssertionError('actor blit left DI/28MHz domain')
        steps += 1
    if r[12] != 0x1FF2 or mem.mmu1 != 68 or mem.mmu2 != 10:
        raise AssertionError('actor blit did not restore mapping/stack')
    sp,dp,w,n = job['source_page'],job['dest_page'],job['width'],job['rows']
    valid_source = sp in range(112,116) or sp in range(136,224)
    valid = valid_source and job['policy'] in (0,1,2)
    if job['op'] == 0:
        valid &= dp in (*range(112,116),*range(118,122),*range(216,224)) and sp != dp and 0 < w <= 256 and 0 < n <= 16
        for off,stride in ((job['source'],job['astride']),(job['dest'],job['bstride'])):
            valid &= 0 <= off < 8192 and stride >= w and off+(n-1)*stride+w <= 8192
    elif job['op'] == 1:
        valid &= job['source']+256 <= 8192 and job['slot'] < 64 and not (current | pending) & (1 << job['slot'])
    else:
        valid = False
    error = mem.pages[77][0x1E11]
    if bool(error) == bool(valid):
        raise AssertionError('actor blit guard disagrees')
    if mem.pages[sp] != source and sp != dp:
        raise AssertionError('actor blit changed prepared source')
    expected = bytearray([0xE3])*8192
    patterns = bytearray([0xE3])*16384
    allowed = set()
    if valid and job['op'] == 0:
        for row in range(n):
            a,b = job['source']+row*job['astride'],job['dest']+row*job['bstride']
            expected[b:b+w] = source[a:a+w]
            allowed.update(range(b,b+w))
    elif valid:
        at = job['slot']*256
        patterns[at:at+256] = source[job['source']:job['source']+256]
    if mem.pages[dp] != expected or mem.writes != allowed or mem.patterns != patterns:
        raise AssertionError('actor blit destination/gaps/patterns differ')
    if not valid and mem.dma.stats['program bytes']:
        raise AssertionError('actor blit rejected after programming DMA')
    backend = min(job['policy'],2 if core >= 0x33 else 1) if job['owned'] == 1 and not hwim2 & 1 and 0x30 <= core < 0xFF else 0
    if job['op'] == 0 and (backend == 1 and w < 64 or n == 1 and w < 64):
        backend = 0
    jobs = (1 if job['op'] == 1 or backend == 2 else n) if valid and backend else 0
    if mem.dma.stats['jobs'] != jobs:
        raise AssertionError('actor blit backend/ownership/capability differs')
    cpu_ms = (r[25]+mem.reads)/28000
    actual_backend = 1 if job['op'] == 1 and backend else backend
    return {'valid':bool(valid),'backend':('cpu','dma','blitter')[actual_backend] if valid else 'rejected',
            'cpu_added_ms':cpu_ms,'total_added_ms':None if jobs else cpu_ms,
            'dma':dict(mem.dma.stats),'instructions':steps,
            'timing_scope':'DMA stall duration excluded; total unknown when DMA is used; no hardware measurement'}


def actor_blit_checks():
    counts,cases = Counter(),[]
    for policy in (0,1,2):
        assert run_actor_blit(policy=policy,source=0,dest=4096,width=256,rows=16,astride=256,bstride=256)['valid']
        assert run_actor_blit(policy=policy,source=7936,dest=7936,width=256,rows=1,astride=256,bstride=256)['valid']
        assert run_actor_blit(policy=policy,source=7936,slot=63,op=1)['valid']
        counts['exact page/pattern-end boundaries'] += 3
    for core,hwim2,owned in ((0x33,0,1),(0x32,0,1),(0x2F,0,1),(0xFF,0,1),(0x33,1,1),(0x33,0,0)):
        for policy in (0,1,2):
            for op in (0,1):
                r = run_actor_blit(core=core,hwim2=hwim2,owned=owned,policy=policy,op=op)
                cases.append(dict(r,core=core,hwim2=hwim2,owned=owned,policy=policy,op=op))
                counts['capability/policy/operation cases'] += 1
            r = run_actor_blit(core=core,hwim2=hwim2,owned=owned,policy=policy,width=64,astride=64)
            cases.append(dict(r,core=core,hwim2=hwim2,owned=owned,policy=policy,op=0,width=64))
            counts['wide rectangle backend cases'] += 1
    # Prepared-buffer copy proxies for source spans/cache staging, not live-source DMA.
    # Include one tile's bitmap and attribute-sized spans; never infer stall-free elapsed time.
    for width in (1,8,9,16,31,32,63,64,256):
        for policy in (0,1,2):
            result = run_actor_blit(width=width,rows=1,astride=width,bstride=width,policy=policy)
            cases.append(dict(result,core=0x33,hwim2=0,owned=1,policy=policy,op=0,width=width,rows=1))
            counts['snapshot span prepared-copy proxies'] += 1
    for kw in ({'source':8192},{'dest':8192},{'width':0},{'width':257},{'rows':0},{'rows':17},
               {'astride':7},{'bstride':7},{'source':8189},{'dest':8189},
               {'source_page':135},{'source_page':224},{'dest_page':116},{'dest_page':117},
               {'source_page':118},{'op':2},{'policy':3},
               {'op':1,'source':65535},{'op':1,'source':8000},{'op':1,'slot':64}):
        assert not run_actor_blit(**kw)['valid']
        counts['bounds reject before transfer'] += 1
    for slot in (0,7,8,31,32,63):
        for owner in ('current','pending'):
            assert not run_actor_blit(op=1,slot=slot,**{owner:1 << slot})['valid']
            counts['current/pending pair protection'] += 1
    for sp,dp in ((136,216),(215,223),(223,216)):
        for policy in (0,1,2):
            for core,irq,owned in ((0x33,0,1),(0x32,0,1),(0x33,1,1),(0x33,0,0)):
                result = run_actor_blit(source_page=sp,dest_page=dp,source=4096,dest=4096,
                                        width=256,rows=16,astride=256,bstride=256,
                                        policy=policy,core=core,hwim2=irq,owned=owned)
                cases.append(dict(result,source_page=sp,dest_page=dp,policy=policy,core=core,hwim2=irq,owned=owned))
                counts['high SRAM exact-end copy/fallback cases'] += 1
    for policy in (0,1,2):
        assert run_actor_blit(source_page=215,dest_page=223,width=8,rows=16,
                              astride=11,bstride=80,policy=policy)['valid']
        counts['high SRAM strided gaps'] += 1
    assert not run_actor_blit(source_page=223,dest_page=223)['valid']
    counts['high SRAM same-page rejection'] += 1
    for page in (122,135,215,224,255):
        assert not run_actor_blit(dest_page=page)['valid']
        counts['high staging aperture rejects'] += 1
    code = bytes.fromhex(load_profile()['hooks']['blit'])
    syms = load_profile()['hooks']['syms']
    broken = bytearray(code)
    broken[int(syms['blit_phys_ahi'],16)] = 0
    # Replace the extended-address command, retaining its parameter and wrong worker's tables.
    broken[int(syms['blit_phys_ahi'],16)-1] = 0x83
    try:
        run_actor_blit(source_page=215,dest_page=223,width=64,astride=64,code=broken)
    except (AssertionError,ValueError):
        counts['physical high-address control detected'] += 1
    else:
        raise AssertionError('missing physical address control passed')
    broken = bytearray(code)
    broken[int(syms['hlib_dma_rect_bstride'],16)-1] = 0xEB
    try:
        run_actor_blit(code=broken)
    except AssertionError:
        counts['wrong stride control detected'] += 1
    else:
        raise AssertionError('actor blitter wrong-stride control passed')
    # Leave pending ownership present in the broken worker's own bitset.
    old,new = bytes.fromhex('CBDDB6A0'),bytes.fromhex('CBDD00A0')
    assert old in code
    try:
        run_actor_blit(op=1,pending=1 << 7,code=code.replace(old,new,1))
    except AssertionError:
        counts['pending overwrite control detected'] += 1
    else:
        raise AssertionError('actor blitter pending-overwrite control passed')
    return {'counts':dict(counts),'cases':cases,'scope':'assembled prepared-data rectangle and protected 256-byte sprite-pair uploads using shared backend; no installed cache/frame hook or physical DMA timing'}


class DisplayMemory(TextMapMemory):
    """Palette/clip setup device model, with distinct original ink and paper colours."""
    def __init__(self, control=0x8E, overrides=None, code=None):
        h = load_profile()['hooks']
        code = bytes.fromhex(h['display']) if code is None else code
        super().__init__([0] * 65536, 0, 0, 1, None, bytes(0x1A00) + code)
        self.nr.update({0x43:control, 0x40:97, 0x14:0xE3, 0x6B:0x0B,
                        0x69:0x35, 0x15:0xE2, 0x68:0, 0x64:0})
        self.nr.update(overrides or {})
        self.palettes = [[(index * 13 + bank * 31) % 400 for index in range(256)] for bank in range(8)]
        self.clip, self.clip_index, self.palette_first = [0,159,0,255], 2, None

    def nextreg(self, reg, value):
        if reg == 0x44:
            if self.palette_first is None:
                self.palette_first = value
            else:
                bank, index = (self.nr[0x43] >> 4) & 7, self.nr[0x40]
                self.palettes[bank][index] = self.palette_first * 2 + (value & 1)
                self.palette_first = None
                if not self.nr[0x43] & 128:
                    self.nr[0x40] = (index + 1) & 255
        elif reg == 0x1C:
            if value != 8:
                raise AssertionError('setup changed other clip indexes')
            self.clip_index = 0
        elif reg == 0x1B:
            self.clip[self.clip_index] = value
            self.clip_index = (self.clip_index + 1) & 3
        elif reg not in (0x43,0x40,0x2F,0x30,0x31,0x6F,0x6E,0x6B,0x64,0x68,0x69,0x15):
            raise AssertionError('setup changed unowned register')
        if reg in (0x40,0x43):
            self.palette_first = None
        self.nr[reg] = value

    def write_port(self, regs, port, value, *args):
        if port != 0x243B:
            raise AssertionError('setup wrote unowned port')
        self.selected = value

    def read_port(self, regs, port):
        if port != 0x253B:
            raise AssertionError('setup read unowned port')
        if self.selected in (0x41, 0x44):
            c = self.palettes[(self.nr[0x43] >> 4) & 7][self.nr[0x40]]
            return c >> 1 if self.selected == 0x41 else c & 1
        return self.nr.get(self.selected, 0)


def run_display_setup(**kwargs):
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    mem = DisplayMemory(**kwargs)
    before = {p:bytes(v) for p,v in mem.pages.items()}
    palette_before = [list(p) for p in mem.palettes]
    control, index = mem.nr[0x43], mem.nr[0x40]
    regs = [0] * 30
    regs[12], regs[24] = 0x1FF0, 0x1A00
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.display.setup')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x1D00:
        if steps >= 20000:
            raise AssertionError('display setup did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.mmu2 != 10 or mem.nr[0x07] != 3:
            raise AssertionError('display setup left private domain')
        steps += 1
    if mem.game_writes or r[12] != 0x1FF2 or mem.nr[0x43] != control or mem.nr[0x40] != index:
        raise AssertionError('setup failed RAM/stack/palette selector preservation')
    if mem.pages[69][:0x1C80] != before[69][:0x1C80] or any(bytes(mem.pages[p]) != b for p,b in before.items() if p != 69):
        raise AssertionError('setup changed code or another page')
    error = mem.pages[69][0x1EB3]
    if any(mem.palettes[i] != palette_before[i] for i in range(8) if i != 3):
        raise AssertionError('setup modified an original palette')
    if not error:
        source = palette_before[4 if control & 2 else 0]
        expected = []
        for pair in range(128):
            bright = (pair >> 3) & 8
            expected.extend((source[128 + ((pair >> 3) & 7) + bright], source[(pair & 7) + bright]))
        if mem.palettes[3] != expected or mem.clip != [16,143,80,223] or mem.nr[0x6B] != 0x0B:
            raise AssertionError('setup palette/clip/visibility differs')
    elif mem.palettes != palette_before:
        raise AssertionError('rejected setup changed palettes')
    return mem, (r[25] + mem.reads) / 28000


def display_checks():
    counts, maximum = Counter(), 0
    ram = [0] * 65536
    for cell in range(576):
        tile = cell % 256
        ram[0x9B00+cell*2] = tile
        ram[0xFC00+tile] = tile
        ram[0xDC00+tile*8:0xDC08+tile*8] = [tile ^ (1 << b) for b in range(8)]
    for control in (0x8C, 0x8E):
        setup, cost = run_display_setup(control=control)
        maximum = max(maximum, cost)
        source = setup.palettes[4 if control & 2 else 0]
        for phase in (0,1):
            for half in (0,1):
                output = run_render_textmap(ram, half=half, flash=phase)['pages'][14]
                # Project documented scroll/clip geometry in the full border coordinate space.
                clip = setup.clip
                xscroll = setup.nr[0x2F] * 256 + setup.nr[0x30]
                for y in range(256):
                    for x in range(320):
                        visible = clip[0]*2 <= x <= clip[1]*2+1 and clip[2] <= y <= clip[3]
                        if visible != (32 <= x < 288 and 80 <= y < 224):
                            raise AssertionError('textmap covers HUD/border or misses viewport')
                        if not visible:
                            continue
                        tx,ty = (x+xscroll)%320, (y+setup.nr[0x31])%256
                        off = half*0x600 + (ty//8)*80 + (tx//8)*2
                        slot = output[off] + ((output[off+1]&1)<<8)
                        bit = (output[0xC00+slot*8+(ty&7)] >> (7-(tx&7))) & 1
                        actual = setup.palettes[3][(output[off+1]&254) | bit]
                        cell = ((y-80)//8)*32 + (x-32)//8
                        tile = cell%256
                        attr = ram[0xFC00+tile]
                        original_bit = ((ram[0xDC00+tile*8+((y-80)&7)] >> (7-((x-32)&7)))&1) ^ bool(phase and attr&128)
                        bright = (attr>>3)&8
                        expected = source[((attr&7)+bright) if original_bit else (128+((attr>>3)&7)+bright)]
                        if actual != expected:
                            raise AssertionError('textmap RGB differs from original ULA ink/paper/FLASH')
                        counts['viewport RGB pixels'] += 1
                counts['palette/phase/buffer geometry'] += 1
    for kwargs in ({'control':0x8D}, {'overrides':{0x6B:0x8B}}, {'overrides':{0x14:62}}):
        mem, cost = run_display_setup(**kwargs)
        if mem.pages[69][0x1EB3] != 1 or mem.pages[69][0x1EB4]:
            raise AssertionError('unsupported/visible/transparent setup was accepted')
        counts['setup guards'] += 1
    code = bytes.fromhex(load_profile()['hooks']['display'])
    for needle, replacement in ((bytes.fromhex('C6A0'), bytes.fromhex('C680')),
                                (bytes.fromhex('ED911B10'),bytes.fromhex('ED911B00'))):
        broken = bytearray(code)
        off = broken.index(needle)
        broken[off:off+len(needle)] = replacement
        try:
            run_display_setup(code=broken)
        except AssertionError as e:
            if 'palette/clip' not in str(e):
                raise
            counts['palette/clip control detected'] += 1
        else:
            raise AssertionError('setup control not detected')
    return {'counts':dict(counts), 'max_once_only_setup_ms':maximum,
            'scope':'assembled palette/clip setup and documented geometry model; no video hardware or installed sprite renderer'}


def copper_frame_template(attributes):
    """Fixed 1548-byte program; compiler must supply all 128 five-byte sprite records."""
    if len(attributes) != 640:
        raise ValueError('copper frame needs 128 complete sprite records')
    program = bytearray((0x80, 224))
    for sprite in range(128):
        program.extend((0x34, sprite))
        for field in range(5):
            program.extend((0x35 + field, attributes[sprite * 5 + field]))
    program.extend((0x6E, 0x80, 0x6B, 0x8B, 0x15, 1, 0x7F, 0, 255, 255))
    return bytes(program)


class FrameCopper:
    """Bounded documented device semantics, not a physical raster/core emulator."""
    def __init__(self, token=0):
        self.memory = bytearray(2048)
        self.nr = {0x62:0, 0x7F:token, 0x6E:0x80, 0x6B:0x8B, 0x15:1, 0x69:0}
        self.mode, self.pc, self.index, self.sprite = 0, 0, 0, 0
        self.attributes = bytearray(640)
        self.events, self.uploads = [], 0

    def write(self, reg, value, source='cpu', line=None):
        if source == 'copper':
            self.events.append((line, reg, value))
        if reg == 0x62:
            mode = value >> 6
            if mode != self.mode and mode in (1, 3):
                self.pc = 0
            self.mode = mode
            self.index = (self.index & 255) | ((value & 7) << 8)
        elif reg == 0x61:
            self.index = (self.index & 0x700) | value
        elif reg == 0x60:
            if self.mode:
                raise AssertionError('upload changed a running copper list')
            self.memory[self.index] = value
            self.index = (self.index + 1) & 2047
            self.uploads += 1
        elif reg == 0x34:
            self.sprite = value & 127
        elif 0x35 <= reg <= 0x39:
            self.attributes[self.sprite * 5 + reg - 0x35] = value
        self.nr[reg] = value

    def advance(self, line, horizontal=0, lines=312):
        # 28 MHz Copper, shortest documented HDMI-60 line: 858 clocks at 14 MHz.
        clocks, line_cycles = horizontal, 1716
        for _ in range(1024):
            if not self.mode:
                return
            hi, lo = self.memory[self.pc * 2:self.pc * 2 + 2]
            if hi & 128:
                if (hi, lo) == (255, 255):
                    return
                wanted_line, wanted_h = ((hi & 1) << 8) | lo, ((hi >> 1) & 63) * 16
                if line != wanted_line or clocks < wanted_h:
                    return
                elapsed = 1
            else:
                self.write(hi, lo, 'copper', line)
                elapsed = 2 if hi else 1
            self.pc = (self.pc + 1) & 1023
            clocks += elapsed
            if clocks >= line_cycles:
                clocks -= line_cycles
                line = (line + 1) % lines
        raise AssertionError('copper list failed to halt')


class QueueMemory(TextMapMemory):
    def __init__(self, program, copper, ready=1, busy=0, token=0, half=1, count=128,
                 previous=128, pending=128, setup=1, code=None):
        h = load_profile()['hooks']
        code = bytes.fromhex(h['queue']) if code is None else code
        image = bytes(0x600) + code
        super().__init__([0] * 65536, half, 0, 1-half if half in (0, 1) else 0, None, image)
        self.pages[74] = bytearray(program).ljust(8192, b'\0')
        self.pages[69][0x1EA0:0x1EAA] = bytes((token, ready, busy, 0, half, 0xA0, count, previous, pending, 0))
        self.pages[69][0x1EB4] = setup
        self.copper = copper

    def __getitem__(self, a):
        if not isinstance(a, slice) and 0x4000 <= a < 0x6000 and self.mmu2 == 74:
            self.reads += 1
            return self.pages[74][a - 0x4000]
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if 0x4000 <= a < 0x6000 and self.mmu2 == 74:
            trailing = a >= 0x400B and (a-0x400B)%12 == 0 and self.pages[69][0x1EA6] <= (a-0x400B)//12 < self.pages[69][0x1EA7]
            if a not in (0x4603, 0x4607, 0x4609) and not trailing:
                raise AssertionError('queue changed immutable copper template/attributes')
            self.pages[74][a - 0x4000] = v
        else:
            super().__setitem__(a, v)

    def nextreg(self, reg, value):
        if reg == 0x52 and value in (10, 74):
            self.mmu2 = value
        elif reg in (0x61, 0x62):
            self.copper.write(reg, value)
        else:
            raise AssertionError('queue changed an unowned NextReg')

    def write_port(self, regs, port, value, *args):
        if port == 0x243B:
            self.selected = value
        elif port == 0x253B and self.selected == 0x60:
            self.copper.write(0x60, value)
        else:
            raise AssertionError('queue wrote an unowned port')

    def read_port(self, regs, port):
        if port != 0x253B or self.selected != 0x7F:
            raise AssertionError('queue read an unowned port')
        return self.copper.nr[0x7F]


def run_queue(program, copper, **kwargs):
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    mem = QueueMemory(program, copper, **kwargs)
    before = {p:bytes(v) for p,v in mem.pages.items()}
    regs = [0] * 30
    regs[12], regs[24] = 0x1FF0, 0x600
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.frame.queue')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    steps, r = 0, sim.registers
    while r[24] != 0x1D00:
        if steps >= 10000:
            raise AssertionError('queue did not return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or mem.nr[0x07] != 3:
            raise AssertionError('queue left DI/28MHz')
        steps += 1
    if mem.mmu2 != 10 or r[12] != 0x1FF2 or mem.game_writes:
        raise AssertionError('queue corrupted game mapping/stack/RAM')
    if any(bytes(mem.pages[p]) != b for p,b in before.items() if p not in (69, 74)):
        raise AssertionError('queue wrote another owner page')
    if mem.pages[69][:0x1EA0] != before[69][:0x1EA0]:
        raise AssertionError('queue modified code or cache')
    cost = (r[25] + mem.reads) / 8
    return {'equivalent_T':cost, 'added_ms':cost/3500, 'instructions':steps,
            'state':list(mem.pages[69][0x1EA0:0x1EAA]), 'program':bytes(mem.pages[74][:1548])}


def queue_checks():
    counts, costs = Counter(), []
    attributes = bytes((i * 29 + 7) & 255 for i in range(640))
    program = copper_frame_template(attributes)
    for token in (0, 254, 255):
        for half in (0, 1):
            copper = FrameCopper(token)
            before = dict(copper.nr), bytes(copper.attributes)
            result = run_queue(program, copper, token=token, half=half)
            costs.append(result['added_ms'])
            if copper.uploads != 1548 or copper.memory[:1548] != result['program'] or copper.mode != 1:
                raise AssertionError('queue upload or arm differs')
            for line in (0, 48, 191, 223):
                copper.advance(line)
            if copper.attributes != before[1] or any(copper.nr[k] != before[0][k] for k in (0x7F,0x6B,0x15,0x6E)):
                raise AssertionError('pending frame exposed before blank')
            counts['old complete frame retained'] += 1
            pending = bytes(copper.memory)
            rejected = run_queue(program, copper, token=(token+1)&255, busy=1, half=1-half)
            if copper.memory != pending or rejected['state'][1] != 1:
                raise AssertionError('busy queue overwritten before acknowledgement')
            counts['pending ownership guard'] += 1
            copper.advance(224, horizontal=1700, lines=262)
            if copper.attributes != attributes or copper.nr[0x7F] != (token+1)&255 or copper.nr[0x6E] != (0x86 if half else 0x80):
                raise AssertionError('copper frame or acknowledgement differs')
            if any(not 224 <= line <= 225 for line,reg,value in copper.events):
                raise AssertionError('commit escaped lower-border interval')
            frozen = list(copper.events)
            copper.advance(224)
            if copper.events != frozen:
                raise AssertionError('completed list repeated')
            counts['blank commit and one-shot HALT'] += 1
            run_queue(program, copper, token=(token+1)&255, busy=1, half=1-half)
            copper.advance(224)
            counts['acknowledged queue reuse'] += 1
    sized = []
    for count, previous in ((0,0),(1,0),(58,0),(2,58),(0,58),(128,128)):
        copper = FrameCopper()
        result = run_queue(program, copper, count=count, previous=previous)
        sent = max(count, previous)
        if copper.uploads != sent*12+12:
            raise AssertionError('queue uploaded the wrong sprite range')
        copper.advance(224)
        if copper.attributes[:count*5] != attributes[:count*5]:
            raise AssertionError('active sprite attributes changed')
        if any(copper.attributes[i*5+3]&128 for i in range(count, previous)):
            raise AssertionError('shrinking frame left trailing sprites visible')
        sized.append({'sprites':count,'previous':previous,'bytes':copper.uploads,'added_ms':result['added_ms']})
        counts['bounded upload / stale trailing sprite cases'] += 1
    for kw in ({'ready':0}, {'ready':2}, {'setup':0}, {'half':2}, {'count':129}, {'previous':129}):
        copper = FrameCopper()
        run_queue(program, copper, **kw)
        if copper.uploads or copper.mode:
            raise AssertionError('incomplete/invalid image armed')
        counts['ready/target guard'] += 1
    copper = FrameCopper()
    run_queue(program, copper)
    copper.write(0x62, 0)
    copper.write(0x6B, 0x0B)
    copper.write(0x15, 0)
    copper.advance(224)
    if copper.events or copper.nr[0x6B] & 128 or copper.nr[0x15] & 1:
        raise AssertionError('cancelled modal frame reappeared')
    counts['modal cancels pending copper'] += 1
    broken = bytearray(program)
    broken[:2] = bytes((0x80,48))
    copper = FrameCopper()
    run_queue(broken, copper)
    copper.advance(48)
    if not copper.events:
        raise AssertionError('active-raster control uninformative')
    counts['active-raster control detected'] += 1
    return {'counts':dict(counts), 'max_queue_added_ms':max(costs), 'sized_uploads':sized,
            'scope':'assembled uploader + bounded Copper model; synthetic sprite records; no sprite compiler, installed frame hook or hardware raster proof'}


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
        lo, low = self.syms['cap_chk'], bytes.fromhex(prof['hooks']['caplo'])
        regblock = self.syms['rom_end']        # the stub writes 20 register bytes here at boot
        if lo < regblock + 20 or lo + len(low) > 0x3A00 or any(v != 255 for v in self.rom[lo:lo + len(low)]):
            raise ValueError('capture entry block overlaps live ROM or the stub register block')
        self.rom[lo:lo + len(low)] = low
        # page 80: the copier window and the hooks' timing helpers (cw_tin / cw_tout)
        self.head = bytes.fromhex(prof['hooks']['cwhead'])
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
    """Page 68 state, page 80 (window + hook timing helpers), CTC channel 3 on the wall clock
    (`wall`, 3.5MHz T, set by the runner), NextReg $C8 (ULA interrupt seen) / $22 bit 7 (/INT) from
    the frame IRQ pulses in `irqs` (wall times; a pulse lasts CW_INT_PULSE T)."""
    def __init__(self, ram, state, patch, clk=1, ctc=True, phase=0, count0=0, irqs=()):
        self.ram, self.rom = ram, patch.rom
        self.pages = {STATE_PAGE: bytearray(state)}
        head = getattr(patch, 'head', None)
        if head is not None:
            page = bytearray(8192)
            page[:len(head)] = head
            page[CW_CLK] = clk
            self.pages[CW_PAGE] = page
        self.mmu0, self.speed = 255, 0
        self.writes, self.maps, self.fast_reads = [], [], 0
        self.ctc, self.phase, self.count0 = ctc, phase, count0
        self.wall, self.irqs, self.c8_clear, self.nr_sel, self.c8_reads = 0.0, sorted(irqs), -1e9, None, []
        self.ctc_writes = []

    def int_active(self):
        return any(t <= self.wall < t + CW_INT_PULSE for t in self.irqs)

    def c8(self):
        """Bit 0 set by a pulse since the last clear; a clear during a pulse does not take."""
        return int(any(t + CW_INT_PULSE > self.c8_clear and t <= self.wall for t in self.irqs))

    def read_port(self, regs, port):
        if port == CW_CTC_PORT:
            if not self.ctc:
                return 255                      # no CTC: floating bus, never counts
            return (self.count0 - int((self.wall + self.phase) // CW_TICK)) & 255
        if port == 0x253B and self.nr_sel == 0xC8:
            self.c8_reads.append(self.wall)
            return self.c8()
        if port == 0x253B and self.nr_sel == 0x22:
            return 0x80 if self.int_active() else 0
        if self.mmu0 == 255 and self.speed == 0 and port & 0xFF in (0x1F, 0xFE):
            return 255                          # game code (update model): as the original simulator
        raise AssertionError('unexpected port read %04X' % port)

    def write_port(self, regs, port, value, *args):
        if port == 0x243B and value in (0xC8, 0x22):
            self.nr_sel = value
        elif port == CW_CTC_PORT:
            self.ctc_writes.append(value)
        elif port & 0xFF == 0x6B and self.speed == 3:
            if getattr(self, 'dma', None) is None:   # the 8F7C map copy (zxnDMA, continuous)
                from .dma import DMA

                def stall(n):                       # CPU held while it runs: TECHNIQUES 1.0 2K copy,
                    regs[25] += round(n * CAP_DMA_CYCLES)   # 381.6 us at 28MHz (28MHz cycles a byte)
                self.dma = DMA(lambda a: LoaderMemory.__getitem__(self, a), self.__setitem__, None, stall=stall)
            self.dma.feed(value)
        else:
            raise AssertionError('unexpected port write %04X' % port)

    def __getitem__(self, a):
        if self.speed == 3 and isinstance(a, int):
            self.fast_reads += 1
        return super().__getitem__(a)

    def nextreg(self, reg, value):
        if reg == 0x07:
            if value not in (0, 3):
                raise AssertionError('unexpected CPU speed')
            self.speed = value
        elif reg == 0x50 and (value in (255, STATE_PAGE) or (value == CW_PAGE and CW_PAGE in self.pages)):
            self.mmu0 = value
            self.maps.append(value)
        elif reg == 0xC8 and value == 1:
            self.c8_clear = self.wall
        else:
            raise AssertionError('capture changed an unowned register/page')


def run_capture(patch, memory, registers, state, site, memory_class=CaptureMemory, limit=10000):
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
    mem = memory_class(patched_ram, state, patch)
    sim = simpool.machine(_rw_simulator(), mem, registers, 'inferno.capture.patched')
    sim.set_tracer(mem)
    r = sim.registers
    if r[26] != 1 or r[27] != 2:
        raise AssertionError('capture entry is not the proved IFF=1/IM2 gameplay domain')
    if site in (0x959B, 0x96A1) and r[6] != 0xC1:
        raise AssertionError('actor lookup does not use the C100 table')
    z80n.install(sim, mem.nextreg)
    elapsed, steps = 0.0, 0
    safe = [i for i in CMP if i != 24]
    timed = site in HOOK_TIMED and CW_PAGE in getattr(mem, 'pages', {})
    if timed:
        x0 = int.from_bytes(mem.pages[CW_PAGE][CW_X:CW_X + 2], 'little')
    while r[24] != end:
        if steps >= limit:
            raise AssertionError('capture did not return')
        if r[24] in patch.site_bytes and r[24] not in patch.sites:
            raise AssertionError('capture jumped into a patched instruction interior')
        # Fetching the opcode is a real memory read too; charge the extra 28MHz wait below.
        before, speed, reads = r[25], mem.speed, mem.fast_reads
        pc, page = r[24], mem.mmu0
        mem.wall = elapsed
        opcode = mem[r[24]]
        sim.opcodes[opcode]()
        # Transition instructions charged at 3.5MHz is a conservative bound.
        instruction_cost = _cost(r, before, speed, reads, mem)
        elapsed += instruction_cost
        if hasattr(mem, 'cost_components'):
            syms = patch.syms
            kind = ('scenery_source_compile' if page == 69 and syms['render_textmap.tm_source'] <= pc < syms['render_textmap.tm_full'] else
                    'scenery_map_bookkeeping' if page == 69 and pc < syms['render_textmap_end'] else 'frame_wrapper_prepare')
            mem.cost_components[kind] += instruction_cost
        if r[26] and opcode != 0xFB:   # EI: no IRQ before the next instruction
            if mem.mmu0 != 255 or mem.speed != 0 or getattr(mem,'mmu1',255) != 255 or getattr(mem,'mmu2',10) != 10:
                raise AssertionError('interrupt-enabled scratch mapping/fast beeper')
            if not (all(r[i] == registers[i] for i in safe) or
                    all(r[i] == original.registers[i] for i in safe)):
                raise AssertionError('interrupt-enabled intermediate register/stack state')
        steps += 1
    diffs = [i for i in CMP if r[i] != original.registers[i]]
    if diffs:
        raise AssertionError('capture registers differ: ' + str(diffs))
    if timed and r[15] != original.registers[15]:
        raise AssertionError('capture R %02X != %02X' % (r[15], original.registers[15]))
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
    if timed and mem.pages[CW_PAGE][CW_CLK] == 1:
        x1 = int.from_bytes(mem.pages[CW_PAGE][CW_X:CW_X + 2], 'little')
        measured = x1 if site == 0x8F7C else (x1 - x0) & 0xFFFF
        measured -= 65536 if measured >= 32768 else 0
        mem.x_measured = measured
        if abs(measured - added) > HOOK_X_TOL:
            raise AssertionError('capture X %d != added %.1f' % (measured, added))
    if hasattr(mem, 'cost_components'):
        mem.cost_components['frame_wrapper_prepare'] -= original.registers[25] - registers[25]
    return mem.pages[STATE_PAGE], added, steps




HOOK_TIMED = (0x8F7C, 0x959B, 0x96A1)   # hooks that measure X and restore R (milestone 3)
CAP_DMA_CYCLES = 381.6 * 28 / 2048      # zxnDMA memory copy, 28MHz cycles a byte (hardware 2K figure)
HOOK_X_TOL = 12                         # T: two sync-loop latencies (KSYNC 6) + 28MHz rounding


class PausePatch(CapturePatch):
    """One checked initialization boundary, after original DI and before IM2 setup."""
    def __init__(self,code=None):
        h=load_profile()['hooks']
        self.code=bytes.fromhex(h['pause']) if code is None else code
        self.rom=loader_rom()
        org=int(h['syms']['pause_loading'],16)
        if org+len(self.code)>=0x3D00 or any(b!=255 for b in self.rom[org:org+len(self.code)]):
            raise ValueError('loading pause overlaps live ROM')
        self.rom[org:org+len(self.code)]=self.code
        self.sites={0x8EF9:(bytes.fromhex('329891'),b'\xC3'+org.to_bytes(2,'little'))}
        self.stops={0x8EF9:0x8EFC}
        self.site_bytes=set(range(0x8EF9,0x8EFC))


class PauseMemory(CaptureMemory):
    def __init__(self,ram,state,patch,speed):
        super().__init__(ram,state,patch)
        self.speed=speed
        self.selected=0

    def nextreg(self,reg,value):
        if reg==7 and value in range(4):
            self.speed=value
        else:
            super().nextreg(reg,value)

    def read_port(self,registers,port):
        if port!=0x253B or self.selected!=7:
            raise AssertionError('pause read unexpected IO')
        return self.speed | (self.speed<<4)

    def write_port(self,registers,port,value,*args):
        if port!=0x243B or value!=7:
            raise AssertionError('pause wrote original IO/display')
        self.selected=value

    def __setitem__(self,a,v):
        if a<8192 and self.mmu0==68 and 0x1D00<=a<0x1EF0:
            self.pages[68][a]=v
        elif a==0x9198 and self.mmu0==255:
            self.ram[a]=v
        else:
            raise AssertionError('pause touched original stack/code/RAM')


def run_loading_pause(memory,registers,speed=0,code=None,worker=None,check_r=True):
    from . import simpool,z80n
    from .dizzy6 import _rw_simulator
    from skoolkit.simulator import Simulator
    if registers[24]!=0x8EF9 or registers[26] or registers[27]!=1:
        raise ValueError('unproved loading pause entry domain')
    patch=PausePatch(code)
    original=simpool.machine(Simulator,list(memory),registers,'inferno.pause.original',copy=True)
    original.opcodes[original.memory[0x8EF9]]()
    state=bytearray(8192)
    # Variable-duration clobbering private worker, never a stand-in for an installed scheduler.
    worker=worker or bytes.fromhex('0100100B78B120FB110102210304DD210506FD210708D901090A110B0C210D0ED9083E9B08C9')
    state[0x1D80:0x1D80+len(worker)]=worker
    mem=PauseMemory(patch.apply_memory(memory),state,patch,speed)
    sim=simpool.machine(_rw_simulator(),mem,registers,'inferno.pause.patched')
    sim.set_tracer(mem)
    z80n.install(sim,mem.nextreg)
    steps=0
    while sim.registers[24]!=0x8EFC:
        if steps>400000:
            raise AssertionError('pause worker failed to return')
        sim.opcodes[mem[sim.registers[24]]]()
        if sim.registers[26] or sim.registers[27]!=1 or sim.registers[14]!=registers[14]:
            raise AssertionError('pause changed IFF/IM/I')
        steps+=1
    compared=tuple(i for i in range(30) if i not in (25,29) and (check_r or i!=15))
    if any(sim.registers[i]!=original.registers[i] for i in compared):
        raise AssertionError('pause changed original registers: '+str([(i,original.registers[i],sim.registers[i]) for i in compared if sim.registers[i]!=original.registers[i]]))
    expected=list(original.memory)
    expected[0x8EF9:0x8EFC]=patch.sites[0x8EF9][1]
    if mem.ram!=expected or mem.mmu0!=255 or mem.speed!=speed:
        raise AssertionError('pause failed original RAM/mapping/caller-speed contract')
    return {'instructions':steps,'refresh_delta':(original.registers[15]-sim.registers[15])&127}


def loading_pause_checks(memory=None,registers=None):
    if memory is None:
        memory=[0]*65536
        memory[0x8EF9:0x8EFC]=bytes.fromhex('329891')
        registers=[(i*17)&255 for i in range(30)]
        registers[12],registers[24],registers[26],registers[27],registers[28]=0xF000,0x8EF9,0,1,0
    counts=Counter()
    for speed in range(4):
        for refresh in (0,1,126,127,128,255):
            regs=list(registers)
            regs[15]=refresh
            run_loading_pause(memory,regs,speed=speed)
            counts['all-register/R/RAM/stack/IFF/caller-speed pause restoration']+=1
    for worker in (b'\xC9',bytes.fromhex('01FFFF0B78B120FBC9')):
        run_loading_pause(memory,registers,worker=worker)
        counts['variable worker M1 duration restoration']+=1
    code=bytes.fromhex(load_profile()['hooks']['pause'])
    broken=code.replace(bytes.fromhex('ED4F'),bytes.fromhex('0000'))
    try:
        run_loading_pause(memory,registers,code=broken)
    except AssertionError:
        counts['missing R restoration control detected']+=1
    else:
        raise AssertionError('missing R control not informative')
    return dict(counts)


DRIVER_WRITE = {
    68: [(0x1D00, 0x1EF0)],
    75: [(0x1EC0, 0x1EE0), (0x1F00, 0x1FF0)],
    76: [(0x1E90, 0x1EAA), (0x1F00, 0x1FF0)],
    78: [(0x1E80, 0x1E96), (0x1F00, 0x1FF0)],
    79: [(0x0800, 0x1800), (0x1E80, 0x1EA0), (0x1F00, 0x1FF0)],
    81: [(0x1800, 0x1BF0), (0x1C00, 0x1C80)],
    69: [(0x1C80, 0x1CC0), (0x1EB0, 0x1EC0), (0x1F00, 0x1FF0)],   # setup_display: colours, flags, stack
    82: [(0x1000, 0x2000)],                             # selection state, reset at load
    83: [(0, 0x2000)], 84: [(0, 0x2000)],
    **{p: [(0, 0x2000)] for p in range(85, 96)},
}


class DriverMemory:
    """Whole loading driver from the 8EF9 gate: every page and slot, guarded writes and mappings."""
    def __init__(self, ram, rom, pages):
        self.ram, self.rom, self.pages = list(ram), rom, pages
        self.slots = [255, 255, 10, 11, 4, 5, 0, 1]
        self.reads = self.speed = self.selected = 0
        self.nr = {}

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        self.reads += 1
        s, p = a >> 13, self.slots[a >> 13]
        if p == 255:
            return self.rom[a]
        if s >= 2 and p in (10, 11, 4, 5, 0, 1):
            return self.ram[a]
        return self.pages[p][a & 8191]

    def __setitem__(self, a, v):
        s, p = a >> 13, self.slots[a >> 13]
        if p == 255:
            raise AssertionError('driver wrote ROM at %04X' % a)
        if s >= 2 and p in (10, 11, 4, 5, 0, 1):
            if a != 0x9198:
                raise AssertionError('driver wrote original RAM at %04X' % a)
            self.ram[a] = v
            return
        o = a & 8191
        if p in DRIVER_WRITE:
            if not any(l <= o < h for l, h in DRIVER_WRITE[p]):
                raise AssertionError('driver wrote page %d offset %04X' % (p, o))
        elif not (112 <= p <= 117 or p == 122 or 136 <= p < 216):
            raise AssertionError('driver wrote unowned page %d' % p)
        self.pages[p][o] = v

    def nextreg(self, reg, value):
        allowed = {0x50: (68, 69, 75, 76, 78, 79, 81, 255), 0x51: (68, 75, 76, 78, 79, 82, 83, 84, 112, 113, 114, 115, 116, 122, 255),
                   0x52: (10, 113, 114, 115, 116, 117, 122, *range(85, 96), *range(96, 112), *range(136, 216)),
                   0x53: (11, *range(128, 136), *range(136, 216))}
        if reg == 7 and value in range(4):
            self.speed = value
        elif reg in (0x15, 0x6B, 0x64, 0x68, 0x69, 0x1C, 0x1B, 0x2F, 0x30, 0x31, 0x43, 0x40, 0x44, 0x6E, 0x6F):
            self.nr[reg] = value
        elif reg in allowed and value in allowed[reg]:
            self.slots[reg - 0x50] = value
        else:
            raise AssertionError('driver set NextReg %02X to %d' % (reg, value))

    def read_port(self, registers, port):
        if port != 0x253B or self.selected not in (7, 0x14, 0x15, 0x40, 0x41, 0x43, 0x44, 0x69, 0x6B):
            raise AssertionError('driver read unexpected IO')
        if self.selected == 7:
            return self.speed | (self.speed << 4)
        return {0x14: 0xE3, 0x41: self.nr.get(0x40, 0) & 0x7F}.get(self.selected, 0)

    def write_port(self, registers, port, value, *args):
        if port != 0x243B or value not in (7, 0x14, 0x15, 0x40, 0x41, 0x43, 0x44, 0x69, 0x6B):
            raise AssertionError('driver wrote IO')
        self.selected = value


def driver_pages(driver=None, owned=None):
    h = load_profile()['hooks']
    pages = {p: bytearray(8192) for p in (68, 75, 76, 78, 79, 81, *range(83, 96), *range(136, 216))}
    pages[82] = select_page()
    pages[69] = cw_work_renderer()
    for p in (*range(112, 118), 122):
        pages[p] = bytearray([0xE3]) * 8192             # exposes any byte the driver fails to set
    table = actor_row_lookup()
    pages.update({p: bytearray(table[(p - 96) * 8192:(p - 95) * 8192]) for p in range(96, 112)})
    flags, finish, reach = actor_fill_lookup()
    pages.update({p: bytearray(reach[(p - 128) * 8192:(p - 127) * 8192]) for p in range(128, 136)})
    stub = bytes.fromhex(h['drvworker'])
    for p, code in ((75, h['pack']), (76, h['fill']), (78, h['job']), (79, h['owned'] if owned is None else owned)):
        code = bytes.fromhex(code)
        pages[p][:len(code)] = code
        pages[p][0x1D00:0x1D00 + len(stub)] = stub
        pages[p][0x1FF0:0x1FF2] = b'\x00\x1D'
    pages[76][0x600:0x700], pages[76][0x800:0xC00] = flags, finish
    code = bytes.fromhex(h['driver'] if driver is None else driver)
    pages[81][:len(code)] = code
    tail = bytes.fromhex(h['drvpage'])
    pages[81][0x1D00:0x1D00 + len(tail)] = tail
    stub = bytes.fromhex(h['drv68'])
    pages[68][0x1D80:0x1D80 + len(stub)] = stub
    return pages


def run_loading_driver(memory, registers, speed=0, driver=None, owned=None, limit=400_000_000):
    """Gate + driver as assembled, from 8EF9 to 8EFC, against the original's single instruction."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    from skoolkit.simulator import Simulator
    patch = PausePatch()
    original = simpool.machine(Simulator, list(memory), registers, 'inferno.driver.original', copy=True)
    original.opcodes[original.memory[0x8EF9]]()
    mem = DriverMemory(patch.apply_memory(memory), patch.rom, driver_pages(driver, owned))
    mem.speed = speed
    regs = list(registers)
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.driver.patched')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps = sim.registers, 0
    while r[24] != 0x8EFC:
        if steps > limit:
            raise AssertionError('driver failed to return')
        sim.opcodes[mem[r[24]]]()
        if r[26] or r[27] != 1 or r[14] != registers[14]:
            raise AssertionError('driver changed IFF/IM/I')
        steps += 1
    compared = tuple(i for i in range(30) if i not in (25, 29))
    bad = [(i, original.registers[i], r[i]) for i in compared if r[i] != original.registers[i]]
    if bad:
        raise AssertionError('driver changed original registers: %s' % bad)
    expected = list(original.memory)
    expected[0x8EF9:0x8EFC] = patch.sites[0x8EF9][1]
    if mem.ram != expected or mem.slots != [255, 255, 10, 11, 4, 5, 0, 1] or mem.speed != speed:
        raise AssertionError('driver failed RAM/mapping/caller-speed contract')
    state = mem.pages[81]
    word = lambda a: int.from_bytes(state[a:a + 2], 'little')
    return {'pages': mem.pages, 'stored': word(0x181A), 'duplicates': word(0x181C), 'rejected': word(0x181E),
            'fail': state[0x1820], 'instructions': steps, 'equivalent_T': (r[25] + mem.reads) / 8}


def driver_expected(ram):
    """Independent oracle, per C100 index: 'none' (no tiles), 'reject', or the exact stream and packed canvas."""
    out = []
    for image in range(256):
        try:
            actor = actor_descriptor(ram, image)
            if not actor['tiles']:
                out.append(None)
                continue
            ptr, pos, stream = actor['pointer'], actor['pointer'] + 1, bytearray((ram[actor['pointer']],))
            while ram[pos]:
                width, dx, dy = ram[pos:pos + 3]
                stream += bytes((width, dx, dy))
                pos += 3
                for j in range(width):
                    stream.append(ram[pos])
                    stream += raw_tile(ram, ram[pos] + 256 * (ram[ptr] & 3))
                    pos += 1
            stream.append(0)
            if len(stream) > 8192:
                raise ValueError('stream capacity')
            left, top, width, height, pixels = solid_image(tuple((x, y, raw_tile(ram, t)) for x, y, t in actor['tiles']))
            if width > 1024:
                raise ValueError('canvas stride')
        except (ValueError, IndexError):
            out.append('reject')
            continue
        canvas = bytes(pixels[i] * 16 + pixels[i + 1] for i in range(0, len(pixels), 2))
        out.append((bytes(stream), canvas))
    return out


def driver_compare(result, expected, capacity=False):
    """The driver's published store against the oracle. capacity: a refused store is allowed."""
    pages, counts = result['pages'], Counter()
    canonical, stored = {}, 0
    for image, want in enumerate(expected):
        e = bytes(pages[79][0x800 + 16 * image:0x810 + 16 * image])
        if want is None or want == 'reject':
            if e[0]:
                raise AssertionError('index %d published without valid content' % image)
            counts['indices with no tiles' if want is None else 'rejected indices'] += 1
            continue
        if not e[0]:
            if capacity:
                counts['capacity refusals'] += 1
                continue
            raise AssertionError('index %d not published' % image)
        source = owned_payload(pages, e[1], int.from_bytes(e[2:4], 'little'), int.from_bytes(e[4:6], 'little'))
        canvas = owned_payload(pages, e[6], int.from_bytes(e[7:9], 'little'), int.from_bytes(e[9:11], 'little'))
        if (source, canvas) != want:
            raise AssertionError('index %d: stored stream/canvas differ (source %s canvas %s)' % (image, source == want[0], canvas == want[1]))
        if e[11:] != bytes(5):
            raise AssertionError('index %d: phase/generation' % image)
        if want[0] in canonical:
            if e[1:11] != canonical[want[0]]:
                raise AssertionError('index %d: duplicate does not share the stored payload' % image)
            counts['duplicate indices sharing a payload'] += 1
        else:
            canonical[want[0]] = e[1:11]
            stored += 1
            counts['distinct streams stored'] += 1
    if result['fail'] or result['stored'] != stored:
        raise AssertionError('driver counters: %s' % {k: result[k] for k in ('stored', 'duplicates', 'rejected', 'fail')})
    return dict(counts)


SEL_STATE = 0x1000                      # page 82: state offsets (asm SEL_* - 0x4000)
SEL_READY, SEL_ROLE, SEL_N, SEL_MASKS = 0x1000, 0x1001, 0x1004, 0x1010
SEL_HEAD, SEL_TAIL, SEL_PREV, SEL_NEXT = 0x1040, 0x1041, 0x1240, 0x1280
SEL_NEW, SEL_EVICT, SEL_QN = 0x103C, 0x103D, 0x1046
SEL_SLOT_ID, SEL_FLAG, SEL_ID_SLOT, SEL_LIST = 0x1100, 0x1200, 0x1300, 0x1800
PAT_MAX = 704


def select_page(code=None):
    """Page 82: selection code at 0 (slot 2, 4000); state reset as the driver does it."""
    page = bytearray(8192)
    code = bytes.fromhex(load_profile()['hooks']['cwsel']) if code is None else code
    page[:len(code)] = code
    page[SEL_ROLE], page[SEL_HEAD], page[SEL_TAIL] = 0x24, 0, 63
    page[SEL_PREV:SEL_PREV + 64] = bytes((i - 1) & 255 if i else 64 for i in range(64))
    page[SEL_NEXT:SEL_NEXT + 64] = bytes(i + 1 for i in range(64))
    page[SEL_SLOT_ID:SEL_SLOT_ID + 128] = b'\xFF' * 128
    page[SEL_ID_SLOT:SEL_ID_SLOT + PAT_MAX] = b'\xFF' * PAT_MAX
    return page


def pattern_index_expected(ram, expected):
    """Oracle for the 8EF9 index: {image: (left, top, [(cx, cy, mask, id)])}, patterns by id, in scan order."""
    ids, patterns, out, canon = {}, [], {}, {}
    for image, want in enumerate(expected):
        if want is None or want == 'reject':
            continue
        if want[0] in canon:
            out[image] = out[canon[want[0]]]
            continue
        canon[want[0]] = image
        actor = actor_descriptor(ram, image)
        left, top, w, h, px = solid_image(tuple((x, y, raw_tile(ram, t)) for x, y, t in actor['tiles']))
        chunks = []
        for cy in range(0, h, 16):
            for cx in range(0, w, 16):
                pattern, mask = bytearray(128), 0
                for y in range(min(16, h - cy)):
                    for x in range(min(16, w - cx)):
                        c = px[(cy + y) * w + cx + x]
                        if c:
                            pattern[y * 8 + x // 2] |= c << (4 if not x & 1 else 0)
                            mask |= 1 << (y // 8 * 2 + x // 8)
                if mask:
                    key = bytes(pattern)
                    if key not in ids:
                        ids[key] = len(patterns)
                        patterns.append(key)
                    chunks.append((cx // 8, cy // 8, mask, ids[key]))
        out[image] = ((left // 8) & 255, (top // 8) & 255, chunks)
    return out, patterns


def index_tables(pages):
    """Decode page 83 as the runtime reads it."""
    p, out = pages[83], {}
    for image in range(256):
        h = p[image * 6:image * 6 + 6]
        if h[0] == 1:
            at = h[2] | h[3] << 8
            out[image] = (h[4], h[5], [(p[at + 5 * i], p[at + 5 * i + 1], p[at + 5 * i + 2],
                                        p[at + 5 * i + 3] | p[at + 5 * i + 4] << 8) for i in range(h[1])])
    return out


def driver_index_compare(result, ram, expected):
    """The index and pattern pages against the oracle; published images only."""
    pages, counts = result['pages'], Counter()
    want, patterns = pattern_index_expected(ram, expected)
    have = index_tables(pages)
    for image in range(256):
        if pages[79][0x800 + 16 * image] == 1:
            if image not in want or have.get(image) != want[image]:
                raise AssertionError('index %d: chunks differ\n%s\n%s' % (image, have.get(image), want.get(image)))
            counts['indexed images'] += 1
    used = result['pages'][81][0x1832] | result['pages'][81][0x1833] << 8
    if used != len(patterns):
        raise AssertionError('patterns stored %d, oracle %d' % (used, len(patterns)))
    for i, pat in enumerate(patterns):
        if bytes(pages[85 + i // 64][i % 64 * 128:i % 64 * 128 + 128]) != pat:
            raise AssertionError('pattern %d differs' % i)
    if pages[69][0x1EB4] != 1 or pages[69][0x1EB3]:
        raise AssertionError('display setup failed')
    if bytes(pages[82][SEL_STATE:]) != bytes(select_page()[SEL_STATE:]):
        raise AssertionError('page 82 state not reset to the runtime initial state')
    counts['distinct patterns'] = len(patterns)
    return dict(counts)


class SelectState:
    """Python model of the page-82 store; select_expected() is its only mutator."""
    def __init__(self, page=None):
        p = page if page is not None else select_page()
        self.role = p[SEL_ROLE]
        self.lru, s = [], p[SEL_HEAD]
        while s != 64:
            self.lru.append(s)
            if len(self.lru) > 64 or p[SEL_NEXT + s] != 64 and p[SEL_PREV + p[SEL_NEXT + s]] != s:
                raise AssertionError('recency list broken')
            s = p[SEL_NEXT + s]
        if len(self.lru) != 64 or self.lru[-1] != p[SEL_TAIL]:
            raise AssertionError('recency list incomplete')
        self.masks = [int.from_bytes(p[SEL_MASKS + 8 * i:SEL_MASKS + 8 * i + 8], 'little') for i in range(3)]
        self.ids = [p[SEL_SLOT_ID + 2 * s] | p[SEL_SLOT_ID + 2 * s + 1] << 8 for s in range(64)]
        self.flags = list(p[SEL_FLAG:SEL_FLAG + 64])
        if p[0x104C] != sum(1 for f in self.flags if f):
            raise AssertionError('dirty count %d, flags %d' % (p[0x104C], sum(1 for f in self.flags if f)))
        self.id_slot = {i: p[SEL_ID_SLOT + i] for i in range(PAT_MAX) if p[SEL_ID_SLOT + i] != 255}

    def tuple(self):
        return (self.role, tuple(self.lru), tuple(self.masks), tuple(self.ids), tuple(self.flags),
                tuple(sorted(self.id_slot.items())))


def select_expected(state, index, log):
    """Oracle: (ready, [(slot, col, row)]) for one selection attempt; mutates state exactly as the assembly."""
    b = (state.role >> 4) & 3
    state.masks[b] = 0
    out = []
    for rec in log:
        if rec['image'] not in index:
            return 0, out
        left, top, chunks = index[rec['image']]
        for cx, cy, mask, pid in chunks:
            col, row = (left + cx + rec['x']) & 255, (top + cy + rec['y']) & 255
            if not any(mask & 1 << c and ((col + (c & 1)) & 255) < 32 and ((row + (c >> 1)) & 255) < 18 for c in range(4)):
                continue
            slot = state.id_slot.get(pid)
            if slot is None:
                used = state.masks[0] | state.masks[1] | state.masks[2]
                best = next((s for s in state.lru if not used >> s & 1), None)
                if best is None:
                    return 0, out
                if state.ids[best] != 0xFFFF:
                    state.id_slot.pop(state.ids[best], None)
                state.ids[best], state.flags[best] = pid, 1
                state.id_slot[pid] = slot = best
            state.masks[b] |= 1 << slot
            state.lru.remove(slot)
            state.lru.append(slot)
            if len(out) >= 128:
                return 0, out
            out.append((slot, col, row))
    c, p = state.role & 3, (state.role >> 2) & 3
    state.role = c << 4 | b << 2 | p
    for slot, _, _ in out:                               # everything the frame uses is uploaded before the commit
        state.flags[slot] = 0
    return 1, out


def driver_fixture():
    """Crafted C100 table: duplicates at distinct addresses, same-size different content, negative dx/dy,
    a hole in the tile grid, an enclosed black interior, empty, bad pointer and oversize images."""
    ram = [0] * 65536
    ram[0x8EF9:0x8EFC] = bytes.fromhex('329891')
    for i in range(256):
        ram[0xC100 + i] = 0x20                          # default target is below 4000: rejected
    def tile(index, bits, attr):
        ram[0xDC00 + 8 * index:0xDC08 + 8 * index] = bits
        ram[0xFC00 + index] = attr
    tile(1, [0xFF, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0xFF], 0x07)    # enclosed black interior
    tile(2, [0xFF] * 8, 0x02)
    tile(3, [0xFE] * 8, 0x02)                           # same size as tile 2, different bytes
    tile(4, [0xF0, 0xF0, 0, 0, 0x0F, 0x0F, 0, 0], 0x42)
    records = {
        0xD000: bytes((0, 2, 0xFF, 0xFE, 1, 2)) + bytes((1, 3, 1, 4, 0)),       # negative dx/dy; hole (grid gap)
        0xD040: bytes((0, 2, 0xFF, 0xFE, 1, 2)) + bytes((1, 3, 1, 4, 0)),       # exact duplicate elsewhere
        0xD080: bytes((0, 2, 0xFF, 0xFE, 1, 3)) + bytes((1, 3, 1, 4, 0)),       # same size, different tile
        0xD0C0: bytes((0, 0)),                                                  # no tiles
        0xD0D0: bytes((1, 1, 0, 0, 1, 0)),                                      # header page 1: different ID
        0xD100: bytes((0, 3, 0, 0, 1, 1, 1, 0)),                                # tile 1 x3 (whole-image B)
        0xD180: bytes((0, 1, 100, 0, 2, 1, 0x9C, 0, 2, 0)),                     # W 129: outside the limit
        0xD1A0: bytes((0, 129)),                                                # invalid width
        0xD200: bytes(b for y in range(8) for b in (64, 0, y, *([2] * 64)))[:0] + bytes((0,)) + bytes(b for y in range(8) for b in (64, 0, y, *([2] * 64))) + bytes((0,)),  # 16 K canvas: refused at the last store page
    }
    for a, b in records.items():
        ram[a:a + len(b)] = b
    # Page 1 tile IDs reach 256+: give index 257 content.
    ram[0xDC00 + 8 * 257:0xDC00 + 8 * 258] = [0x18] * 8
    ram[0xFC00 + 257] = 0x05
    # C100 pointers are two consecutive bytes, the next index shares one: even indices only.
    for i, a in enumerate(sorted(records)):
        ram[0xC100 + 2 * i], ram[0xC101 + 2 * i] = a & 255, a >> 8
    regs = [(i * 17) & 255 for i in range(30)]
    regs[12], regs[24], regs[26], regs[27], regs[28], regs[15] = 0xF000, 0x8EF9, 0, 1, 0, 0x55
    return ram, regs


def _driver_variant(block, old, new, occurrence=0):
    code = load_profile()['hooks'][block]
    h = code.upper()
    o, n = old.upper(), new.upper()
    at = -2
    for _ in range(occurrence + 1):
        at = h.index(o, at + 2)
    return h[:at] + n + h[at + len(o):]


def driver_checks():
    """Crafted-table checks and negative controls for the assembled loading driver (no recording needed)."""
    ram, regs = driver_fixture()
    expected = driver_expected(ram)
    syms = load_profile()['hooks']['syms']
    result = run_loading_driver(ram, regs)
    counts = Counter(driver_compare(result, expected))
    counts.update(driver_index_compare(result, ram, expected))
    if not counts['duplicate indices sharing a payload'] or not counts['rejected indices'] or not counts['indices with no tiles']:
        raise AssertionError('fixture does not exercise the driver: %s' % dict(counts))
    for speed in range(4):
        for refresh in (0, 127, 128, 255):
            r = list(regs)
            r[15] = refresh
            driver_compare(run_loading_driver(ram, r, speed=speed), expected)
            counts['gate register/R/speed restoration around the whole driver'] += 1
    # Capacity: store pinned at the last page, only some images fit; nothing partial is published.
    h = load_profile()['hooks']['owned'].upper()
    if h.count('3E88') != 1:
        raise AssertionError('capacity control: reset page constant not unique')
    owned = h.replace('3E88', '3ED7')                   # first store page 215
    capped = run_loading_driver(ram, regs, owned=owned)
    capped_counts = driver_compare(capped, expected, capacity=True)
    if not capped_counts.get('capacity refusals'):
        raise AssertionError('capacity control not informative')
    counts['capacity refusal unpublished (control)'] += capped_counts['capacity refusals']
    # Negative controls: each broken driver must fail the oracle or the run's own contract.
    controls = {
        'duplicate search compares size only': _driver_variant('driver', '1ABE20', '1ABF20'),
        'canvas not cleared': None,
        'B fill skipped': None,
        'unsigned dx/dy': _driver_variant('driver', '5F179F57', '5F00AF57'),
    }
    source = load_profile()['hooks']['driver'].upper()
    clear_at = int(syms['drv_clear'], 16) * 2
    fill_at = int(syms['drv_fill'], 16) * 2
    controls['canvas not cleared'] = source[:clear_at] + 'C9' + source[clear_at + 2:]
    controls['B fill skipped'] = source[:fill_at] + 'AFC9' + source[fill_at + 4:]
    for name, code in controls.items():
        try:
            driver_compare(run_loading_driver(ram, regs, driver=code), expected)
        except (AssertionError, KeyError):
            counts['control detected: ' + name] += 1
        else:
            raise AssertionError('control not informative: ' + name)
    return {'counts': dict(counts), 'driver_ms_fixture': result['equivalent_T'] / 3500,
            'scope': 'assembled driver via the 8EF9 gate on a crafted table; simulator, DI, no hardware'}


def driver_stream(ram, image):
    """The exact serialized stream the store keeps for a C100 index; ValueError if malformed."""
    actor = actor_descriptor(ram, image)
    ptr, pos, stream = actor['pointer'], actor['pointer'] + 1, bytearray((ram[actor['pointer']],))
    while ram[pos]:
        width, dx, dy = ram[pos:pos + 3]
        stream += bytes((width, dx, dy))
        pos += 3
        for j in range(width):
            stream.append(ram[pos])
            stream += raw_tile(ram, ram[pos] + 256 * (ram[ptr] & 3))
            pos += 1
    stream.append(0)
    return bytes(stream)


def dispatch_expected(store, live, page68):
    """Oracle for the window dispatch: (ready, reasons), from the store and the live original RAM."""
    if page68[0x3F5]:
        return 0, ['log overflow']
    for record in capture_log(page68):
        image = record['image']
        e = bytes(store[79][0x800 + 16 * image:0x810 + 16 * image])
        if e[0] != 1:
            return 0, ['no entry']
        if e[11:14] != bytes(3):
            return 0, ['phase/generation']
        try:
            stream = driver_stream(live, image)
        except ValueError:
            return 0, ['malformed live record']
        if owned_payload(store, e[1], int.from_bytes(e[2:4], 'little'), int.from_bytes(e[4:6], 'little')) != stream:
            return 0, ['changed content']
    return 1, []


def driver_store(result):
    """Owned-store pages of a driver run: metadata page and the used pages only."""
    pages = result['pages']
    return {p: bytes(pages[p]) for p in (79, 82, 83, *range(85, 96), *range(136, 216)) if p in (79, 82, 83) or 85 <= p < 96 or any(pages[p])}


class DispatchMemory:
    """Page 69 dispatch alone: slot 0 = 69, slot 1 mapped, the rest original RAM; CTC poll scripted."""
    def __init__(self, ram, pages):
        self.ram, self.pages = list(ram), pages
        self.mmu1 = 68
        self.polls = self.yield_every = 0
        self.iyl = lambda: 0

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        if a < 8192:
            return self.pages[69][a]
        if a < 16384:
            return self.pages[self.mmu1][a & 8191]
        return self.ram[a]

    def __setitem__(self, a, v):
        if a < 8192 and (0x1C00 <= a < 0x1C40 or 0x1EC0 <= a < 0x1F00):
            self.pages[69][a] = v
        else:
            raise AssertionError('dispatch wrote %04X (slot 1 page %d)' % (a, self.mmu1))

    def nextreg(self, reg, value):
        if reg == 0x51 and (value in (68, 79, 255) or 136 <= value < 216):
            self.mmu1 = value
        elif not (reg == 0x52 and value == 10):
            raise AssertionError('dispatch set NextReg %02X to %d' % (reg, value))

    def read_port(self, regs, port):
        if port != 0x1B3B:
            return 0                                     # NextReg $C8 read by wk_leave
        self.polls += 1
        if self.yield_every and self.polls % self.yield_every == 0:
            return self.iyl()
        return (self.iyl() + 1) & 255

    def write_port(self, *args):
        pass


def run_dispatch(ram, store, log, yield_every=0, scene=1, code=None, overflow=0, slices=None):
    """Assembled dispatch from wk_dispatch to its RET; a yield re-enters through wk_enter (resume)."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    syms = {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}
    pages = {p: bytearray(v) for p, v in store.items()}
    pages[69] = cw_work_renderer()
    if code is not None:
        org = syms['wk_dispatch']
        pages[69][org:org + len(code)] = code
    pages[68] = bytearray(8192)
    at = 0x900
    for record in log:
        pages[68][at:at + len(record)] = record
        at += len(record)
    pages[68][0x3F2:0x3F4] = at.to_bytes(2, 'little')
    pages[68][0x3F4], pages[68][0x3F5] = len(log), overflow
    pages[69][0x1EAC], pages[69][0x1EC2] = scene, 10
    mem = DispatchMemory(ram, pages)
    mem.yield_every = yield_every
    regs = [0] * 30
    regs[12] = 0x1C3E                                    # WK_STACK - return address
    regs[24], regs[14], regs[27] = syms['wk_dispatch'], 0xFE, 2
    pages[69][0x1C3E:0x1C40] = (0x3333).to_bytes(2, 'little')
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.dispatch')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps, yields = sim.registers, 0, 0
    mem.iyl = lambda: r[11]                              # IYl
    while r[24] != 0x3333:
        if r[24] == syms['wk_out']:
            yields += 1
            r[0], r[24] = 1, syms['wk_enter']            # next slice: not the first, so resume
            continue
        if steps > 3_000_000:
            raise AssertionError('dispatch did not return')
        sim.opcodes[mem[r[24]]]()
        steps += 1
    if mem.mmu1 != 68 or mem.ram != list(ram):
        raise AssertionError('dispatch failed slot/RAM contract')
    return {'ready': pages[69][0x1EE0], 'matched': pages[69][0x1EEF], 'yields': yields, 'steps': steps}


def sprite_port(pages, state, port, value):
    """4-bit pattern RAM model: 303B selects (slot * 2 + bit 7) * 128, 5B writes and advances. True if handled."""
    if port == 0x303B:
        state[0] = ((value & 0x3F) * 2 + (value >> 7)) * 128
        state[1:] = [(value & 0x7F) * 5]
        return True
    if port & 0xFF == 0x5B:
        pages['sprite'][state[0]] = value
        state[0] += 1
        return True
    if port & 0xFF == 0x57:                              # attributes: slot from 303B, 5 bytes or 4 without the extended bit
        state[1] = state[1] if len(state) > 1 else 0
        slot, i = state[1] // 5, state[1] % 5
        pages['attr'][slot * 5 + i] = value
        if i == 3 and not value & 0x40:
            pages['attr'][slot * 5 + 4] = 0
            state[1] = (slot + 1) * 5
        else:
            state[1] += 1
        return True
    return False


def attributes_expected(out, previous=0):
    """Five attribute bytes per list entry, signed tile positions, 4-bit pattern = slot."""
    a = bytearray()
    for slot, col, row in out:
        x = ((col - 256 if col > 127 else col) * 8 + 32) & 0x1FF
        a += bytes((x & 255, (row * 8 + 80) & 255, x >> 8, 0xC0 | slot >> 1, 0x80 | (slot & 1) << 6))
    return bytes(a)


def patterns_uploaded(page, sprite, pattern_pages, out):
    """(ok, count): every slot of the list holds its owner's 128 bytes."""
    ids = [page[SEL_SLOT_ID + 2 * s] | page[SEL_SLOT_ID + 2 * s + 1] << 8 for s in range(64)]
    for slot in {e[0] for e in out}:
        pid = ids[slot]
        at = pid % 64 * 128
        if bytes(sprite[slot * 128:slot * 128 + 128]) != bytes(pattern_pages[85 + pid // 64][at:at + 128]):
            return False, slot
    return True, 0


SPRITE_NEXTREGS = (0x15, 0x19, 0x1C, 0x40, 0x41, 0x43, 0x4B, 0x6B, 0x6E)


class SelectMemory(DispatchMemory):
    """+ page 82 at slot 2 (its state writable) and page 83 at slot 1."""
    mmu2 = 82
    spr = None

    def write_port(self, regs, port, value, *args):
        if self.spr is None:
            self.spr = [0, 0]
        sprite_port(self.pages, self.spr, port, value)

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        if 0x4000 <= a < 0x6000:
            return self.pages[82][a - 0x4000]
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if 0x4000 <= a < 0x6000:
            if a < 0x5000:
                raise AssertionError('selection wrote its code')
            self.pages[82][a - 0x4000] = v
        else:
            super().__setitem__(a, v)

    def nextreg(self, reg, value):
        if reg in SPRITE_NEXTREGS:
            self.pages.setdefault('nr', {})[reg] = value
        elif reg == 0x51 and (value == 83 or 85 <= value < 96):
            self.mmu1 = value
        elif reg == 0x52 and value == 82:
            self.mmu2 = value
        else:
            super().nextreg(reg, value)


def select_log(records):
    """Page-68 log bytes for (image, x, y) draws with an empty stream (selection does not read the rows)."""
    return [bytes((0, 0, x & 255, y & 255, image, 0, 0)) for image, x, y in records]


def run_select(page82, page83, log, yield_every=0, drop_after=None, code=None, patterns=None, sprite=None, attr=None):
    """Assembled selection from wk_select to its RET (or abandoned after drop_after yields, as a 3c drop)."""
    from . import simpool, z80n
    from .dizzy6 import _rw_simulator
    syms = {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}
    pages = {69: cw_work_renderer(), 82: bytearray(page82), 83: bytearray(page83), 68: bytearray(8192)}
    pages.update({p: bytearray(8192) for p in range(85, 96)} if patterns is None else patterns)
    pages['sprite'] = bytearray(16384) if sprite is None else bytearray(sprite)
    pages['attr'] = bytearray(640) if attr is None else bytearray(attr)
    if code is not None:
        pages[82][:len(code)] = code
    at = 0x900
    for record in log:
        pages[68][at:at + len(record)] = record
        at += len(record)
    pages[68][0x3F4] = len(log)
    pages[69][0x1EE0] = 1                                # DX_READY
    pages[69][0x1EC2] = 82                               # WK_M2
    mem = SelectMemory(bytes(65536), pages)
    mem.yield_every = yield_every
    regs = [0] * 30
    regs[12], regs[24], regs[14], regs[27] = 0x1C3E, 0x4000, 0xFE, 2
    pages[69][0x1C3E:0x1C40] = (0x3333).to_bytes(2, 'little')
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.select')
    sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    r, steps, yields, dropped = sim.registers, 0, 0, False
    mem.iyl = lambda: r[11]
    while r[24] != 0x3333:
        if r[24] == syms['wk_out']:
            yields += 1
            if drop_after is not None and yields >= drop_after:
                dropped = True
                break
            r[0], r[24] = 1, syms['wk_enter']
            continue
        if steps > 3_000_000:
            raise AssertionError('selection did not return')
        sim.opcodes[mem[r[24]]]()
        steps += 1
    if not dropped and mem.mmu1 != 68:
        raise AssertionError('selection left slot 1 at page %d' % mem.mmu1)
    return {'page': pages[82], 'attr': pages['attr'], 'sprite': pages['sprite'], 'ready': pages[82][SEL_READY], 'n': pages[82][SEL_N], 'yields': yields,
            'steps': steps, 'cycles': r[25], 'dropped': dropped}


def select_list(page):
    n = page[SEL_N]
    return [tuple(page[SEL_LIST + 3 * i:SEL_LIST + 3 * i + 3]) for i in range(n)]


def select_checks():
    """Assembled selection/store from a crafted index: against the oracle over a long scripted sequence with
    yields, drops, eviction, protection, over-capacity, list overflow, wrap-around and every controlled edge."""
    import random
    rng = random.Random(0x1A2B)
    page83 = bytearray(8192)
    index, at, pid = {}, 0x600, 0
    for image in range(180):                             # 1-3 chunks, cells and shared patterns
        n = rng.randint(1, 3)
        chunks = []
        for j in range(n):
            share = rng.random() < 0.2 and pid
            chunks.append((2 * j, rng.choice((0, 2)), rng.randint(1, 15), rng.randrange(pid) if share else pid))
            pid += 0 if share else 1
        left, top = rng.choice((0, 255, 2)), rng.choice((0, 254, 1))
        page83[image * 6:image * 6 + 6] = bytes((1, n, at & 255, at >> 8, left, top))
        for i, c in enumerate(chunks):
            page83[at + 5 * i:at + 5 * i + 5] = bytes((c[0], c[1], c[2], c[3] & 255, c[3] >> 8))
        at += 5 * n
        index[image] = (left, top, chunks)
    missing = 200                                        # header invalid: not ready
    pattern_pages = {p: bytearray(rng.randrange(256) for _ in range(8192)) for p in range(85, 96)}
    code = bytes.fromhex(load_profile()['hooks']['cwsel'])
    counts = Counter()

    def scripted(code_used=None, frames=None):
        page, state, sprite, attr = select_page(), SelectState(), bytearray(16384), bytearray(640)
        if code_used is not None:
            page[:len(code_used)] = code_used
        for k, f in enumerate(frames):
            log, every, drop = f
            before = SelectState(page).tuple()
            if before != state.tuple():
                raise AssertionError('state diverged before frame %d' % k)
            r = run_select(page, page83, select_log(log), yield_every=every, drop_after=drop, code=code_used, patterns=pattern_pages, sprite=sprite, attr=attr)
            page, sprite, attr = r['page'], r['sprite'], r['attr']
            if r['dropped']:
                counts['dropped attempts'] += 1
                state = SelectState(page)                 # whatever partial state it left is the new truth
                continue
            ready, out = select_expected(state, index, [dict(image=i, x=x, y=y) for i, x, y in log])
            if r['ready'] != ready or select_list(page) != out:
                raise AssertionError('frame %d: ready %d/%d or list differs' % (k, r['ready'], ready))
            if SelectState(page).tuple() != state.tuple():
                raise AssertionError('frame %d: state differs' % k)
            if ready:
                good, slot = patterns_uploaded(page, sprite, pattern_pages, out)
                if not good:
                    raise AssertionError('frame %d: slot %d pattern not uploaded' % (k, slot))
                counts['frames with all patterns verified'] += 1
                if bytes(attr[:5 * len(out)]) != attributes_expected(out):
                    raise AssertionError('frame %d: attributes differ' % k)
                if any(attr[5 * i + 3] for i in range(len(out), 128)):
                    raise AssertionError('frame %d: stale sprite left visible' % k)
                counts['frames with attributes verified'] += 1
            counts['ready frames' if ready else 'not-ready frames'] += 1
            counts['yields'] += r['yields']
        return page

    def frame_set(n, seed):
        rn = random.Random(seed)
        pool = rn.sample(range(180), 40)
        out = []
        for k in range(n):
            if k % 37 == 36:
                log = [(i, rn.randint(2, 20), rn.randint(2, 12)) for i in range(70)]   # over capacity
            elif k % 53 == 52:
                log = [(7, 5, 5)] * 130                  # list overflow
            elif k % 41 == 40:
                log = [(missing, 0, 0)]
            else:
                if k % 11 == 0:
                    pool = rn.sample(range(180), 40)
                log = [(rn.choice(pool), rn.choice((rn.randrange(256), 3, 30, 31, 32, 255, 250)),
                        rn.choice((rn.randrange(256), 2, 17, 18, 255))) for _ in range(rn.randint(0, 14))]
            out.append((log, rn.choice((0, 0, 1, 2, 3, 5)), (rn.randint(1, 8) if rn.random() < 0.15 else None)))
        return out

    scripted(frames=frame_set(400, 77))
    # protection: slots of the current and pending frames survive a demanding frame
    variants = {}
    b = bytes.fromhex
    at = code.index(b('A628'))                            # and (hl); jr z,sl_take
    variants['protection ignored'] = code[:at] + b('AF') + code[at + 1:]
    at = code.index(b('3A4050'))                          # ld a,(LRU_HEAD): walk from the newest instead
    variants['eviction takes the newest'] = code[:at + 1] + b('4150') + code[at + 3:]
    at = code.index(b('3E083248'))                        # bursts of a pattern
    variants['upload one burst short'] = code[:at + 1] + b('07') + code[at + 2:]
    at = code.index(b('360021'))                          # flag cleared after the pattern
    variants['uploaded flag not cleared'] = code[:at + 1] + b('01') + code[at + 2:]
    remaps = [i for i in range(len(code)) if code[i:i + 6] == b('3A0A50ED9251')]     # sl_yupn, sl_yup, sl_ychunk, sl_yscan
    if len(remaps) != 4:
        raise AssertionError('resume remap pattern %d' % len(remaps))
    variants['slot-1 remap on upload resume removed'] = code[:remaps[1]] + bytes(6) + code[remaps[1] + 6:]
    at = code.index(b('C650'))                            # Y = 32 + 48 + row * 8
    variants['sprite Y offset wrong'] = code[:at + 1] + b('58') + code[at + 2:]
    at = code.index(b('3A4E5090'))                        # sprites to hide
    variants['stale sprites not hidden'] = code[:at + 3] + b('AF') + code[at + 4:]
    at = code.index(b('E60F57'))
    variants['role rotation wrong'] = code[:at + 1] + b('03') + code[at + 2:]
    at = code.index(b('FE12'))
    variants['row limit 24'] = code[:at + 1] + b('18') + code[at + 2:]
    variants['slot-1 remap on chunk resume removed'] = code[:remaps[2]] + bytes(6) + code[remaps[2] + 6:]
    for name, broken in variants.items():
        try:
            scripted(code_used=broken, frames=frame_set(400, 77))
        except (AssertionError, KeyError):
            counts['control detected: ' + name] += 1
        else:
            raise AssertionError('control not informative: ' + name)
    from . import runchecks
    checks = []
    runchecks.measured(checks, 'selection frames equal to the oracle', counts['ready frames'] + counts['not-ready frames'])
    runchecks.measured(checks, 'yields exercised', counts['yields'])
    runchecks.measured(checks, 'drops exercised', counts['dropped attempts'])
    runchecks.measured(checks, 'negative controls detected', sum(v for k, v in counts.items() if k.startswith('control detected')), expected=len(variants))
    return {'counts': dict(counts), 'checks': checks, 'scope': 'assembled selection/store (page 82) on a crafted index and scripted frames; simulator, no hardware'}


def dispatch_checks():
    """Assembled window dispatch on a crafted store: exact hits, duplicates, yields and every miss."""
    ram, regs = driver_fixture()
    drv = run_loading_driver(ram, regs)
    store = driver_store(drv)
    expected = driver_expected(ram)
    valid = [i for i, e in enumerate(expected) if e not in (None, 'reject') and store[79][0x800 + 16 * i]]
    streams = {}
    dup = next(i for i in valid if streams.setdefault(expected[i][0], i) != i)
    canon = streams[expected[dup][0]]
    def record(image, ptr=None):
        d = actor_descriptor(ram, image)
        pos = d['pointer'] + 1
        out = bytearray((0, 0, 3, 4, image, ram[d['pointer']]))
        while ram[pos]:
            width = ram[pos]
            out += bytes(ram[pos:pos + 3 + width])
            pos += 3 + width
        out.append(0)
        return bytes(out)
    log = [record(canon), record(dup), record(valid[0]), record(valid[-1])]
    counts = Counter()
    code = bytes.fromhex(load_profile()['hooks']['cwdx'])
    def check(name, ram2=None, log2=None, store2=None, want=None, **kw):
        ram2, log2, store2 = ram2 if ram2 is not None else ram, log2 if log2 is not None else log, store2 or store
        result = run_dispatch(ram2, store2, log2, **kw)
        state = bytearray(8192)
        at = 0x900
        for rec in log2:
            state[at:at + len(rec)] = rec
            at += len(rec)
        state[0x3F2:0x3F4], state[0x3F4], state[0x3F5] = at.to_bytes(2, 'little'), len(log2), kw.get('overflow', 0)
        oracle, reasons = dispatch_expected(store2, ram2, state)
        oracle = 0 if kw.get('scene') == 0 else oracle
        if want is not None and oracle != want:
            raise AssertionError('%s: oracle says %d' % (name, oracle))
        if result['ready'] != oracle:
            raise AssertionError('%s: dispatch %d, oracle %d %s' % (name, result['ready'], oracle, reasons))
        counts[name] += 1
        return result
    good = check('all draws exact, duplicate index included', want=1)
    if good['matched'] != len(log):
        raise AssertionError('matched count %d' % good['matched'])
    for every in (1, 2, 3, 5, 7):
        out = check('same result with a yield every Nth poll', want=1, yield_every=every)
        if not out['yields']:
            raise AssertionError('no yields at every=%d' % every)
        counts['yields taken (control input)'] += out['yields']
    check('scene not ready', want=0, scene=0)
    check('log overflow', want=0, overflow=1)
    bad_image = next(i for i, e in enumerate(expected) if e == 'reject')
    check('no entry', want=0, log2=[record(valid[0])[:4] + bytes((bad_image,)) + record(valid[0])[5:]])
    for what, delta in (('bitmap', 0), ('attribute', 8)):
        d = actor_descriptor(ram, valid[0])
        tile = d['tiles'][0][2]
        mutated = list(ram)
        a = 0xDC00 + 8 * tile if what == 'bitmap' else 0xFC00 + tile
        mutated[a] ^= 1
        check('live %s changed: miss' % what, ram2=mutated, want=0, yield_every=2)
    # geometry: dy of the first run (first image in the log) changed
    mutated = list(ram)
    d = actor_descriptor(ram, canon)
    mutated[d['pointer'] + 3] ^= 1
    check('live geometry changed: miss', ram2=mutated, want=0)
    # generation and FLASH in the entry
    wrong = {p: bytearray(v) for p, v in store.items()}
    wrong[79][0x800 + 16 * canon + 12] = 1
    check('entry generation: miss', store2={p: bytes(v) for p, v in wrong.items()}, want=0)
    # stored length one short: comparison of the terminator cannot pass unnoticed
    short = {p: bytearray(v) for p, v in store.items()}
    entry = 0x800 + 16 * canon
    short[79][entry + 4] -= 1
    short = {p: bytes(v) for p, v in short.items()}
    check('stored length differs: miss', store2=short, want=0)
    # negative controls (the broken dispatch's own code must disagree with the oracle)
    h = code.hex().upper()
    variants = {}
    b = bytes.fromhex
    pat = b('1ABE')
    if code.count(pat + b('C2')) < 8:
        raise AssertionError('bitmap compare pattern')
    variants['bitmap comparison removed'] = code.replace(pat, b('1ABF'), 1)
    resume = b('3AE51EED9251')                           # the tile yield's slot-1 remap
    if code.count(resume) != 2:
        raise AssertionError('resume remap pattern %d' % code.count(resume))
    at = code.rindex(resume)
    variants['slot-1 remap on resume removed'] = code[:at] + bytes(len(resume)) + code[at + len(resume):]
    size = b('ED5BE81EB7ED52C2')
    if code.count(size) != 1:
        raise AssertionError('size compare pattern')
    at = code.index(size)
    variants['stored length not compared'] = code[:at + 7] + bytes(3) + code[at + 10:]
    cases = {'bitmap comparison removed': {'ram2': None, 'mut': True},
             'slot-1 remap on resume removed': {'yield_every': 2},
             'stored length not compared': {'store2': short}}
    for name, broken in variants.items():
        kw = dict(cases[name])
        if kw.pop('mut', False):
            kw['ram2'] = list(ram)
            kw['ram2'][0xDC00 + 8 * actor_descriptor(ram, valid[0])['tiles'][0][2]] ^= 1
        kw = {k: v for k, v in kw.items() if v is not None}
        try:
            check(name, code=broken, **kw)
        except (AssertionError, KeyError):
            counts['control detected: ' + name] += 1
        else:
            raise AssertionError('control not informative: ' + name)
    return {'counts': dict(counts), 'scope': 'assembled dispatch (page 69) from a crafted store and log; simulator, no hardware'}


def driver_boundary_state(path):
    """Original RAM and registers at the first 8EF9 of a recording."""
    import skoolkit.rzxplay as rp
    from skoolkit.snapshot import Snapshot
    from types import SimpleNamespace
    from .rzx import parse_rzx, InputRecording
    blocks = parse_rzx(str(path))
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    ctx.total_frames = 2000
    class Sink:
        def write(self, text):
            pass
    ctx.tracefile, hold = Sink(), []
    def event(tf, context, fc, pc):
        if pc == 0x8EF9 and not hold:
            hold.append((list(context.simulator.memory), list(context.simulator.registers), context.frame_count))
            context.stop = True
    old, rp.trace_exec = rp.trace_exec, event
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=2000, force=False)
        while blocks and not ctx.stop:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
    finally:
        rp.trace_exec = old
    if not hold:
        raise AssertionError('8EF9 not reached in %s' % path)
    return hold[0]


def driver_level_check(reference, level):
    """One level: run the assembled driver on the real table at 8EF9, against the oracle."""
    ram, regs, frame = driver_boundary_state(Path(reference) / ('Inferno%d.rzx' % level))
    expected = driver_expected(ram)
    result = run_loading_driver(ram, regs)
    counts = driver_compare(result, expected)
    counts.update(driver_index_compare(result, ram, expected))
    return {'level': level, 'frame': frame, 'counts': counts, 'driver_ms': result['equivalent_T'] / 3500,
            'instructions': result['instructions'], 'scope': 'executed assembly in the simulator; 28 MHz model, read allowance; no hardware'}


class ModalPatch(CapturePatch):
    """Original gameplay-return boundary; no modal drawing instruction is bypassed."""
    def __init__(self, code=None):
        h = load_profile()['hooks']
        self.code = bytes.fromhex(h['modal']) if code is None else code
        self.rom = loader_rom()
        org = int(h['syms']['modal_hide'], 16)
        if org + len(self.code) >= 0x3D00 or any(v != 255 for v in self.rom[org:org + len(self.code)]):
            raise ValueError('modal hook overlaps live ROM')
        self.rom[org:org + len(self.code)] = self.code
        self.sites = {0x9019: (bytes.fromhex('31D586'), b'\xC3' + org.to_bytes(2, 'little'))}
        self.stops = {0x9019: 0x901C}
        self.site_bytes = set(range(0x9019, 0x901C))


class ModalMemory(CaptureMemory):
    def __init__(self, ram, state, patch, display=None):
        super().__init__(ram, state, patch)
        self.nr = dict(display or {0x6B:0x8B, 0x15:0x01, 0x69:0x80, 0x62:0x40})
        self.selected, self.display_writes = 0, []

    def nextreg(self, reg, value):
        if reg in (0x6B, 0x15, 0x69, 0x62):
            if self.speed != 3 or self.mmu0 != 68:
                raise AssertionError('modal display write outside private domain')
            self.nr[reg] = value
            self.display_writes.append((reg, value))
        else:
            super().nextreg(reg, value)

    def write_port(self, regs, port, value, *args):
        if port != 0x243B:
            raise AssertionError('modal wrote an unowned port')
        self.selected = value

    def read_port(self, regs, port):
        if port != 0x253B or self.selected not in self.nr:
            raise AssertionError('modal read an unowned port')
        return self.nr[self.selected]


def modal_checks(capture):
    """Actual original-replay return state, plus visibility bit and stale-phase controls."""
    data = json.loads(Path(capture).read_text())
    if data['desync'] or not data.get('samples'):
        raise AssertionError('modal check needs an original replay sample without desync')
    patch, counts, maximum = ModalPatch(), Counter(), 0
    for sample in data['samples']:
        if sample['pc'] != 0x9019:
            raise AssertionError('wrong modal entry sample')
        ram = [0] * 16384 + sample['memory']['16384']
        regs = sample['registers']
        for value in range(256):
            state = bytearray(8192)
            state[0x3F6] = 2
            display = {0x6B:value, 0x15:value ^ 0xA5, 0x69:255-value, 0x62:0x40}
            memories = []
            def factory(m, s, p):
                mem = ModalMemory(m, s, p, display)
                memories.append(mem)
                return mem
            result, cost, steps = run_capture(patch, ram, regs, state, 0x9019, factory)
            want = {r:v & (0xFE if r == 0x15 else 0x7F) for r,v in display.items()}
            want[0x62] = 0
            if memories[0].nr != want or result[0x3F6] != 0 or memories[0].display_writes[0] != (0x62, 0):
                raise AssertionError('modal visibility or pending-phase invalidation failed')
            maximum = max(maximum, cost)
            counts['display-bit preservation cases'] += 1
        for register in (0x6B, 0x15, 0x69, 0x62):
            code = bytearray(patch.code)
            instruction = bytes((0xED, 0x91, 0x62, 0)) if register == 0x62 else bytes((0xED, 0x92, register))
            off = code.index(instruction)
            code[off:off+len(instruction)] = bytes(len(instruction))
            memories = []
            def factory(m, s, p):
                mem = ModalMemory(m, s, p)
                memories.append(mem)
                return mem
            run_capture(ModalPatch(code), ram, regs, state, 0x9019, factory)
            mask = 0x40 if register == 0x62 else 1 if register == 0x15 else 128
            if not memories[0].nr[register] & mask:
                raise AssertionError('missing-hide control was not informative')
            counts['missing-hide control detected'] += 1
        bad = list(ram)
        bad[0x9019] ^= 1
        try:
            patch.apply_memory(bad)
        except ValueError:
            counts['modal site refusal'] += 1
        else:
            raise AssertionError('modal site refused no changed bytes')
    return {'counts': dict(counts), 'entry_frames': [s['frame'] for s in data['samples']],
            'max_equivalent_T': maximum, 'max_added_ms': maximum / 3500,
            'scope': 'assembled hide at sampled original gameplay return; all other modal paths and integration remain open'}


class FramePatch(CapturePatch):
    """Capture + modal cancellation + hidden post-copy scenery preparation."""
    def __init__(self):
        super().__init__()
        h = load_profile()['hooks']
        for block, symbol in (('modal','modal_hide'),('framehook','frame_hook')):
            code, org = bytes.fromhex(h[block]), int(h['syms'][symbol],16)
            if org+len(code) >= 0x3D00 or any(v != 255 for v in self.rom[org:org+len(code)]):
                raise ValueError('frame hook overlaps live ROM')
            self.rom[org:org+len(code)] = code
        self.sites[0x9019] = bytes.fromhex('31D586'), b'\xC3'+int(h['syms']['modal_hide'],16).to_bytes(2,'little')
        self.sites[0x8F95] = bytes.fromhex('3A49AC'), b'\xC3'+int(h['syms']['frame_hook'],16).to_bytes(2,'little')
        self.stops.update({0x9019:0x901C, 0x8F95:0x8F98})
        self.site_bytes = {a+j for a,(old,new) in self.sites.items() for j in range(len(old))}
        self.renderer = bytearray(8192)
        for block,symbol in (('textmap','render_textmap'),('queue','queue_frame'),('prepare','prepare_frame'),('display','setup_display')):
            org = int(h['syms'][symbol],16)
            code = bytes.fromhex(h[block])
            self.renderer[org:org+len(code)] = code
        for phase in range(2):
            self.renderer[0x400+phase*256:0x500+phase*256] = bytes((a&127)*2 for a in range(256))


class FrameMemory(CaptureMemory):
    def __init__(self, ram, state, patch, previous=None, display=None):
        super().__init__(ram, state, patch)
        self.pages[69] = bytearray(previous[69]) if previous else bytearray(patch.renderer)
        self.pages[14] = bytearray(previous[14]) if previous else bytearray([0xE3]*8192)
        self.mmu1, self.mmu2 = 255, 10
        self.nr = dict(display or {0x6B:0x0B, 0x6E:0x80, 0x7F:0})
        self.selected, self.text_writes = 0, set()
        self.cost_components = Counter()

    def __getitem__(self, a):
        if isinstance(a,slice):
            return [self[i] for i in range(*a.indices(65536))]
        if self.speed == 3:
            self.fast_reads += 1
        if a < 8192 and self.mmu0 != 255:
            return self.pages[self.mmu0][a]
        if 8192 <= a < 16384 and self.mmu1 != 255:
            return self.pages[self.mmu1][a-8192]
        if 0x4000 <= a < 0x6000 and self.mmu2 == 14:
            return self.pages[14][a-0x4000]
        return self.rom[a] if a < 16384 else self.ram[a]

    def __setitem__(self, a, v):
        if a < 8192 and self.mmu0 != 255:
            self.pages[self.mmu0][a] = v
        elif 8192 <= a < 16384 and self.mmu1 != 255:
            self.pages[self.mmu1][a-8192] = v
        elif 0x4000 <= a < 0x6000 and self.mmu2 == 14:
            offset = a-0x4000
            front = 1 if self.nr[0x6E] == 0x86 else 0
            if self.nr[0x6B]&128 and (front*0x600 <= offset < front*0x600+0x600 or
                    0xC00+front*0x800 <= offset < 0x1400+front*0x800):
                raise AssertionError('frame worker changed visible map/definitions')
            self.pages[14][offset] = v
            self.text_writes.add(offset)
        elif a >= 16384:
            raise AssertionError('frame wrote original game RAM')
        else:
            raise AssertionError('frame wrote unmapped ROM')

    def nextreg(self, reg, value):
        if reg == 0x50 and value in (68,69,255):
            self.mmu0 = value
        elif reg == 0x51 and value in (68,255):
            self.mmu1 = value
        elif reg == 0x52 and value in (14,10):
            self.mmu2 = value
        elif reg == 0x07 and value in (0,3):
            if value == 0 and (self.mmu1 != 255 or self.mmu2 != 10):
                raise AssertionError('frame restored speed before original mapping')
            self.speed = value
        else:
            raise AssertionError('hidden frame preparation changed display/unowned register')

    def write_port(self, regs, port, value, *args):
        if port != 0x243B:
            raise AssertionError('frame wrote unowned port')
        self.selected = value

    def read_port(self, regs, port):
        if port != 0x253B or self.selected not in self.nr:
            raise AssertionError('frame read unowned register')
        return self.nr[self.selected]


def run_frame(patch, ram, registers, state, previous=None, display=None):
    memories = []
    def factory(m,s,p):
        mem = FrameMemory(m,s,p,previous,display)
        memories.append(mem)
        return mem
    result,cost,steps = run_capture(patch,ram,registers,state,0x8F95,factory,limit=200000)
    mem = memories[0]
    ready = mem.pages[69][0x1EAC]
    if mem.mmu1 != 255 or mem.mmu2 != 10 or mem.pages[69][0x1EA1]:
        raise AssertionError('frame mapping or premature sprite/display readiness')
    if ready:
        half, flash = mem.pages[69][0x1E80:0x1E82]
        expected_ram = list(ram)
        expected_ram[0x9B00:0x9F80] = state[0x400:0x880]
        data = mem.pages[14]
        for cell,tile in enumerate(map_tiles(expected_ram)):
            at = half*0x600+(cell//32)*80+(cell%32)*2
            slot = data[at]+((data[at+1]&1)<<8)
            attr = data[at+1]>>1
            raw = bytes(data[0xC00+slot*8:0xC08+slot*8])+bytes((attr,))
            if tile_pixels(raw) != expected_tile(expected_ram,tile,flash):
                raise AssertionError('post-copy frame pixels differ from clean scenery')
    elif mem.text_writes:
        raise AssertionError('unready frame wrote display memory')
    return {'ready':ready,'equivalent_T':cost,'added_ms':cost/3500,'instructions':steps,
            'cost_components_T':dict(mem.cost_components),
            'pages':{p:bytes(v) for p,v in mem.pages.items()}}


def frame_units(patch, fixture):
    ram, regs, state = fixture
    counts = Counter()
    good = run_frame(patch,ram,regs,state)
    for front in (0,1):
        result = run_frame(patch,ram,regs,state,good['pages'],{0x6B:0x8B,0x6E:0x86 if front else 0x80,0x7F:0})
        if not result['ready'] or result['pages'][69][0x1E80] != 1-front:
            raise AssertionError('frame selected the visible buffer')
        counts['frame inactive buffer unit'] += 1
    pending = dict(good['pages'])
    pending[69] = bytearray(pending[69])
    pending[69][0x1EA0:0x1EA3] = bytes((7,1,1))
    for ack, expected in ((6,0),(7,1)):
        result = run_frame(patch,ram,regs,state,pending,{0x6B:0x8B,0x6E:0x80,0x7F:ack})
        if result['ready'] != expected:
            raise AssertionError('pending frame ownership not respected')
        counts['frame pending/ack unit'] += 1
    for phase in (0,1):
        inactive = bytearray(state)
        inactive[0x3F6] = phase
        if run_frame(patch,ram,regs,inactive,good['pages'])['ready']:
            raise AssertionError('incomplete capture prepared a frame')
        counts['frame phase guard'] += 1
    broken = FramePatch()
    broken.rom[int(load_profile()['hooks']['syms']['frame_hook'],16)] = 0
    try:
        run_frame(broken,ram,regs,state)
    except AssertionError as e:
        if 'interrupt-enabled' not in str(e):
            raise
        counts['frame unsafe-DI control detected'] += 1
    else:
        raise AssertionError('frame unsafe-DI control not detected')
    stale = dict(good['pages'])
    stale[69] = bytearray(stale[69])
    off = stale[69].index(bytes.fromhex('CD0000'),0x700,0x800)
    stale[69][off:off+3] = bytes(3)
    changed = list(ram)
    clean = list(ram)
    clean[0x9B00:0x9F80] = state[0x400:0x880]
    tile = next(t for t in map_tiles(clean) if (ram[0xFC00+t]&7) != ((ram[0xFC00+t]>>3)&7))
    changed[0xDC00+tile*8] ^= 255
    try:
        run_frame(patch,changed,regs,state,stale)
    except AssertionError as e:
        if 'frame pixels' not in str(e):
            raise
        counts['frame skipped-render control detected'] += 1
    else:
        raise AssertionError('frame skipped-render control not detected')
    return counts


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
        rb = self.regblock - 0x2000            # the stub writes 20 register bytes there at boot
        if any(v != 255 for v in self.page[rb:rb + 20]):
            raise ValueError('hook code in the stub register block %04X-%04X' % (self.regblock, self.regblock + 19))
        head = bytearray(8192)                  # page 80: the hooks' timing helpers (CW_CLK = 0:
        head[:len(self.capture.head)] = self.capture.head   # no window runs, so no X is measured)
        self.extra_banks[CW_PAGE // 2] = bytes(head) + (head_tail if work and driver else bytes(8192))
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


def continuation_case(snapshot, blocks, level, limit=2_000_000, pulse_blocks=None, handoff=0x718C, input_byte=255):
    """Crafted original 7131 invocation, not a recorded transition or full-game proof.

    Default stops at CALL Nb (718C). Extended initialization stops in Nb's A2FF input
    routine, with common logical HALT wake-ups, not timed IRQ or continuous-game proof.
    Both machines run the game's 7131 loader and Na initializer. One uses the original ROM decoder;
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
            return input_byte

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
    calls, steps, halt_irqs = 0, 0, 0
    refresh_reads = Counter()
    convergences, pending = [], False
    original_cursor = cursor
    while patched.registers[24] != handoff or steps == 0:
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
            if po[pc] == 0x76 and handoff == 0x718C:
                raise RuntimeError('unexpected HALT before Nb handoff at %04X' % pc)
            if oo[pc] == 0xED and oo[(pc + 1) & 65535] == 0x5F:
                # R is a nondeterministic input (tape pulse acquisition and bank hooks have
                # different M1 counts). Compare continuation under the SAME R input; report
                # each such site rather than quietly treating derived A/RAM as exempt.
                original.registers[15] = patched.registers[15]
                refresh_reads['%04X' % pc] += 1
            original.opcodes[oo[pc]]()
            patched.opcodes[po[pc]]()
            if po[pc] == 0x76 and handoff != 0x718C:
                if not original.registers[26] or not patched.registers[26]:
                    raise AssertionError('initialization HALT with interrupts disabled')
                for machine in (original,patched):
                    # Logical common wake-up, not wall-clock IRQ scheduling. SkoolKit's
                    # HALT opcode itself advances PC only inside its timed IRQ window.
                    machine.registers[24] = (pc+1) & 65535
                    if not machine.accept_interrupt(machine.registers,machine.memory,pc):
                        raise AssertionError('initialization HALT IRQ rejected')
                halt_irqs += 1
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
            'halt_irqs': halt_irqs,
            'boundary_iff': patched.registers[26], 'boundary_im': patched.registers[27],
            'boundary_bytes': bytes(po.ram[handoff:handoff+16]).hex(),
            'boundary_live_candidates': len(live_actor_candidates(po.ram)),
            'next_block': po.pages[STATE_PAGE][0], 'handoff_sp': patched.registers[12], 'handoff_pc': patched.registers[24],
            'synchronized_refresh_reads': dict(refresh_reads),
            'physical_return_convergences': convergences}


def continuation_tests(folder, pulse=False, initialization=False):
    folder = Path(folder)
    blocks = tape_blocks(folder / 'Inferno.tzx')
    results = []
    timed = None
    if pulse:
        from skoolkit.tape import parse_tzx
        timed = [b for b in parse_tzx(str(folder / 'Inferno.tzx'), timings=True).blocks if b.data]
    # Tape ordinals 0..5 initialize the six levels; ordinal 6 is the ending.
    for level in (range(6) if initialization else range(7)):
        # Every pair loads from the live level-1 state; no independent target-level restore.
        results.append(continuation_case(folder / 'Inferno.z80', blocks, level, pulse_blocks=timed,
                                         handoff=0xA2FF if initialization else 0x718C))
    if initialization:
        return {'cases':results,'scope':'crafted 7131 invocations through Nb to A2FF input routine; common logical HALT IRQ wake-up, byte ROM oracle/equal R inputs; not timed IRQ or continuous gameplay'}
    return {'cases': results, 'scope': ('actual TZX pulses versus bank loader to 718C; equal R inputs; Nb not executed' if pulse else 'crafted 7131 invocations to 718C; Na executed, Nb loaded but not executed; canonical bytes/equal R inputs')}


# --- Copier window (claude/inferno-copier-window) ------------------------------------------
# Original pacing: the copier 9790 OUTs the A700 beeper buffer once per cell and calls the 9907
# limiter after row 6; the next interrupt resumes it. Milestone 1 replaced 9790..97FB by the
# translated head in page 80 (no OUT, exact RAM/registers/R, logged OUT changes). Milestone 2
# OUTs each change at its original T and enters 9907 at the original time, polled on CTC
# channel 3, with frame IRQs inside the window taken by cw_irq (page 80 byte 0 = IM2 JR offset).
CW_PAGE = 80
CW_ROWS = 13
CW_CELLS = 32 * CW_ROWS
CW_HEAD_T0, CW_HEAD_PER_G = 79477, 101
CW_CLK, CW_X, CW_NIRQ = 0x1810, 0x1811, 0x181D   # page-80 variables (asm EQUs)
CW_KT = 0x1847             # signed T: measured speed-switch pair excess over the model (cw_cal)
CW_CTC_PORT, CW_TICK = 0x1B3B, 32                # CTC channel 3, prescaler 256
CW_ISR = (94, 10)          # original no-op ISR (998E = 0): T and M1 incl. the IM2 acknowledge
CW_INT_PULSE = 32          # /INT length, 3.5MHz T
CW_TOL = 56                # OUT/9907 tolerance: one 32 T tick, +-16 rounding, poll latency


def cw_out_t(k, g):
    """Original uncontended T of the OUT for head cell k (from 9790 entry); g = tiles >=16 before it."""
    r = k // 32
    return 121 + (r + 1) * 54 + r * 66 + k * 187 + (19 if k > 255 else 0) + 69 + CW_HEAD_PER_G * g


class CopierWindowPatch(CapturePatch):
    """Capture patch whose 8F92 tail enters the copier window instead of JP 9790.

    window_only: the milestone-2 vehicle installs only the 8F92 site (cap_done, then the window);
    no capture hooks run before it, so the earlier-hook time X is 0 at run time.
    work (milestone 3b): the 8F95 work (prepare_frame + render_textmap) runs as a page-69 coroutine
    in the window's waits (cw_work) and is finished at 8F95 (JP wk_hook; R restored there)."""
    def __init__(self, head=None, window_only=False, rom_code=None, work=False, work_code=None):
        super().__init__()
        h = load_profile()['hooks']
        rom_code = bytes.fromhex(h['cwrom']) if rom_code is None else bytes(rom_code)
        org = self.syms['cw_go']
        if org + len(rom_code) >= 0x3D00 or any(v != 255 for v in self.rom[org:org + len(rom_code)]):
            raise ValueError('copier-window trampoline overlaps live ROM')
        self.rom[org:org + len(rom_code)] = rom_code
        tail = self.syms['cap_done_tail']
        if bytes(self.rom[tail:tail + 12]) != bytes.fromhex('ED9150FFED910700FBC39097'):
            raise ValueError('unexpected cap_done tail')
        self.rom[tail:tail + 3] = b'\xC3' + org.to_bytes(2, 'little')
        self.head = bytes.fromhex(h['cwhead']) if head is None else bytes(head)
        if self.head[0] != self.syms['cw_irq'] - 1:
            raise ValueError('page-80 byte 0 is not the IM2 JR offset to cw_irq')
        if window_only:
            self.sites = {a: v for a, v in self.sites.items() if a == 0x8F92}
            self.site_bytes = {a + j for a, (old, new) in self.sites.items() for j in range(len(old))}
            self.stops = {}
        self.stops = dict(self.stops)
        self.stops[0x8F92] = 0x9907
        self.work = bool(work)
        if self.work:
            if window_only:
                raise ValueError('the 8F95 work needs the capture hooks')
            self.sites[0x8F95] = bytes.fromhex('3A49AC'), b'\xC3' + self.syms['wk_hook'].to_bytes(2, 'little')
            self.stops[0x8F95] = 0x8F98
            self.site_bytes = {a + j for a, (old, new) in self.sites.items() for j in range(len(old))}
            self.renderer = cw_work_renderer(work_code)


def cw_work_renderer(work_code=None):
    """Page 69 of a work build: FramePatch's renderer image (textmap, queue, prepare, display and the
    palette tables) plus the coroutine (cwwork at wk_enter)."""
    h = load_profile()['hooks']
    page = bytearray(8192)
    for block, symbol in (('textmap', 'render_textmap'), ('queue', 'queue_frame'), ('prepare', 'prepare_frame'), ('display', 'setup_display')):
        org = int(h['syms'][symbol], 16)
        code = bytes.fromhex(h[block])
        page[org:org + len(code)] = code
    for phase in range(2):
        page[0x400 + phase * 256:0x500 + phase * 256] = bytes((a & 127) * 2 for a in range(256))
    code = bytes.fromhex(h['cwwork']) if work_code is None else bytes(work_code)
    org = int(h['syms']['wk_enter'], 16)
    if any(page[org:org + len(code)]):
        raise ValueError('work code overlaps the renderer page')
    page[org:org + len(code)] = code
    code = bytes.fromhex(h['cwdx'])
    org = int(h['syms']['wk_dispatch'], 16)
    if any(page[org:org + len(code)]):
        raise ValueError('dispatch code overlaps the renderer page')
    page[org:org + len(code)] = code
    stub = bytes.fromhex(h['drvworker'])
    page[0x1D00:0x1D00 + len(stub)] = stub             # the 8EF9 driver calls setup_display through it
    page[0x1FF0:0x1FF2] = b'\x00\x1D'
    return page


CW_WKEN, CW_WKN = 0x1848, 0x1853        # page 80: work build flag (2), slices run
WK_STATE = 0x1EC0                       # page 69: 0 idle, 1 suspended, 2 done
DX_READY, DX_N = 0x1EE0, 0x1EEF         # page 69: dispatch result (item 2), records matched
WK_SP = 0x1EC5                          # page 69: the suspended work's SP
# page-69 bytes that are the 8F95 work's results (prepare_frame/render_textmap state; not its stack/SP saves)
WK_RESULT = [(0x0800, 0x0C00), (0x1000, 0x1800), (0x1E80, 0x1E86), (0x1E88, 0x1E89), (0x1E8B, 0x1E8D),
             (0x1EA1, 0x1EA2), (0x1EAC, 0x1EAD)]


class CopierWindowMemory(CaptureMemory):
    """Page 80 window state, a CTC channel 3 down counter on the model's wall clock, port FE log."""
    def __init__(self, ram, state, patch, clk=1, x=0, ctc=True, phase=0, count0=0, irqs=()):
        super().__init__(ram, state, patch, clk, ctc, phase, count0, irqs)
        self.pages[CW_PAGE][CW_X:CW_X + 2] = (x & 0xFFFF).to_bytes(2, 'little')
        self.outs, self.game_outs, self.log_outs = [], [], True

    def write_port(self, regs, port, value, *args):
        if port & 0xFF == 0xFE:
            (self.outs if self.log_outs else self.game_outs).append((self.wall, value))
        else:
            super().write_port(regs, port, value)


class CopierWorkMemory(CopierWindowMemory):
    """+ the 8F95 work (milestone 3b): page 69 (code, state, stacks), page 14 (textmap output),
    slot 1 = page 68 and slot 2 = page 14 as the work maps them, and the display registers that
    prepare_frame reads (static here: no display layer). The work may not write game RAM."""
    def __init__(self, ram, state, patch, *args, pages=None, display=None):
        super().__init__(ram, state, patch, *args)
        self.pages[CW_PAGE][CW_WKEN] = 2
        self.pages[69] = bytearray(pages[69]) if pages else bytearray(patch.renderer)
        self.pages[14] = bytearray(pages[14]) if pages else bytearray([0xE3] * 8192)
        self.pages.setdefault(79, bytearray(8192))
        self.pages.setdefault(82, select_page())
        self.pages.setdefault('sprite', bytearray(16384))
        self.pages.setdefault('attr', bytearray(640))
        self.spr = [0, 0]
        self.mmu1, self.mmu2 = 255, 10
        self.nr = dict(display or {0x6B: 0x0B, 0x6E: 0x80, 0x7F: 0})

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        if self.speed == 3:
            self.fast_reads += 1
        if a < 8192 and self.mmu0 != 255:
            return self.pages[self.mmu0][a]
        if 8192 <= a < 16384 and self.mmu1 != 255:
            return self.pages[self.mmu1][a - 8192]
        if 0x4000 <= a < 0x6000 and self.mmu2 in (14, 82):
            return self.pages[self.mmu2][a - 0x4000]
        return self.rom[a] if a < 16384 else self.ram[a]

    def __setitem__(self, a, v):
        if 8192 <= a < 16384 and self.mmu1 != 255:
            if self.mmu1 in (79, 83) or 85 <= self.mmu1 < 96 or self.mmu1 >= 136:
                raise AssertionError('dispatch wrote the owned store')
            self.pages[self.mmu1][a - 8192] = v
        elif 0x4000 <= a < 0x6000 and self.mmu2 == 14:
            self.pages[14][a - 0x4000] = v
        elif 0x4000 <= a < 0x6000 and self.mmu2 == 82:
            if a < 0x5000:
                raise AssertionError('selection wrote its code')
            self.pages[82][a - 0x4000] = v
        elif self.mmu0 == 69 and a >= 0x4000:
            raise AssertionError('8F95 work wrote game RAM %04X' % a)
        else:
            super().__setitem__(a, v)

    def nextreg(self, reg, value):
        if reg in SPRITE_NEXTREGS:
            self.nr_sprite = getattr(self, 'nr_sprite', {})
            self.nr_sprite[reg] = value
        elif reg == 0x50 and value == 69:
            self.mmu0 = value
            self.maps.append(value)
        elif reg == 0x51 and (value in (68, 79, 83, 255) or 85 <= value < 96 or 136 <= value < 216):
            self.mmu1 = value
        elif reg == 0x52 and value in (14, 10, 82):
            self.mmu2 = value
        else:
            if reg == 0x07 and value == 0 and (self.mmu1 != 255 or self.mmu2 != 10):
                raise AssertionError('speed restored before the original mapping')
            super().nextreg(reg, value)

    def write_port(self, regs, port, value, *args):
        if sprite_port(self.pages, self.spr, port, value):
            return
        if port == 0x243B and value in self.nr:
            self.nr_sel = value
        else:
            super().write_port(regs, port, value)

    def read_port(self, regs, port):
        if port == 0x253B and self.nr_sel in self.nr:
            return self.nr[self.nr_sel]
        return super().read_port(regs, port)


def _cost(r, before, speed, reads, mem):
    """Equivalent 3.5MHz T of one step; 28MHz reads carry one wait; transitions charged at 3.5MHz
    (mem.fast_switch: at 28MHz instead - the other bound, for the self-calibration check)."""
    fast = speed == 3 and mem.speed == 3 or (speed != mem.speed and getattr(mem, 'fast_switch', False))
    return (r[25] - before + (mem.fast_reads - reads if speed == 3 else 0)) / (8 if fast else 1)


def run_cw_window(patch, memory, registers, x=0, clk=1, ctc=True, phase=0, count0=0, irqs=(), limit=600000,
                  fast_switch=False, kt=0, frame=False, frame_irq=None, store=None):
    """8F92 -> 9907 differentially, on one wall clock (3.5MHz T from the 8F92 state).

    Original: CALL 9790 path with frame IRQs (if any) at the given wall times. Patched: cap_done +
    window, entered x late (the time earlier hooks would have added; written to CW_X), CTC model with
    the given phase. Checked: every register incl. R; all RAM except, with IRQs, the 4 bytes below the
    final SP, which 9907's PUSH DE / PUSH HL overwrite (run in both, then all RAM must match); the
    OUT (254) stream = the original's value changes in order, each at its original T within CW_TOL,
    or late (head not yet there); 9907 at its original time within CW_TOL. Without IRQs also the
    milestone-1 log against cw_out_t and the head T model.
    Work patch (milestone 3b): the 8F95 work runs in slices inside the window's waits (DI, page 69;
    reported: slices, work T, spans). frame: then 8F95 -> 8F98 (run_cw_frame) from the original's
    8F95 state; its page 14/69/68 results must equal run_frame's (the 8F95 work run at 8F95)."""
    from skoolkit.simulator import Simulator
    from .dizzy6 import _rw_simulator
    from . import z80n, simpool
    source = list(memory)
    site = registers[24]
    if site not in (0x8F92, 0x8F7C):
        raise AssertionError('state is not at 8F92 or 8F7C')
    if site == 0x8F7C and (x or 0x8F7C not in patch.sites):
        raise AssertionError('an 8F7C state needs the capture hooks (they measure X)')
    if source[0x998E]:
        raise AssertionError('998E set at %04X' % site)
    start = registers[25]
    foot = set()
    game_pc = lambda pc: pc >= 0x4000 and not (0x998B <= pc < 0x99BC or pc >= 0xFFF4)   # not the ISR
    work = getattr(patch, 'work', False)
    mem = (CopierWorkMemory if work else CopierWindowMemory)(patch.apply_memory(source), bytearray(8192), patch,
                                                             clk, x, ctc, phase, count0, irqs)
    if work and store:
        mem.pages.update({p: bytearray(v) for p, v in store.items()})
    mem.log_outs = site == 0x8F92
    mem.fast_switch = fast_switch
    mem.pages[CW_PAGE][CW_KT] = kt & 0xFF
    sim = simpool.machine(_rw_simulator(), mem, registers, 'inferno.cw.patched')
    sim.set_tracer(mem)
    r = sim.registers
    z80n.install(sim, mem.nextreg)
    syms = patch.syms
    waits = [(syms['cw_wait'], syms['cw_wait_end'])]
    elapsed, steps, wait_t = float(x), 0, 0.0
    pending, p_taken, p_lost, prev = sorted(irqs), [], [], registers[24]
    di_spans, di_start, entered_9790, reached_8f92, x_window, p8f92 = [], None, False, site == 0x8F92, None, None
    # Where each IRQ meets the game: a game-code IRQ before 8F92, or one a hook lost and compensated
    # (cap_lost), acts at a game instruction - the hooks shift the game by X, so the original takes it
    # at that same instruction (as an RZX does), not at the same wall time; level code reads R. IRQs
    # in the window (and pulses nothing compensated) keep their wall time.
    anchors, gcount, unanchored = {}, 0, []
    lost_at = syms_lost = patch.syms.get('cap_lost')
    work_t, work_spans, w_start, state68 = 0.0, [], None, None
    while r[24] != 0x9907:
        if steps >= limit:
            raise AssertionError('copier window did not reach 9907')
        pc = r[24]
        if pc in patch.site_bytes and pc not in patch.sites:
            raise AssertionError('jumped into a patched instruction interior')
        if r[26]:
            if di_start is not None:
                di_spans.append((di_start - x, elapsed - di_start))
                di_start = None
            if not ((mem.mmu0 == 255 and mem.speed == 0) or (mem.mmu0 == CW_PAGE and mem.speed == 3)
                    or (mem.mmu0 == 255 and mem[prev] == 0xFB)) or getattr(mem, 'mmu1', 255) != 255 \
                    or getattr(mem, 'mmu2', 10) != 10:   # EI: no IRQ before the next instruction
                raise AssertionError('interrupt-enabled scratch mapping or fast game code')
        elif di_start is None:
            di_start = elapsed
        while pending and elapsed >= pending[0] + CW_INT_PULSE:
            p_lost.append(pending.pop(0))
            unanchored.append(p_lost[-1])
        if pending and elapsed >= pending[0] and r[26]:
            if mem[0x998E]:
                raise AssertionError('998E set at an IRQ inside the window')
            before, speed, reads, sp, game_isr = r[25], mem.speed, mem.fast_reads, r[12], mem.mmu0 == 255
            mem.wall = elapsed
            if sim.accept_interrupt(r, mem, prev):
                p_taken.append(pending.pop(0))
                if game_isr and not reached_8f92:
                    foot.update((sp - j) & 0xFFFF for j in range(1, 5))
                    anchors[p_taken[-1]] = gcount
                elapsed += _cost(r, before, speed, reads, mem)
                prev = r[24]
                continue
        if pc == 0x9790:
            entered_9790 = True
        if pc == lost_at and mem.mmu0 != CW_PAGE and not reached_8f92:
            # compensated as an ISR before the next game instruction; the pulse may still be active
            # (cap_lost waits for /INT to drop), so it can still be in `pending`
            seen = [w for w in unanchored + pending if w <= elapsed and w not in anchors]
            if seen:
                anchors[min(seen)] = gcount
                if min(seen) in unanchored:
                    unanchored.remove(min(seen))
        if game_pc(pc) and not reached_8f92:
            gcount += 1
        if pc == 0x8F92 and not reached_8f92:
            reached_8f92, p8f92, mem.log_outs = True, elapsed, True
            x_window = int.from_bytes(mem.pages[CW_PAGE][CW_X:CW_X + 2], 'little')
        if work and pc == syms['cw_go'] and state68 is None:
            state68 = bytes(mem.pages[STATE_PAGE])      # the capture as the 8F95 work will find it
        mem.wall = elapsed
        before, speed, reads, page = r[25], mem.speed, mem.fast_reads, mem.mmu0
        prev = pc
        sim.opcodes[mem[pc]]()
        cost = _cost(r, before, speed, reads, mem)
        elapsed += cost
        if page == CW_PAGE and any(a <= pc < b for a, b in waits):
            wait_t += cost
        if page == 69:
            work_t += cost
            if w_start is None:
                w_start = elapsed - cost
        elif w_start is not None:
            work_spans.append((w_start - x, elapsed - cost - w_start))
            w_start = None
        steps += 1
    if di_start is not None:
        di_spans.append((di_start - x, elapsed - di_start))
    original = simpool.machine(Simulator, source, registers, 'inferno.cw.original', copy=True)
    o, om = original.registers, original.memory
    pending = sorted(w for w in irqs if w not in anchors)
    at_game = sorted(anchors.values())
    o_taken, outs, t0, prev, ocount = [], [], None, registers[24], 0
    sp92, o8f92 = (registers[12] if site == 0x8F92 else None), None
    while o[24] != 0x9907:
        now = o[25] - start
        while pending and now >= pending[0] + CW_INT_PULSE:
            raise AssertionError('original held interrupts off at %d' % pending[0])
        due = (pending and now >= pending[0]) or (at_game and o8f92 is None and ocount >= at_game[0])
        if due and o[26]:
            sp = o[12]
            if original.accept_interrupt(o, om, prev):
                if at_game and o8f92 is None and ocount >= at_game[0]:
                    at_game.pop(0)
                else:
                    pending.pop(0)
                o_taken.append(now)
                if o8f92 is None:           # game-code IRQ before 8F92: PC and the ISR's AF below SP
                    foot.update((sp - j) & 0xFFFF for j in range(1, 5))
                prev = o[24]
                continue
        if o[24] == 0x8F92 and o8f92 is None:
            sp92, o8f92 = o[12], now
            if at_game:
                raise AssertionError('game-instruction IRQ anchor not reached before 8F92')
        if game_pc(o[24]) and o8f92 is None:
            ocount += 1
        if o[24] == 0x9790 and t0 is None:
            t0, map9790 = o[25], bytes(om[0x9B00:0x9F80])
        if o[24] == 0x97C5:
            outs.append((o[25] - start, o[0]))
        if om[0x998E]:
            raise AssertionError('998E set inside the original head')
        prev = o[24]
        original.opcodes[om[o[24]]]()
    head_t, o9907 = o[25] - t0, o[25] - start
    o_regs, o_ram = list(o), bytes(om[16384:])
    for _ in range(2):                      # 9907: PUSH DE / PUSH HL
        original.opcodes[om[o[24]]]()
    errors = []
    diffs = [i for i in CMP if r[i] != o_regs[i]]
    if diffs:
        errors.append('registers ' + str(diffs))
    if r[15] != o_regs[15]:
        errors.append('R %02X != %02X' % (r[15], o_regs[15]))
    expected = bytearray(o_ram)
    for a, (old, new) in patch.sites.items():
        expected[a - 16384:a - 16384 + len(new)] = new
    sp = o_regs[12]
    dead = {(sp - j) & 0xFFFF for j in range(1, 5)}   # window CALLs / IRQ pushes; 9907 overwrites them
    early = set()   # an IRQ before the copier's own SP: its pushes lie below the caller's SP, as in the original
    if irqs:
        early = {(sp92 - j) & 0xFFFF for j in range(1, 7)}
        # game-code IRQs between 8F7C and 8F92 come at other instructions in the two runs (the hooks
        # shift the game by X): their PC/AF pushes are garbage below the caller's SP in both
        early |= {a for a in foot if (sp92 - a) & 0xFFFF <= 0x400}
    bad = [i + 16384 for i, (u, v) in enumerate(zip(mem.ram[16384:], expected)) if u != v and i + 16384 not in dead | early]
    if bad:
        errors.append('RAM %s' % [hex(a) for a in bad[:6]])
    if dead:
        for _ in range(2):
            sim.opcodes[mem[r[24]]]()
        after = bytearray(original.memory[16384:])
        for a, (old, new) in patch.sites.items():
            after[a - 16384:a - 16384 + len(new)] = new
        left = [i + 16384 for i, (u, v) in enumerate(zip(mem.ram[16384:], after)) if u != v and i + 16384 not in early]
        if left:
            errors.append('bytes below SP not overwritten by 9907 PUSH DE / PUSH HL: %s' % [hex(a) for a in left[:4]])
    change_k = [i for i, (t, v) in enumerate(outs) if i == 0 or v != outs[i - 1][1]]
    changes = [outs[i] for i in change_k]
    fallback = entered_9790
    stream = outs if fallback else changes
    if [v for t, v in mem.outs] != [v for t, v in stream]:
        errors.append('OUT values differ (%d written, %d expected)' % (len(mem.outs), len(stream)))
        dts = []
    else:
        dts = [pt - ot for (pt, pv), (ot, ov) in zip(mem.outs, stream)]
    d9907 = elapsed - o9907
    # an IRQ handled inside the window delays an OUT due within one cell after it (handler + /INT wait)
    irq_near = {i for i, (t, v) in enumerate(stream) for w in o_taken if 0 <= t - w <= 400}
    # an OUT due within 64 T of an IRQ: the 32 T clock cannot order them, so it may move by one ISR
    irq_edge = {i for i, (t, v) in enumerate(stream) for w in o_taken if -64 <= t - w <= CW_ISR[0] + 64}
    irq_delayed = [i for i, d in enumerate(dts) if (i in irq_near and CW_TOL < d <= CW_TOL + 40)
                   or (i in irq_edge and CW_TOL < abs(d) <= CW_TOL + CW_ISR[0] + 8)]
    late = [i for i, d in enumerate(dts) if d > CW_TOL and i not in irq_delayed]
    if not fallback:
        if any(d < -CW_TOL for i, d in enumerate(dts) if i not in irq_delayed):
            errors.append('OUT early by %.0f T' % -min(dts))
        first_ok = min([i for i, d in enumerate(dts) if abs(d) <= CW_TOL], default=len(dts))
        if any(i > first_ok for i in late):
            errors.append('late OUT after an on-time OUT')
        if abs(d9907) > CW_TOL:
            errors.append('9907 off by %.0f T' % d9907)
        if not irqs:
            rows = list(mem.pages[CW_PAGE][0x1700:0x1700 + CW_ROWS])
            if len(outs) != CW_CELLS or CW_HEAD_T0 + CW_HEAD_PER_G * sum(rows) != head_t:
                errors.append('head T model')
            model, g = _cw_out_model(bytes(0x9B00) + map9790)
            if [t - (t0 - start) for t, v in outs] != model or g != sum(rows):
                errors.append('OUT T model')
    return {'values': [v for t, v in stream], 'change_k': change_k, 'irq_delayed': [round(dts[i]) for i in irq_delayed], 'errors': errors, 'fallback': fallback, 'dts': dts, 'late': len(late),
            'late_T': max([dts[i] for i in late], default=0), 'd9907': d9907, 'o9907': o9907,
            'changes': len(changes), 'G': None if irqs else sum(mem.pages[CW_PAGE][0x1700:0x1700 + CW_ROWS]),
            'wait_T': wait_t, 'busy_T': elapsed - x - wait_t, 'di_spans': di_spans,
            'irqs_taken': len(p_taken), 'irqs_lost': p_lost, 'original_irqs': len(o_taken),
            'clk': mem.pages[CW_PAGE][CW_CLK], 'ctc_writes': mem.ctc_writes, 'steps': steps,
            'x_window': x_window, 'x_true': None if p8f92 is None or o8f92 is None else p8f92 - o8f92,
            'p8f92': p8f92 if site == 0x8F7C else 0.0,
            'kt': mem.pages[CW_PAGE][CW_KT] - (256 if mem.pages[CW_PAGE][CW_KT] > 127 else 0),
            # lost pulses that began just after a hook's last $C8 read: between that read and the IRQ
            # sample after its EI + NEXTREG 7,0 (charged at 3.5MHz here) nothing can see them
            # = lost before 8F92, not compensated, and no $C8 read while/just after it (a read that did see
            # it and still did not compensate is a failure, not a gap)
            'irqs_gap': [w for w in p_lost if w not in anchors and (p8f92 is None or w < p8f92)
                         and not any(w <= c <= w + 60 for c in mem.c8_reads)],
            'irqs_anchored': len(anchors),
            'work_T': work_t, 'work_spans': work_spans, 'slices': len(work_spans),
            'work_done': bool(work) and mem.pages[69][WK_STATE] == 2,
            'dx': ((mem.pages[69][DX_READY], mem.pages[69][DX_N], bytes(mem.pages[STATE_PAGE]), list(mem.ram),
                    mem.pages[69][0x1EAC])
                   if work and store else None),
            'sel': bytes(mem.pages[82]) if work and store else None,
            'sprite': bytes(mem.pages['sprite']) if work and store else None,
            'attr': bytes(mem.pages['attr']) if work and store else None,
            'frame': (run_cw_frame(patch, original, mem.pages, state68, phase=phase, count0=count0, irq=frame_irq)
                      if work and frame else None)}


def run_cw_frame(patch, original, pages, state68, phase=0, count0=0, irq=None, release=300):
    """Milestone 3b: 8F95 -> 8F98 after a window run. original: the original machine just past 9907
    (state proven equal to the patched one there); it is run to 8F95 with one frame IRQ `release`
    instructions in (the one that ends the 9907 limiter). From that 8F95 state the work patch's
    hook (wk_hook) finishes the work with the window run's pages 68/69/14 and returns to 8F98:
    registers incl. R and all RAM equal to the original's 8F98 (irq: a pulse at that T after 8F95,
    inside the hook: lost and compensated; the original takes the no-op ISR at 8F98); pages 14,
    68 (bar the capture stack/SP) and 69's results (WK_RESULT) equal run_frame (FramePatch, the
    work at 8F95) from the same 8F95 state and the capture as the window found it."""
    from skoolkit.simulator import Simulator
    from .dizzy6 import _rw_simulator
    from . import z80n, simpool
    o, om = original.registers, original.memory
    prev, steps = o[24], 0
    while o[24] != 0x8F95:
        if steps == release and o[26]:
            if not original.accept_interrupt(o, om, prev):
                raise AssertionError('limiter IRQ not accepted')
        prev = o[24]
        original.opcodes[om[o[24]]]()
        steps += 1
        if steps > 400000:
            raise AssertionError('original did not reach 8F95')
    ram, regs = bytes(om[0:65536]), list(o)
    errors = []
    # the original 8F95 -> 8F98 (+ the no-op ISR at 8F98 when a pulse is tested)
    ref = simpool.machine(Simulator, bytearray(ram), regs, 'inferno.cwf.original', copy=True)
    q, qm = ref.registers, ref.memory
    while q[24] != 0x8F98:
        ref.opcodes[qm[q[24]]]()
    t_orig = q[25] - regs[25]
    if irq is not None:
        sp = q[12]
        if not ref.accept_interrupt(q, qm, 0x8F95):
            raise AssertionError('original IRQ at 8F98 not accepted')
        while not (q[24] == 0x8F98 and q[12] == sp):
            ref.opcodes[qm[q[24]]]()
    mem = CopierWorkMemory(patch.apply_memory(list(ram)), pages[STATE_PAGE], patch, 1, 0, True, phase, count0,
                           () if irq is None else (irq,), pages=pages)
    sim = simpool.machine(_rw_simulator(), mem, regs, 'inferno.cwf.patched')
    sim.set_tracer(mem)
    r = sim.registers
    z80n.install(sim, mem.nextreg)
    elapsed, n = 0.0, 0
    resumed = mem.pages[69][WK_STATE]
    while r[24] != 0x8F98:
        if n > 300000:
            raise AssertionError('8F95 hook did not return')
        if r[24] in patch.site_bytes and r[24] not in patch.sites:
            raise AssertionError('8F95 hook jumped into a patched instruction interior')
        if r[26] and r[24] != 0x8F95 and mem[(r[24] - 1) & 0xFFFF] != 0xFB:
            if mem.mmu0 != 255 or mem.speed != 0 or mem.mmu1 != 255 or mem.mmu2 != 10:
                raise AssertionError('interrupt-enabled scratch mapping in the 8F95 hook')
        before, speed, reads = r[25], mem.speed, mem.fast_reads
        mem.wall = elapsed
        sim.opcodes[mem[r[24]]]()
        elapsed += _cost(r, before, speed, reads, mem)
        n += 1
    diffs = [i for i in CMP if r[i] != q[i]]
    if diffs:
        errors.append('8F98 registers ' + str(diffs))
    if r[15] != q[15]:
        errors.append('8F98 R %02X != %02X' % (r[15], q[15]))
    expected = bytearray(qm[16384:])
    for a, (old, new) in patch.sites.items():
        expected[a - 16384:a - 16384 + len(new)] = new
    below = {(regs[12] - j) & 0xFFFF for j in range(1, 5)} if irq is not None else set()   # the ISR's pushes
    bad = [i + 16384 for i, (u, v) in enumerate(zip(mem.ram[16384:], expected)) if u != v and i + 16384 not in below]
    if bad:
        errors.append('8F98 RAM %s' % [hex(a) for a in bad[:6]])
    good = run_frame(FramePatch(), list(ram), regs, bytearray(state68))
    gp = good['pages']
    if resumed != 2:            # 3c: not finished in the window: dropped; 8F95 writes nothing but readiness 0
        if mem.pages[69][0x1EAC] or mem.pages[69][0x1EA1]:
            errors.append('dropped frame left readiness set')
        if bytes(mem.pages[14]) != bytes(pages[14]) or bytes(mem.pages[STATE_PAGE]) != bytes(pages[STATE_PAGE]):
            errors.append('8F95 wrote page 14/68 for a dropped frame')
        if any(mem.pages[69][a] != pages[69][a] for a in range(0x0800, 0x1800)):
            errors.append('8F95 wrote page 69 work data for a dropped frame')
        return {'errors': errors, 'ready': False, 'state_at_8f95': resumed, 'hook_T': elapsed,
                'added_T': elapsed - t_orig, 'reference_T': good['equivalent_T']}
    if bytes(mem.pages[14]) != gp[14]:
        errors.append('page 14 differs from the 8F95 work')
    if any(bytes(mem.pages[69][a:b]) != gp[69][a:b] for a, b in WK_RESULT):
        errors.append('page 69 results differ from the 8F95 work')
    keep = lambda p: bytes(p[:CAP_SP_OFF]) + bytes(p[CAP_SP_OFF + 2:0x1F80])
    if keep(mem.pages[STATE_PAGE]) != keep(gp[STATE_PAGE]):
        errors.append('page 68 differs from the 8F95 work')
    return {'errors': errors, 'ready': bool(gp[69][0x1EAC]), 'state_at_8f95': resumed,
            'hook_T': elapsed, 'added_T': elapsed - t_orig, 'reference_T': good['equivalent_T']}


CAP_SP_OFF = 0x03F0                     # page 68: CAP_SP (the legacy frame hook saves the game SP there)


def _cw_out_model(memory):
    """Original T (from 9790 entry) of all 416 head OUTs, from the tile map alone; and G."""
    g, ts = 0, []
    for k in range(CW_CELLS):
        ts.append(cw_out_t(k, g))
        g += memory[0x9F7E - 2 * k] >= 16
    return ts, g


def _cw_states(reference, levels, stop, every, sites=(0x8F92,)):
    """Entry states (RAM, registers, last port FE value) at 8F92 (and/or 8F7C: the update model)
    from the original recordings. One site: {level: states}; several: {site: {level: states}}."""
    from .simrun import run

    class Grab:
        def __init__(self):
            self.sim, self.n, self.port = None, {s: 0 for s in sites}, None
            self.states = {s: [] for s in sites}

        def on_sim(self, sim):
            self.sim = sim

        def before(self, pc):
            m = self.sim.memory
            if m[pc] == 0xD3 and m[(pc + 1) & 0xFFFF] == 0xFE:
                self.port = self.sim.registers[0]
            if pc in self.n:
                self.n[pc] += 1
                if self.n[pc] % every == 0:
                    self.states[pc].append((bytes(m[a] for a in range(65536)), list(self.sim.registers), self.port))
    out = {s: {} for s in sites}
    for level in levels:
        g = Grab()
        run(str(reference / ('Inferno%s.z80' % level)), [str(reference / ('Inferno%s.rzx' % level))], g, stop=stop)
        for s in sites:
            out[s][level] = g.states[s]
    return out[sites[0]] if len(sites) == 1 else out


def _cw_variant(patch_head, old, new, offset=0):
    """Head bytes with one unique pattern changed (negative controls)."""
    at = patch_head.find(old)
    if at < 0 or patch_head.find(old, at + 1) >= 0:
        raise AssertionError('control pattern not unique: ' + old.hex())
    code = bytearray(patch_head)
    code[at + offset:at + offset + len(new)] = new
    return code


def copier_window_controls(head, syms):
    """Broken windows that the checks must reject (each uses its own changed bytes)."""
    c = {}
    c['change detection removed (JP Z -> JP)'] = (_cw_variant(head, bytes.fromhex('FDBE00CA'), b'\xC3', 3), False)
    c['tile count INC C removed'] = (_cw_variant(head, bytes.fromhex('D50C'), b'\x00', 1), False)
    rk = head.find(bytes.fromhex('3A02186FC6'))   # LD A,(CW_R) / LD L,A / ADD A,CW_M1K
    if rk < 0 or head.find(bytes.fromhex('3A02186FC6'), rk + 1) >= 0:
        raise AssertionError('CW_M1K pattern')
    code = bytearray(head)
    code[rk + 5] = (code[rk + 5] + 1) & 0xFF
    c['R constant off by one'] = (code, False)
    a, b = syms['cw_irq'], syms['cw_wait']   # cw_irq only (cw_wkback counts the same way)
    c['IRQ T not added'] = (head[:a] + _cw_variant(head[a:b], bytes.fromhex('ED34') + CW_ISR[0].to_bytes(2, 'little'),
                                                   bytes.fromhex('ED340000')) + head[b:], True)
    c['IRQ M1 not added'] = (head[:a] + _cw_variant(head[a:b], bytes((0xC6, CW_ISR[1])), b'\xC6\x00') + head[b:], True)
    c['pad 3 ticks late'] = (_cw_pad_variant(head, syms, 96), False)
    c['OUT deadlines 3 ticks early'] = (_cw_krb_variant(head, -96), False)
    return c


def _cw_pad_variant(head, syms, delta):
    pat = bytes.fromhex('3A191821')         # LD A,(CW_RBF) / LD HL,6104+1024+16-CW_KPAD
    at = head.find(pat)
    if at < 0 or head.find(pat, at + 1) >= 0:
        raise AssertionError('CW_KPAD pattern')
    code = bytearray(head)
    v = (int.from_bytes(code[at + 4:at + 6], 'little') + delta) & 0xFFFF
    code[at + 4:at + 6] = v.to_bytes(2, 'little')
    return code


def _cw_krb_variant(head, delta):
    at = head.find(bytes.fromhex('23ED34'))  # INC HL / ADD HL,CW_KRB
    if at < 0 or head.find(bytes.fromhex('23ED34'), at + 1) >= 0:
        raise AssertionError('CW_KRB pattern not unique')
    code = bytearray(head)
    v = (int.from_bytes(code[at + 3:at + 5], 'little') + delta) & 0xFFFF
    code[at + 3:at + 5] = v.to_bytes(2, 'little')
    return code


def _cw_rom_variant(patch, lo, hi, old, new, count=1):
    """The patch with a byte pattern in its ROM range [lo, hi) changed (negative controls)."""
    rom = bytes(patch.rom[lo:hi])
    at = [i for i in range(len(rom)) if rom.startswith(old, i)]
    if len(at) != count:
        raise AssertionError('control pattern %s found %d times' % (old.hex(), len(at)))
    for i in at:
        patch.rom[lo + i:lo + i + len(new)] = new
    return patch


def copier_window_update_controls():
    """Broken hooks / window entries the update model must reject: name -> (patch, IRQ kind). IRQ
    kind: None; 'hook' (a pulse inside the 8F7C hook: lost); 'entry' (inside the window's entry DI
    span: lost); 'before' (a pulse taken by game code before an actor hook); 'slice' (inside the first
    work slice: lost); 'frame' (inside the 8F95 hook: lost). Milestone 3b: the work patch throughout."""
    def p(head=None, rom_code=None, work_code=None):
        return CopierWindowPatch(head, rom_code=rom_code, work=True, work_code=work_code)
    s = p().syms
    hooks = load_profile()['hooks']
    cap, lo = bytes.fromhex(hooks['capture']), bytes.fromhex(hooks['caplo'])
    a0, l0 = s['cap_scene'], s['cap_chk']   # caplo starts at cap_chk
    at = cap.find(b'\x1E\x00\xCD')          # LD HL,K / LD A,KR / LD E,0 / CALL cap_out (scene)
    pat = cap[at - 5:at]
    if at < 5 or pat[0] != 0x21 or pat[3] != 0x3E or cap.find(b'\x1E\x00\xCD', at + 1) >= 0:
        raise AssertionError('scene exit constants not found')
    kx = (int.from_bytes(pat[1:3], 'little') + 96) & 0xFFFF
    c = {}
    c['hook X constant 3 ticks high'] = (_cw_rom_variant(p(), a0, a0 + len(cap), pat, b'\x21' + kx.to_bytes(2, 'little')), None)
    c['hook R constant off by one'] = (_cw_rom_variant(p(), a0, a0 + len(cap), pat, pat[:4] + bytes(((pat[4] + 1) & 0xFF,))), None)
    klr = lo.find(b'\xAA\xE6\x7F\xAA') - 2   # ADD A,CAP_KLR / XOR D / AND 7F / XOR D (R + 10 in cap_lost)
    ka = lo.find(b'\xED\x35')                  # ADD DE,CAP_KLOST
    if klr < 0 or lo[klr] != 0xC6 or ka < 0:
        raise AssertionError('cap_lost constants not found')
    c['lost IRQ: R not added'] = (_cw_rom_variant(p(), l0, l0 + len(lo), lo[klr:klr + 2], bytes((0xC6, (lo[klr + 1] - 10) & 0xFF))), 'hook')
    kl = int.from_bytes(lo[ka + 2:ka + 4], 'little')
    c['lost IRQ: X not adjusted'] = (_cw_rom_variant(p(), l0, l0 + len(lo), lo[ka:ka + 4], b'\xED\x35' + ((kl + 94) & 0xFFFF).to_bytes(2, 'little')), 'hook')
    c['hook $C8 clear removed'] = (_cw_rom_variant(p(), 0x3900, 0x3C00, b'\xED\x91\xC8\x01', bytes(4), 4), 'before')
    c['window entry lost IRQ not counted'] = (p(_cw_variant(p().head, bytes.fromhex('ED780F30'), b'\x18', 3)), 'entry')
    # 3b: the work in the window's waits and its 8F95 finish
    work = bytes.fromhex(load_profile()['hooks']['cwwork'])
    poll = bytes.fromhex('3E1BDB3BFD953DFA')            # LD A,1B / IN A,(3B) / SUB IYl / DEC A / JP M
    if work.count(poll) != 2:
        raise AssertionError('work poll pattern')
    c['work ignores the slice end (polls never yield)'] = (p(work_code=work.replace(poll, poll[:6] + b'\xAF\xFA')), None)
    c['slice lost pulse not counted'] = (p(_cw_variant(p().head, bytes.fromhex('7C0F30'), b'\x18', 2)), 'slice')
    wsp = b'\xED\x73' + WK_SP.to_bytes(2, 'little')          # LD (WK_SP),SP in wk_yield
    if work.count(wsp) != 1:
        raise AssertionError('WK_SP save pattern')
    c['yield loses SP'] = (p(work_code=work.replace(wsp, bytes(4))), None)
    lost = bytes.fromhex('C60AA8E67FA8')               # wk_lost: ADD A,10 / XOR B / AND 7F / XOR B
    if work.count(lost) != 1:
        raise AssertionError('wk_lost pattern')
    c['8F95 lost pulse not counted'] = (p(work_code=work.replace(lost, b'\xC6\x00' + lost[2:])), 'frame')
    return c


def copier_window_update_checks(states, every_irq=50, controls=True, sample=1, only=None, stores=None):
    """Milestone 3 update model: 8F7C -> 9907 with the capture hooks (X measured on the CTC, R
    restored) and the window, on one wall clock. Per state: registers incl. R, RAM, OUT changes and
    9907 on time; X measured against the true added time. Every every_irq-th state: frame IRQs before,
    inside and after the hooks and in the window's entry DI span (lost pulses compensated), and the
    negative controls."""
    patch = CopierWindowPatch(work=True)
    ctl = copier_window_update_controls() if controls else {}
    stores = stores or {}
    counts, failures, detected = Counter(), [], Counter()
    xerr, d9907s, xs, busy, wait, gaps = [], [], [], [], [], []
    work_ms, f_added, f_full = [], [], []
    sel_pages, sel_index, sprite_pages, attr_pages = {}, {}, {}, {}
    run, prev_i = 0, None       # consecutive dropped frames (consecutive updates only when sample == 1)
    first = next(c for c in states.values() if c)[0]   # any state: cw_cal's result does not depend on it
    # the other bound for the speed switches: charged at 28MHz; the first window measures them (cw_cal)
    kt_fast = run_cw_window(patch, first[0], first[1], clk=0, fast_switch=True)['kt']
    if kt_fast > -30:
        raise AssertionError('cw_cal did not measure the fast speed switches (%d)' % kt_fast)
    head = bytearray(patch.head)
    at = head.find(bytes.fromhex('3A4718' '5F879F5719'))   # cw_tout: LD A,(CW_KT) .. ADD HL,DE
    if at < 0 or head.find(bytes.fromhex('3A4718' '5F879F5719'), at + 1) >= 0:
        raise AssertionError('cw_tout KT pattern')
    head[at + 7] = 0
    ctl_kt = CopierWindowPatch(bytes(head), work=True)

    def fail(level, i, what, res):
        if len(failures) < 80:
            failures.append({'level': level, 'state': i, 'case': what,
                             'errors': res['errors'][:3] if isinstance(res, dict) else [str(res)]})
        counts['failures'] += 1

    for level, cases in states.items():
        for i, (ram, regs, port) in enumerate(cases):
            if not _cw_pick(level, i, sample, only):
                continue
            n = _cw_n(level, i)
            counts['states'] += 1
            phase, count0 = (n * 13) % CW_TICK, (n * 37) & 255
            store = stores.get(level)
            if store and level in sel_pages:
                store = {**store, 82: sel_pages[level], 'sprite': sprite_pages[level], 'attr': attr_pages[level]}   # store state and pattern RAM carry across consecutive updates
            try:
                res = run_cw_window(patch, ram, regs, phase=phase, count0=count0, frame=True, store=store)
            except AssertionError as e:
                fail(level, i, 'no IRQ', e)
                continue
            if res.get('dx') is not None and res['work_done']:
                got, matched, page68, live, scene = res['dx']
                try:
                    want, reasons = dispatch_expected(stores[level], live, page68)
                    want = want if scene else 0
                except ValueError as e:
                    fail(level, i, 'dispatch oracle', e)
                    continue
                counts['dispatch ready' if want else 'dispatch not ready'] += 1
                counts.update({'dispatch miss: ' + k: 1 for k in reasons})
                counts['dispatch records matched'] += matched
                if got != want:
                    fail(level, i, 'dispatch', {'errors': ['DX_READY %d, oracle %d: %s' % (got, want, reasons)]})
                if res['sel'] is not None:
                    before = sel_pages.get(level, store[82])
                    state, log = SelectState(before), capture_log(page68) if not page68[0x3F5] else []
                    if want:
                        index = sel_index.setdefault(level, index_tables({83: stores[level][83]}))
                        ready, out = select_expected(state, index, log)
                    else:
                        ready, out = 0, []
                    page = res['sel']
                    if page[SEL_READY] != ready or (ready and select_list(page) != out) or (want and SelectState(page).tuple() != state.tuple()):
                        fail(level, i, 'selection', {'errors': ['SEL_READY %d, oracle %d, lists %s' % (page[SEL_READY], ready, select_list(page) == out)]})
                    counts['selection ready' if ready else 'selection not ready'] += 1
                    if want and not ready:
                        counts['selection not ready after dispatch ready'] += 1
                    if ready:
                        good, slot = patterns_uploaded(page, res['sprite'], stores[level], out)
                        if not good:
                            fail(level, i, 'upload', {'errors': ['slot %d pattern differs' % slot]})
                        counts['frames with all patterns verified'] += 1
                        if res['attr'][:5 * len(out)] != attributes_expected(out):
                            fail(level, i, 'attributes', {'errors': ['attribute bytes differ']})
                        counts['frames with attributes verified'] += 1
                        counts['patterns uploaded'] += sum(before[SEL_FLAG + s] != 0 and page[SEL_FLAG + s] == 0 for s in range(64))
                    counts['selection chunks'] += len(out)
                    counts['selection new patterns'] += page[SEL_NEW]
                    counts['selection evictions'] += page[SEL_EVICT]
                    counts['max frame chunks'] = max(counts['max frame chunks'], len(out))
            if res.get('sel') is not None:
                sprite_pages[level] = res['sprite']
                attr_pages[level] = res['attr']
                sel_pages[level] = res['sel']                    # a dropped attempt's partial state is the real next state
            if res['errors'] or res['fallback']:
                fail(level, i, 'no IRQ', res)
            fr = res['frame']
            if fr['errors']:
                fail(level, i, '8F95 finish', fr)
            counts['work slices'] += res['slices']
            counts['work done in the window'] += res['work_done']
            counts['dropped: work started, not finished'] += fr['state_at_8f95'] == 1
            counts['dropped: no slice'] += fr['state_at_8f95'] == 0
            counts['frames ready'] += fr['ready']
            drop = fr['state_at_8f95'] != 2
            run = run + 1 if drop and prev_i == (level, i - sample) else int(drop)
            prev_i = (level, i)
            counts['max consecutive dropped frames'] = max(counts['max consecutive dropped frames'], run)
            work_ms.append(res['work_T'])
            f_added.append(fr['added_T'])
            f_full.append(fr['reference_T'])
            xw = res['x_window'] - (65536 if res['x_window'] >= 32768 else 0)
            xerr.append(xw - res['x_true'])
            xs.append(res['x_true'])
            d9907s.append(res['d9907'])
            busy.append(res['busy_T'] - res['p8f92'])   # the window's own busy time
            wait.append(res['wait_T'])
            counts['OUT changes'] += res['changes']
            counts['late OUTs (burst prefix after X)'] += res['late']
            if n % every_irq:
                continue
            spans = [(s, l) for s, l in res['di_spans'] if s < res['p8f92'] - 1]
            entry = [(s, l) for s, l in res['di_spans'] if s >= res['p8f92'] - 1][:1]
            points = []
            for s, l in spans[:3] + spans[-1:]:
                points += [s - 28, s - 8, s + 4, s + l / 2, s + l - 24, s + l - 8, s + l + 4]
            for s, l in entry:
                points += [s + 2, s + l / 2, s + l - 4]
            for s, l in res['work_spans'][:2] + res['work_spans'][-1:]:   # inside work slices (DI, page 69)
                points += [s + 4, s + l / 2, s + l - 8]
            points += [j * res['o9907'] / 9 for j in range(1, 9)]
            for t in sorted(set(round(v, 1) for v in points if 0 < v < res['o9907'] - 300)):
                try:
                    ri = run_cw_window(patch, ram, regs, phase=phase, count0=count0, irqs=(t,))
                except AssertionError as e:
                    fail(level, i, 'IRQ at %.0f' % t, e)
                    continue
                counts['IRQ injections'] += 1
                if ri['irqs_gap']:     # unseen by design in this model: the game may diverge (it reads R)
                    counts['IRQ in a post-check gap (model; lost uncompensated)'] += 1
                    gaps.append(ri['d9907'])
                    continue
                counts['IRQ in a DI span (lost, compensated)'] += bool(ri['irqs_lost'])
                counts['IRQ at a game instruction (original anchored there)'] += ri['irqs_anchored']
                d9907s.append(ri['d9907'])
                if ri['errors'] or ri['original_irqs'] != 1:
                    fail(level, i, 'IRQ at %.0f' % t, ri)
            if fr['hook_T'] > 120:      # a pulse inside the 8F95 hook (DI): lost, compensated (R + 10)
                t = max(40.0, fr['hook_T'] / 2 - 40)
                try:
                    rj = run_cw_window(patch, ram, regs, phase=phase, count0=count0, frame=True, frame_irq=t)['frame']
                except AssertionError as e:
                    rj = {'errors': [str(e)]}
                counts['IRQ in the 8F95 hook (lost, compensated)'] += 1
                if rj['errors']:
                    fail(level, i, '8F95 IRQ at %.0f' % t, rj)
            rf = run_cw_window(patch, ram, regs, phase=phase, count0=count0, fast_switch=True, kt=kt_fast)
            counts['fast speed-switch runs (cw_cal correction)'] += 1
            d9907s.append(rf['d9907'])
            if rf['errors']:
                fail(level, i, 'fast speed switches', rf)
            bad = run_cw_window(ctl_kt, ram, regs, phase=phase, count0=count0, fast_switch=True, kt=kt_fast)['errors']
            detected['speed-switch correction not applied in hooks' + (' detected' if bad else ' MISSED')] += 1
            for name, (bp, kind) in ctl.items():
                irq = ()
                if kind == 'hook' and spans:
                    irq = (spans[0][0] + spans[0][1] / 2,)
                elif kind == 'entry' and entry:
                    irq = (entry[0][0] + entry[0][1] / 2,)
                elif kind == 'before' and len(spans) > 1:
                    irq = ((spans[0][0] + spans[0][1] + spans[1][0]) / 2,)
                elif kind == 'slice' and res['work_spans']:
                    irq = (res['work_spans'][0][0] + res['work_spans'][0][1] / 2,)
                if kind and kind != 'frame' and not irq:
                    continue
                if (kind == 'frame' and fr['hook_T'] <= 120) or (name.startswith(('work', 'yield')) and res['slices'] < 2):
                    continue            # nothing for the control to break in this state
                try:
                    rc = run_cw_window(bp, ram, regs, phase=phase, count0=count0, irqs=irq, frame=True,
                                       frame_irq=max(40.0, fr['hook_T'] / 2 - 40) if kind == 'frame' else None)
                    bad = rc['errors'] + rc['frame']['errors']
                except AssertionError as e:
                    bad = [str(e)]
                detected[name + (' detected' if bad else ' MISSED')] += 1
    q = lambda v, f: round(sorted(v)[min(len(v) - 1, int(f * len(v)))], 1) if v else None
    return {'counts': dict(counts), 'failures': failures,
            'x_error_T': {'min': q(xerr, 0), 'p1': q(xerr, .01), 'median': q(xerr, .5), 'p99': q(xerr, .99), 'max': q(xerr, 1)},
            'x_T': {'min': q(xs, 0), 'median': q(xs, .5), 'max': q(xs, 1)},
            'd9907_T': {'min': q(d9907s, 0), 'max': q(d9907s, 1)},
            'kt_fast_switches_T': kt_fast,
            'post_check_gap_d9907_T': {'min': q(gaps, 0), 'max': q(gaps, 1)},
            'window_busy_ms_max': round(max(busy, default=0) / 3500, 3),
            'window_wait_ms_min': round(min(wait, default=0) / 3500, 3),
            'work_in_window_T': {'min': q(work_ms, 0), 'median': q(work_ms, .5), 'max': q(work_ms, 1)},
            'frame_8f95_added_T': {'min': q(f_added, 0), 'median': q(f_added, .5), 'p90': q(f_added, .9), 'max': q(f_added, 1)},
            'frame_work_at_8f95_before_T': {'min': q(f_full, 0), 'median': q(f_full, .5), 'max': q(f_full, 1)},
            'negative_controls': dict(detected),
            'scope': 'update model 8F7C -> 9907 -> 8F98 in the simulator: capture hooks + copier window + the 8F95 '
                     'work in its waits (milestone 3b), finished at 8F95; CTC, frame IRQ and NextReg $C8/$22 models '
                     '(a $C8 clear during a pulse does not take); uncontended T with 28MHz read waits, speed '
                     'transitions charged at 3.5MHz; 9907 -> 8F95 by the original with one limiter IRQ; no hardware'}


def _cw_n(level, i):
    """State number: sets the CTC phase and the every-50th IRQ/control sample. Depends only on
    (level, index), so one level, a sample or a single state checks exactly what the full run does."""
    return int(level) * 1000 + i


def _cw_pick(level, i, sample=1, only=None):
    if only:
        return '%s:%d' % (level, i) in only
    return i % sample == 0


def _cw_store(reference, level, cache):
    """The owned store the 8EF9 driver builds for a level (cached beside the states)."""
    import pickle
    from hashlib import md5
    tag = md5((load_profile()['hooks']['driver'] + load_profile()['hooks']['cwsel']).encode()).hexdigest()[:8]
    path = Path('%s.store%s.%s' % (cache, level, tag)) if cache else None
    if path and path.exists():
        return pickle.loads(path.read_bytes())
    ram, regs, frame = driver_boundary_state(Path(reference) / ('Inferno%s.rzx' % level))
    store = driver_store(run_loading_driver(ram, regs))
    if path:
        path.write_bytes(pickle.dumps(store))
    return store


def _cw_load_states(reference, levels, stop, every, cache):
    """{site: {level: states}} for 8F92 and 8F7C; with cache, one pickle per level (<cache>.<level>)."""
    import pickle
    both, missing = {0x8F92: {}, 0x8F7C: {}}, []
    for level in levels:
        f = Path('%s.%s' % (cache, level)) if cache else None
        if f is not None and f.exists():
            d = pickle.loads(f.read_bytes())
            for s in both:
                both[s][level] = d[s]
        else:
            missing.append(level)
    if missing:
        got = _cw_states(Path(reference), missing, stop, every, sites=(0x8F92, 0x8F7C))
        for level in missing:
            for s in both:
                both[s][level] = got[s][level]
            if cache:
                Path('%s.%s' % (cache, level)).write_bytes(pickle.dumps({s: both[s][level] for s in both}))
    return both


def _cw_merge(parts):
    """Merge per-level results: counts add ('max ...'/'min ...' keep the extreme), failures concatenate,
    T ranges keep min/max (percentiles stay per level, under 'per_level_results')."""
    def counts(dicts):
        out = Counter()
        for d in dicts:
            for k, v in d.items():
                if k.startswith('max'):
                    out[k] = max(out.get(k, v), v)
                elif k.startswith('min'):
                    out[k] = min(out.get(k, v), v)
                else:
                    out[k] += v
        return dict(out)

    def ranges(dicts):
        dicts = [d for d in dicts if d and d.get('min') is not None]
        return {'min': min(d['min'] for d in dicts), 'max': max(d['max'] for d in dicts)} if dicts else {}

    def merge(rs):
        out = {'counts': counts([r['counts'] for r in rs]), 'failures': sum((r['failures'] for r in rs), []),
               'negative_controls': counts([r['negative_controls'] for r in rs])}
        for k in rs[0]:
            if k.endswith('_T') and isinstance(rs[0][k], dict):
                out[k] = ranges([r[k] for r in rs])
            elif k.endswith('_ms_max'):
                out[k] = max(r[k] for r in rs)
            elif k.endswith('_ms_min'):
                out[k] = min(r[k] for r in rs)
            elif k in ('scope', 'kt_fast_switches_T'):
                out[k] = rs[0][k]
        return out
    out = merge(parts)
    out['per_level'] = {}
    for r in parts:
        out['per_level'].update(r.get('per_level', {}))
    if all('update' in r for r in parts):
        out['update'] = merge([r['update'] for r in parts])
        out['update']['scope'] = parts[0]['update']['scope']
    out['per_level_results'] = parts
    return out


def copier_window_parallel(reference, levels, jobs, args):
    """One process per level (`--jobs`): the same checks, about 6x faster on 6 cores; merged JSON."""
    import subprocess
    import sys
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='cw_levels_'))
    procs, outs = [], []
    for level in levels:
        out = tmp / ('level%s.json' % level)
        cmd = [sys.executable, '-m', 'nexclash.inferno', '--copier-window-checks', str(reference),
               '--cw-levels', level, '--json', str(out)] + args
        procs.append((level, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(tmp / ('level%s.err' % level), 'w'))))
        outs.append(out)
        while sum(p.poll() is None for _, p in procs) >= jobs:
            procs[[p.poll() is None for _, p in procs].index(True)][1].wait()
    for level, p in procs:
        p.wait()
    parts = []
    for level, out in zip(levels, outs):
        if not out.exists():
            raise AssertionError('level %s produced no result: %s' % (level, (tmp / ('level%s.err' % level)).read_text()[-2000:]))
        parts.append(json.loads(out.read_text()))
    return _cw_merge(parts)


def copier_window_checks(reference, levels=('1', '2', '3', '4', '5', '6'), stop=2000, every=1, xs=None, cache=None,
                         update=True, sample=1, only=None):
    """Copier window milestone 2 on every sampled 8F92 state.

    Per state: window-only patch (x = 0), CTC phase varied per state. With xs (per-level lists of the
    capture hooks' measured time before 8F92, aligned with the states): the same state entered x late
    (accumulate-X), which must still enter 9907 on time; late OUTs are reported. Every 50th state: IRQ
    injection at 20 points over 8F92..9907, units (untested/absent CTC) and negative controls."""
    reference = Path(reference)
    patch = CopierWindowPatch(window_only=True)
    syms = patch.syms
    controls = {name: (CopierWindowPatch(code, window_only=True), needs_irq)
                for name, (code, needs_irq) in copier_window_controls(patch.head, syms).items()}
    counts, failures, detected, per = Counter(), [], Counter(), {}
    dts_all, late_x, d9907s = [], [], []
    both = _cw_load_states(reference, levels, stop, every, cache)
    states = both[0x8F92]

    def fail(level, i, what, res):
        if len(failures) < 12:
            failures.append({'level': level, 'state': i, 'case': what, 'errors': res['errors'][:3] if isinstance(res, dict) else [str(res)]})
        counts['failures'] += 1

    for level, cases in states.items():
        w = per.setdefault(level, Counter())
        xlist = (xs or {}).get(level)
        if xlist is not None and len(xlist) != len(cases):
            raise AssertionError('X list does not align with level %s states' % level)
        for i, (ram, regs, port) in enumerate(cases):
            if not _cw_pick(level, i, sample, only):
                continue
            n = _cw_n(level, i)
            counts['states'] += 1
            phase, count0 = (n * 13) % CW_TICK, (n * 37) & 255
            res = run_cw_window(patch, ram, regs, phase=phase, count0=count0)
            counts['OUT changes'] += res['changes']
            if res['errors'] or res['fallback']:
                fail(level, i, 'x=0', res)
            dts_all.extend(res['dts'])
            d9907s.append(res['d9907'])
            counts['late OUTs at x=0'] += res['late']
            if res['late'] - (1 if res['values'] and res['values'][0] == port else 0) > 0:
                counts['states with late level changes at x=0'] += 1
                counts['max late T at x=0'] = max(counts['max late T at x=0'], round(res['late_T']))
            w['max_window_ms'] = max(w['max_window_ms'], round(res['o9907'] / 3500, 3))
            w['max_busy_ms'] = max(w['max_busy_ms'], round(res['busy_T'] / 3500, 3))
            w['min_wait_ms'] = min(w.get('min_wait_ms', 99), round(res['wait_T'] / 3500, 3))
            spans = [s for t, s in res['di_spans']]
            counts['max entry DI span T'] = max(counts['max entry DI span T'], round(spans[0]))
            counts['max exit DI span T'] = max(counts['max exit DI span T'], round(spans[-1]))
            counts['max other DI span T'] = max([counts['max other DI span T']] + [round(s) for s in spans[1:-1]])
            if xlist is not None:
                x = int(round(xlist[i]))
                rx = run_cw_window(patch, ram, regs, x=x, phase=phase, count0=count0)
                counts['accumulate-X states'] += 1
                if rx['errors']:
                    fail(level, i, 'x=%d' % x, rx)
                d9907s.append(rx['d9907'])
                if rx['late']:
                    counts['accumulate-X states with late OUTs'] += 1
                    counts['accumulate-X late OUTs'] += rx['late']
                    late_x.append(rx['late_T'])
                    # a late first OUT that repeats the port's current value changes nothing physical
                    physical = rx['late'] - (1 if rx['values'][0] == port else 0)
                    if physical > 0:
                        counts['accumulate-X states with late level changes'] += 1
            if n % 50 == 0:
                end = res['o9907']
                for j, t in enumerate([1 + j * (end - 300) / 19 for j in range(20)] + [40.0, 80.0, 120.0]):
                    ri = run_cw_window(patch, ram, regs, phase=phase, count0=count0, irqs=(t,))
                    counts['IRQ injections'] += 1
                    if ri['irqs_lost']:     # entry DI span: compensated from NextReg $C8 (milestone 3)
                        counts['IRQ in the entry DI span (compensated)'] += 1
                        counts['IRQ in the entry DI span max at T'] = max(counts['IRQ in the entry DI span max at T'], round(t))
                    else:
                        counts['IRQ taken in window' if ri['irqs_taken'] else 'IRQ taken by game code'] += 1
                    if ri['irq_delayed']:
                        counts['OUTs delayed by an IRQ handler'] += len(ri['irq_delayed'])
                        counts['max IRQ-delayed OUT T'] = max(counts['max IRQ-delayed OUT T'], max(ri['irq_delayed']))
                    if ri['errors'] or ri['original_irqs'] != 1:
                        fail(level, i, 'irq at %.0f' % t, ri)
                if end * 0.2 + 69888 < end - 500:
                    ri = run_cw_window(patch, ram, regs, phase=phase, count0=count0, irqs=(end * 0.2, end * 0.2 + 69888))
                    counts['IRQ double injections'] += 1
                    if ri['errors'] or ri['irqs_taken'] != 2:
                        fail(level, i, 'two irqs', ri)
                for name, (bp, needs_irq) in controls.items():
                    try:
                        bad = run_cw_window(bp, ram, regs, phase=phase, count0=count0,
                                            irqs=(end * 0.5,) if needs_irq else ())['errors']
                    except AssertionError as e:
                        bad = [str(e)]
                    detected[name + (' detected' if bad else ' MISSED')] += 1
                for clk, ctc, want in ((0, True, 1), (0, False, 2), (2, True, 2)):
                    ru = run_cw_window(patch, ram, regs, clk=clk, ctc=ctc, phase=phase, count0=count0)
                    counts['CTC unit clk=%d ctc=%s' % (clk, ctc)] += 1
                    if want == 1:   # first window after boot: the test runs before the time base read
                        ok = (ru['clk'] == 1 and not ru['fallback'] and ru['ctc_writes'] == [0x27, 0] and ru['d9907'] > 0
                              and not [e for e in ru['errors'] if not e.startswith('9907 off')])
                        counts['max first-window late T'] = max(counts['max first-window late T'], round(ru['d9907']))
                    else:           # original copier at original speed; R not restored
                        ok = ru['clk'] == 2 and ru['fallback'] and not [e for e in ru['errors'] if not e.startswith('R ')]
                        counts['max fallback 9907 late T'] = max(counts['max fallback 9907 late T'], round(ru['d9907']))
                    if not ok:
                        fail(level, i, 'CTC unit %d/%s' % (clk, ctc), ru)
    for level, w in per.items():
        per[level] = dict(w)
    dts_all.sort()
    q = lambda v, f: round(v[min(len(v) - 1, int(f * len(v)))]) if v else None
    out = {'counts': dict(counts), 'failures': failures, 'per_level': per,
           'out_offset_T': {'min': q(dts_all, 0), 'p1': q(dts_all, .01), 'median': q(dts_all, .5), 'p99': q(dts_all, .99), 'max': q(dts_all, 1)},
           'd9907_T': {'min': round(min(d9907s)) if d9907s else None, 'max': round(max(d9907s)) if d9907s else None},
           'accumulate_X_late_T': {'max': round(max(late_x, default=0)), 'median': q(sorted(late_x), .5)},
           'negative_controls': dict(detected),
           'scope': 'copier window 8F92->9907 in the simulator (uncontended T, 28MHz read waits, CTC and IRQ '
                    'models); no contention, no hardware'}
    if update:
        stores = {level: _cw_store(reference, level, cache) for level in levels}
        out['update'] = copier_window_update_checks(both[0x8F7C], sample=sample, only=only, stores=stores)
        out['failures'] = failures + out['update']['failures']
    return out


class CopierWindowSnapshotPatch(BootstrapPatch):
    """Software diagnostic from level 1: the copier window at 8F92 (cap_done + page 80), the bank
    loader as in the capture diagnostic; no sprite/Layer 2 display. window_only: no capture hooks
    (milestone 2, X = 0); else the capture hooks too (milestone 3: X measured, R restored, map copy
    by DMA). work (milestone 3b): + the 8F95 work in the window's waits, finished at 8F95 (page 69,
    bank 34's upper half; CW_WKEN set in page 80). Hardware test vehicle for pace and sound against
    the plain Inferno.nex; not a release."""
    name = 'Inferno copier-window diagnostic (no sprites; not a release)'
    tail_addr, max_tail = 0x9A80, 128

    def __init__(self, blocks, window_only=True, work=False, driver=False):
        super().__init__(blocks)
        self.window = CopierWindowPatch(window_only=window_only, work=work)
        if driver:                             # the 8EF9 gate joins the alt ROM and the sites
            gate = PausePatch()
            org = int(load_profile()['hooks']['syms']['pause_loading'], 16)
            code = gate.code
            if any(b != 255 for b in self.window.rom[org:org + len(code)]):
                raise ValueError('8EF9 gate overlaps the window ROM')
            self.window.rom[org:org + len(code)] = code
            self.window.sites[0x8EF9] = gate.sites[0x8EF9]
            h = load_profile()['hooks']                # leaving gameplay (death, break): hide the new layers
            code, org = bytes.fromhex(h['modalx']), 0x3BE0
            if any(b != 255 for b in self.window.rom[org:org + len(code)]):
                raise ValueError('modal hook overlaps the window ROM')
            self.window.rom[org:org + len(code)] = code
            self.window.sites[0x901C] = bytes.fromhex('FD213A5C'), b'\xC3' + org.to_bytes(2, 'little') + b'\x00'
        self.page = bytes(self.window.rom[8192:])
        self.extra_banks[12] = self.page + bytes(8192)
        rb = self.regblock - 0x2000            # the stub writes 20 register bytes there at boot
        if any(v != 255 for v in self.page[rb:rb + 20]):
            raise ValueError('hook code in the stub register block %04X-%04X' % (self.regblock, self.regblock + 19))
        head = bytearray(8192)
        head[:len(self.window.head)] = self.window.head      # CW_CLK = 0: CTC tested at first use
        if CW_PAGE // 2 in self.extra_banks:
            raise ValueError('page 80 already allocated')
        if work:
            head[CW_WKEN] = 2
            image = bytearray(self.extra_banks.get(69 // 2, bytes(16384)))
            if any(image[8192:]):
                raise ValueError('page 69 already allocated')
            image[8192:] = self.window.renderer
            self.extra_banks[69 // 2] = bytes(image)
            if 79 // 2 in self.extra_banks:
                raise ValueError('page 79 already allocated')
            self.extra_banks[79 // 2] = bytes(16384)    # empty store (no driver in this build): every dispatch misses
            if 82 // 2 in self.extra_banks:
                raise ValueError('page 82 already allocated')
            self.extra_banks[82 // 2] = bytes(select_page()) + bytes(8192)   # 83: index, written at 8EF9; 84-95 too
            if driver:
                pages = driver_pages()
                image = bytearray(self.extra_banks[69 // 2])
                image[:8192] = pages[68]               # state page: only the gate's 1D80 stub is non-zero
                self.extra_banks[69 // 2] = bytes(image)
                for even in (74, 76, 78, *range(96, 112, 2), *range(128, 136, 2)):
                    if even // 2 in self.extra_banks and even != 78:
                        raise ValueError('page %d already allocated' % even)
                    self.extra_banks[even // 2] = bytes(pages.get(even, bytes(8192))) + bytes(pages.get(even + 1, bytes(8192)))
                head_tail = bytes(pages[81])
        else:
            head_tail = bytes(8192)
        self.extra_banks[CW_PAGE // 2] = bytes(head) + (head_tail if work and driver else bytes(8192))
        self.sites = [(a, old, new) for a, (old, new) in self.window.sites.items()]

    def apply(self, snap):
        if snap.is128:
            raise ValueError('copier-window diagnostic expects original 48K Inferno')
        source = [0] * 16384 + list(snap.banks[5] + snap.banks[2] + snap.banks[0])
        ram = self.window.apply_memory(source)[16384:]
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])


def copier_window_build(reference, folder, hooks=False, work=False, driver=False):
    """Inferno_copier_window_diagnostic.nex (window only), with hooks Inferno_copier_window_m3_
    diagnostic.nex (capture hooks + window), with work Inferno_copier_window_m3b_diagnostic.nex (+ the
    8F95 work in the window's waits) + boot checks (NEXLOAD and foreign ROM3) + page-80/69 bytes."""
    from . import z80tonex, nextboot
    from .build import rom48
    from hashlib import md5
    reference, folder = Path(reference), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = reference / 'Inferno.z80'
    work = work or driver
    hooks = hooks or work
    patch = CopierWindowSnapshotPatch(tape_blocks(reference / 'Inferno.tzx'), window_only=not hooks, work=work, driver=driver)
    nex = folder / ('Inferno_driver_diagnostic.nex' if driver else 'Inferno_copier_window_m3b_diagnostic.nex' if work else
                    'Inferno_copier_window_m3_diagnostic.nex' if hooks else 'Inferno_copier_window_diagnostic.nex')
    _, tail, data, _ = z80tonex.convert(str(snapshot), str(nex), quiet=True, patch=patch)
    if driver:                                  # tables sit in banks 48+: the loader must refuse a 1 MB machine
        image = bytearray(nex.read_bytes())
        image[8] = 1
        nex.write_bytes(image)
    checks = {}
    for name, foreign in [('Sinclair', None), ('foreign ROM3', bytes(v ^ 0xA5 for v in rom48()))]:
        checks[name] = nextboot.check(str(nex), str(snapshot), patch, (tail, tail + len(data)),
                                      nexload=True, sysrom=foreign)
    # Hook bytes as the game finds them AFTER the stub (it writes its register block into the alt ROM;
    # 3a's cap_in sat under it and every hook crashed on hardware, 2026-11-08).
    from skoolkit.snapshot import Snapshot
    alt = nextboot.boot(str(nex), Snapshot.get(str(snapshot)).pc, nexload=True)['alt'][1]
    want = patch.window.rom
    hit = ['%04X' % a for a in range(0x2000, 0x3D00) if want[a] != rom48()[a] and alt[a] != want[a]]
    checks['hook bytes after boot'] = (['%d hook bytes overwritten, first %s' % (len(hit), hit[:4])] if hit else [])
    raw = nex.read_bytes()
    if raw.find(patch.extra_banks[CW_PAGE // 2]) < 0:
        checks['page 80'] = ['window page not in the NEX']
    if raw.find(patch.page[0x3CB0 - 0x2000:0x3CB0 - 0x2000 + len(bytes.fromhex(load_profile()['hooks']['cwrom']))]) < 0:
        checks['alt ROM'] = ['window trampoline not in the NEX']
    if driver:
        missing = [b for b in (37, 38, 39, 40, 41, *range(48, 56), *range(64, 68)) if raw.find(patch.extra_banks[b]) < 0]
        if missing:
            checks['driver banks'] = ['not in the NEX: %s' % missing]
        if raw[8] != 1:
            checks['RAM required'] = ['header does not ask for the expanded machine']
    if work and raw.find(patch.extra_banks[69 // 2][8192:]) < 0:
        checks['page 69'] = ['work page not in the NEX']
    return {'boot_checks': checks, 'tail': [tail, tail + len(data)], 'sites': ['%04X' % a for a, o, n in patch.sites],
            'nex_md5': md5(raw).hexdigest(), 'cwhead_md5': md5(patch.window.head).hexdigest(),
            'scope': 'level-1 snapshot; %s, bank loader as the capture diagnostic; boot state checked in '
                     'software, the window itself only in the simulator; not a release'
                     % ('capture hooks (X, R, DMA map copy) + copier window + the 8F95 work in its waits (8F95 finishes)'
                        if work else 'capture hooks (X, R, DMA map copy) + copier window' if hooks else 'copier window only (8F92)')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument('--loading-prep-check', type=Path)
    action.add_argument('--loading-prep-all', type=Path)
    action.add_argument('--loading-pause-checks', action='store_true')
    action.add_argument('--loading-driver-checks', action='store_true')
    action.add_argument('--dispatch-checks', action='store_true')
    action.add_argument('--select-checks', action='store_true')
    action.add_argument('--loading-driver-level', type=Path)
    ap.add_argument('--level', type=int, default=6)
    action.add_argument('--initialization-tests', type=Path)
    action.add_argument('--owned-cache-checks', action='store_true')
    action.add_argument('--copier-window-checks', type=Path)
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--cw-x', type=Path, help='per-level capture X (JSON) for the accumulate-X runs')
    ap.add_argument('--cw-cache', type=Path, help='state cache prefix: one pickle per level, <prefix>.<level> (written if absent)')
    ap.add_argument('--cw-levels', help='copier-window checks: these levels only, e.g. 3,6')
    ap.add_argument('--cw-sample', type=int, default=1, help='copier-window checks: every Nth state (same per-state cases)')
    ap.add_argument('--cw-only', help='copier-window checks: just these states, e.g. 3:182,6:27 (rerun failures)')
    ap.add_argument('--jobs', type=int, default=1, help='copier-window checks: one process per level, this many at once')
    ap.add_argument('--cw-hooks', action='store_true', help='--copier-window-build with the capture hooks (milestone 3)')
    ap.add_argument('--cw-work', action='store_true', help='--copier-window-build with hooks + the 8F95 work in the window (3b)')
    ap.add_argument('--cw-driver', action='store_true', help='--copier-window-build with the 8EF9 driver and its pages too (no display)')
    action.add_argument('--actor-job-checks', action='store_true')
    action.add_argument('--actor-pack-checks', action='store_true')
    action.add_argument('--actor-fill-checks', action='store_true')
    action.add_argument('--actor-blit-checks', action='store_true')
    action.add_argument('--actor-pack-check', type=Path)
    action.add_argument('--actor-pack-all', type=Path)
    action.add_argument('--modal-checks', type=Path)
    action.add_argument('--queue-checks', action='store_true')
    action.add_argument('--display-checks', action='store_true')
    action.add_argument('--frame-check', type=Path)
    action.add_argument('--frame-all', type=Path)
    action.add_argument('--textmap-check', type=Path)
    action.add_argument('--textmap-all', type=Path)
    action.add_argument('--textmap-units', type=Path)
    action.add_argument('--scenery-check', type=Path)
    action.add_argument('--scenery-all', type=Path)
    action.add_argument('--scene-renderer-checks', type=Path)
    action.add_argument('--tile-batch-units', action='store_true')
    action.add_argument('--tile-cache-units', action='store_true')
    action.add_argument('--tile-renderer-units', action='store_true')
    action.add_argument('--render-model-units', action='store_true')
    action.add_argument('--capture-all', type=Path)
    action.add_argument('--capture-build', type=Path)
    action.add_argument('--copier-window-build', type=Path)
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
    if a.initialization_tests:
        result = continuation_tests(a.initialization_tests,initialization=True)
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.loading_prep_check or a.loading_prep_all:
        result = (capture_all(a.loading_prep_all,a.out,a.quick,progress=print,scenery='textmap',frame=True,pack=True,loading=True)
                  if a.loading_prep_all else model_verify(a.loading_prep_check,a.quick,capture=True,scenery='textmap',frame=True,pack=True,loading=True))
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return int(any(c['failures'] for c in result['cases'])) if a.loading_prep_all else int(bool(result['examples']))
    if a.select_checks:
        result = select_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.dispatch_checks:
        result = dispatch_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.loading_driver_checks or a.loading_driver_level:
        result = driver_checks() if a.loading_driver_checks else driver_level_check(a.loading_driver_level, a.level)
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.loading_pause_checks:
        result = loading_pause_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.copier_window_checks:
        xs = None
        if a.cw_x:
            xs = {k: (v['X'] if isinstance(v, dict) else v) for k, v in json.loads(a.cw_x.read_text()).items()}
        levels = tuple(a.cw_levels.split(',')) if a.cw_levels else ('1', '2', '3', '4', '5', '6')
        only = set(a.cw_only.split(',')) if a.cw_only else None
        if only and not a.cw_levels:
            levels = tuple(sorted({s.split(':')[0] for s in only}))
        if a.jobs > 1 and len(levels) > 1:
            passed = ['--quick', str(a.quick), '--cw-sample', str(a.cw_sample)]
            for flag, value in (('--cw-x', a.cw_x), ('--cw-cache', a.cw_cache), ('--cw-only', a.cw_only)):
                if value:
                    passed += [flag, str(value)]
            result = copier_window_parallel(a.copier_window_checks, levels, a.jobs, passed)
        else:
            result = copier_window_checks(a.copier_window_checks, levels=levels, stop=a.quick, every=a.every, xs=xs,
                                          cache=a.cw_cache, sample=a.cw_sample, only=only)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(bool(result['failures']))
    if a.owned_cache_checks:
        result = owned_cache_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.actor_job_checks:
        result = actor_job_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.actor_blit_checks:
        result = actor_blit_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.actor_fill_checks:
        result = actor_fill_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.actor_pack_checks:
        result = actor_pack_checks()
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0
    if a.actor_pack_check or a.actor_pack_all:
        if a.quick <= 0:
            ap.error('--quick must be positive')
        result = (capture_all(a.actor_pack_all,a.out,a.quick,progress=print,scenery='textmap',frame=True,pack=True)
                  if a.actor_pack_all else model_verify(a.actor_pack_check,a.quick,capture=True,scenery='textmap',frame=True,pack=True))
        result['scope'] = 'frame preservation plus offline assembled colour expansion and quota-serviced whole-image B fill on host-model exact-content misses; live-table preparation census is a host model; no installed cache/scheduler/upload/sprite display'
        if a.actor_pack_all:
            result['timing_gate'] = {'target_total_added_ms':10,'status':'FAIL',
                                    'cold_capture_scenery_colour_fill_max_ms':result['counts']['max capture scenery cold colour and B fill equivalent T']/3500,
                                    'excluded':'runtime cache validation/allocation, uploads, queue and external fill-service wrapper',
                                    'hardware_proof':False}
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return int(any(v for k,v in result['counts'].items() if k.endswith('!')))
    if a.frame_check or a.frame_all:
        if a.quick <= 0:
            ap.error('--quick must be positive')
        result = (capture_all(a.frame_all,a.out,a.quick,progress=print,scenery='textmap',frame=True)
                  if a.frame_all else model_verify(a.frame_check,a.quick,capture=True,scenery='textmap',frame=True))
        result['scope'] = 'capture and assembled post-copy preparation; all game registers/RAM preserved; display stays disabled without sprite compiler'
        if a.json:
            a.json.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return int(any(v for k,v in result['counts'].items() if k.endswith('!')))
    if a.display_checks:
        result = display_checks()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0
    if a.queue_checks:
        result = queue_checks()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0
    if a.modal_checks:
        result = modal_checks(a.modal_checks)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0
    if a.textmap_check or a.textmap_units or a.textmap_all:
        if a.quick <= 0:
            ap.error('--quick must be positive')
        result = (capture_all(a.textmap_all, a.out, a.quick, progress=print, scenery='textmap')
                  if a.textmap_all else model_verify(a.textmap_check, a.quick, capture=True, scenery='textmap')
                  if a.textmap_check else textmap_checks(a.textmap_units))
        if a.textmap_check or a.textmap_all:
            result['scope'] = 'capture + offline assembled textmap construction; no installed display or sprite/commit timing'
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if (a.model_check or a.capture_check or a.capture_all or a.scenery_all or a.scenery_check) and a.quick <= 0:
        ap.error('--quick must be positive')
    if a.scenery_check:
        result = model_verify(a.scenery_check, a.quick, capture=True, scenery=True)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.scenery_all:
        result = capture_all(a.scenery_all, a.out, a.quick, progress=print, scenery=True)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.scene_renderer_checks:
        result = scene_renderer_checks(a.scene_renderer_checks, a.out)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.tile_batch_units:
        result = tile_batch_units()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.tile_cache_units:
        result = tile_cache_units()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
    if a.tile_renderer_units:
        result = tile_renderer_units()
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(v for k, v in result['counts'].items() if k.endswith('!')))
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
    if a.copier_window_build:
        result = copier_window_build(a.copier_window_build, a.out, hooks=a.cw_hooks, work=a.cw_work, driver=a.cw_driver)
        if a.json:
            a.json.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(any(result['boot_checks'].values()))
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
