"""Movie (Imagine, 1986): exact archive input and native graphics decoding.

Game bytes, recordings, derived assets and editable paintings are supplied locally.
The original-presentation build restores its temporary loader workspace completely.
See games/movie.md for the exact source, proof scope and coverage limits.
"""
import copy
from collections import Counter
from skoolkit import CSimulator
from . import rzx
import hashlib
import json
import os
from pathlib import Path
from . import hooklib, z80tonex as Z

SOURCE_MD5 = 'facf9b90032759b7012abd91602b4b45'
LOADING_SHA256 = '7fffacad76b83ba6bb939ee850c0ede6688993e00cb084712f9b955359732acd'
PLAY_HEIGHT = 168  # Original direct-drawn icon selection occupies the final 24 rows.
CMP = hooklib.CMP_R
ROOT = Path(__file__).resolve().parents[1]
REVERSE = tuple(int(f'{v:08b}'[::-1], 2) for v in range(256))
TRAINERS = {
    'Infinite lives': ((0xFD89,0x00,0x29),(0xFD8A,0xE0,0xF8)),
    "Enemies don't move": ((0xE7F2,0xE5,0xC9),),
    "Enemies don't shoot": ((0xE991,0x0B,0x00),),
    'Skip final film check': ((0x78C2,0xCD,0xAF),(0x78C3,0xF9,0),(0x78C4,0x78,0)),
    'Start with film reel': ((0xFC2E,0,11),(0xFC0A,0x22,0),(0xFC0B,0x2E,0),(0xFC0C,0xFC,0)),
}


def load_profile():
    return json.loads((ROOT / 'docs/profiles/movie.json').read_text())


def is_movie(snap):
    sig = load_profile()['signature']
    if getattr(snap, 'machine', '') not in ('48K', '48K/128K'):
        return False
    memory = snap.memory() if callable(getattr(snap, 'memory', None)) else snap.memory
    return bytes(memory[sig['addr']:sig['addr'] + len(bytes.fromhex(sig['hex']))]) == bytes.fromhex(sig['hex'])


def word(m, a):
    return m[a] | m[a + 1] << 8


def graphic_parts(m, source):
    """Native header -> width, height, (rows, mask address, bitmap address) parts.

    The mask bits are stored reversed; their original consumer reverses them through
    the 8000 lookup table. None denotes the unmasked direct graphics format.
    """
    header, height = m[source - 1], m[source]
    width, fmt = (header & 7) + 1, header >> 6
    if fmt == 3:
        parts = [(height, None, source + 1)]
    elif fmt == 2:
        parts = [(height, source + 1 + width * height, source + 1)]
    elif fmt == 1:
        parts = [(height, word(m, source + 1), source + 3)]
    else:
        count = (((header + 8) >> 4) + 1) & 7
        parts = [(m[source + 1 + n * 5], word(m, source + 4 + n * 5),
                  word(m, source + 2 + n * 5)) for n in range(count)]
        if sum(h for h, _, _ in parts) != height:
            raise ValueError(f'Movie graphic {source:04X}: inconsistent multipart height')
    return width * 8, height, parts


def decode_graphic(m, source):
    """Pixels and their original bitmap owners; 0 clear, 1 opaque black, 2 ink."""
    width, height, parts = graphic_parts(m, source)
    pixels, owners = [], []
    for rows, mask, bitmap in parts:
        for y in range(rows):
            row, own = [], []
            for x in range(width):
                offset, bit = y * (width // 8) + x // 8, 128 >> (x & 7)
                ink = bool(m[bitmap + offset] & bit)
                clear = mask is not None and bool(REVERSE[m[mask + offset]] & bit)
                row.append(2 if ink else 0 if clear else 1)
                own.append((bitmap + offset, x & 7))
            pixels.append(row)
            owners.append(own)
    return pixels, owners


def art_inventory(memory):
    """Validate the original 256-entry pointer table before decoding its graphics."""
    # The main table stores headers; these consumers store height pointers directly:
    # 718D/812C (CF43), F1CC and 6B74/6B79 (843D/844F), 9459 (B0D1).
    sources = {0xD201, 0xCF43, 0x843D, 0x844F, 0xB0D1}
    for at in range(0xD000, 0xD200, 2):
        source = word(memory, at) + 1
        if not 0x7000 < source < 0xE000: continue
        try:
            width, height, parts = graphic_parts(memory, source)
            if not 1 <= height <= 96 or not parts: continue
            if not all(0x7000 <= b and b + width // 8 * rows <= 0xE000
                       and (mask is None or 0x7000 <= mask and mask + width // 8 * rows <= 0xE000)
                       for rows, mask, b in parts): continue
            sources.add(source)
        except (ValueError, IndexError): continue
    return sorted(sources)


def export_art(source, out):
    """Original-pixel editable baseline. Never overwrite an existing painting."""
    from PIL import Image, ImageDraw
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    sheet_path = out / 'MOVIE_PAINTING_SPRITES.png'
    if sheet_path.exists(): raise FileExistsError('Preserve existing Movie painting; choose a new directory')
    snap = Z.Z80Snapshot(str(source))
    m = list(Z.rom48()) + list(snap.banks[5] + snap.banks[2] + snap.banks[0])
    sources = art_inventory(m)
    scale, cw, ch, columns = 4, 280, 416, 8
    sheet = Image.new('RGB', (columns * cw, ((len(sources) + columns - 1) // columns) * ch), (48, 52, 58))
    draw = ImageDraw.Draw(sheet)
    entries, assignments, conflicts = [], {}, []
    cache = bytearray([255]) * 229376
    for address in range(0x7000, 0xE000):
        cache[(address - 0x7000) * 8:(address - 0x7000 + 1) * 8] = bytes(1 if m[address] & (128 >> b) else 0 for b in range(8))
    for i, src in enumerate(sources):
        pixels, owners = decode_graphic(m, src)
        w, h = len(pixels[0]), len(pixels)
        x, y = i % columns * cw + 8, i // columns * ch + 24
        im = Image.new('RGB', (w, h))
        im.putdata([(219, 219, 182) if p == 2 else (0, 0, 0) if p == 1 else (48, 52, 58) for row in pixels for p in row])
        sheet.paste(im.resize((w * scale, h * scale), Image.Resampling.NEAREST), (x, y))
        draw.text((x, y - 18), f'{src:04X}  {w} x {h}', fill=(230, 230, 230))
        entries.append(dict(source=src, x=x, y=y, width=w, height=h, scale=scale))
        for row, own in zip(pixels, owners):
            for p, (address, bit) in zip(row, own):
                index = (address - 0x7000) * 8 + bit
                value = 1 if p == 2 else 0 if p == 1 else 255
                if index in assignments and assignments[index] != value: conflicts.append((address, bit))
                assignments[index] = value
                cache[index] = value
    sheet.save(sheet_path)
    palette = [0] * 256; palette[1] = (6 << 6) | (6 << 3) | 5; palette[255] = 0x1C7
    (out / 'palette.bin').write_bytes(b''.join(v.to_bytes(2, 'little') for v in palette))
    (out / 'colours.bin').write_bytes(cache)
    (out / 'painting.json').write_text(json.dumps(dict(source_md5=hashlib.md5(Path(source).read_bytes()).hexdigest(),
        entries=entries, opacity_conflicts=sorted(set(conflicts))), indent=2) + '\n')
    return {'assets': len(sources), 'opacity_conflicts': len(set(conflicts)), 'sheet': str(sheet_path)}


def painting_sheet(source, assets, destination):
    """Re-export native-sized, flat-colour cells; shared parts use the same pixels."""
    from PIL import Image, ImageDraw
    assets = Path(assets)
    layout = json.loads((assets / 'painting.json').read_text())
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != layout['source_md5']:
        raise ValueError('Painting belongs to a different Movie release')
    s = Z.Z80Snapshot(str(source)); m = list(Z.rom48() + s.banks[5] + s.banks[2] + s.banks[0])
    colours = (assets / 'colours.bin').read_bytes(); palette = (assets / 'palette.bin').read_bytes()
    def rgb(i):
        v = int.from_bytes(palette[2*i:2*i+2], 'little')
        return tuple(round(((v >> shift) & 7) * 255 / 7) for shift in (6, 3, 0))
    im = Image.new('RGB', (2240, ((len(layout['entries']) + 7) // 8) * 416), (48,52,58))
    draw = ImageDraw.Draw(im)
    for entry in layout['entries']:
        px, owners = decode_graphic(m, entry['source'])
        w,h,k = entry['width'],entry['height'],entry['scale']
        tile = Image.new('RGB',(w,h))
        tile.putdata([rgb(colours[(a-0x7000)*8+b]) if p == 2 else (0,0,0) if p == 1 else (48,52,58)
                      for row,own in zip(px,owners) for p,(a,b) in zip(row,own)])
        im.paste(tile.resize((w*k,h*k),Image.Resampling.NEAREST),(entry['x'],entry['y']))
        draw.text((entry['x'],entry['y']-18),f"{entry['source']:04X}  {w} x {h}",fill=(230,230,230))
    im.save(destination)


def import_painting(source, assets, sheet, out):
    """Only edited ink pixels propagate to shared animation parts; no blending.

    Reject contradictory edits to a shared pixel, changed silhouettes/black line
    art, or a cell painted between native pixels. Preserve the input PNG.
    """
    from PIL import Image
    assets, out = Path(assets), Path(out)
    layout = json.loads((assets/'painting.json').read_text())
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != layout['source_md5']:
        raise ValueError('Painting belongs to a different Movie release')
    s=Z.Z80Snapshot(str(source)); m=list(Z.rom48()+s.banks[5]+s.banks[2]+s.banks[0])
    cache=bytearray((assets/'colours.bin').read_bytes()); raw=(assets/'palette.bin').read_bytes()
    palette=[int.from_bytes(raw[i:i+2],'little') for i in range(0,512,2)]
    def rgb(v): return tuple(round(((v >> sh)&7)*255/7) for sh in (6,3,0))
    pic=Image.open(sheet).convert('RGB'); edits={}
    for e in layout['entries']:
        px,owners=decode_graphic(m,e['source']); k=e['scale']
        for y,(row,own) in enumerate(zip(px,owners)):
            for x,(p,(a,b)) in enumerate(zip(row,own)):
                idx=(a-0x7000)*8+b
                old=rgb(palette[cache[idx]]) if p==2 else (0,0,0) if p==1 else (48,52,58)
                tile=pic.crop((e['x']+x*k,e['y']+y*k,e['x']+(x+1)*k,e['y']+(y+1)*k))
                values=set(tile.getdata())
                if values=={old}: continue
                if p != 2 or len(values)!=1:
                    raise ValueError(f"Edit crosses protected drawing or native pixel at {e['source']:04X}/{x},{y}")
                c=values.pop(); value=sum(round(v*7/255)<<sh for v,sh in zip(c,(6,3,0)))
                if value==0 or value>>1==0xE3: raise ValueError('Black line art and transparency are reserved')
                if idx in edits and edits[idx]!=value: raise ValueError(f'Conflicting edits to shared pixel {a:04X}/{b}')
                edits[idx]=value
    used=set(cache)-{255}; lookup={palette[i]:i for i in used}
    free=[i for i in range(1,255) if i not in used]
    for idx,value in sorted(edits.items()):
        if value not in lookup:
            if not free: raise ValueError('Movie painting exceeds 254 ink colours')
            i=free.pop(0);palette[i]=value;lookup[value]=i
        cache[idx]=lookup[value]
    out.mkdir(parents=True,exist_ok=True)
    (out/'colours.bin').write_bytes(cache)
    (out/'palette.bin').write_bytes(b''.join(v.to_bytes(2,'little') for v in palette))
    (out/'painting.json').write_text(json.dumps(layout,indent=2)+'\n')
    painting_sheet(source,out,out/'MOVIE_PAINTING_SPRITES.png')
    return {'edited_shared_pixels':len(edits),'ink_colours':len(set(cache)-{0,255})}


def kernel_trial(memory, descriptor, live=False, shift=0):
    """Execute the assembled companion primitive against an original captured chunk.

    This validates the pixel primitive, not the not-yet-integrated game hooks.
    The cache is constructed from native source bytes and independent masks.
    """
    from .dizzy6 import _rw_simulator
    from . import simpool, z80n
    data = list(memory)
    pages = {}
    d = descriptor
    for y in range(d['height']):
        for col in range(d['width']):
            delta = y * d['source_stride'] + (-col if d['mirror'] else col)
            bitmap = (d['bitmap'] + delta) & 65535
            mask = REVERSE[memory[(d['mask'] + delta) & 65535]] if d['mask'] is not None else 0
            bits = memory[bitmap]
            pixels = [1 if bits & (128 >> bit) else 255 if mask & (128 >> bit) else 0 for bit in range(8)]
            page, offset = (bitmap >> 10) + 6, (bitmap & 1023) * 8
            pages.setdefault(page, [255] * 8192)[offset:offset + 8] = pixels
            pages.setdefault(page+28, [0] * 8192)[offset:offset + 8] = [0 if v==255 else v for v in pixels]
    data[:2048] = [(memory[0x9500 + i // 8] >> (7 - i % 8)) & 1 for i in range(2048)]
    blob = bytes.fromhex(load_profile()['hooks']['kernel'])
    data[0x0800:0x0800 + len(blob)] = blob
    blob = bytes.fromhex(load_profile()['hooks']['bulk'])
    data[0x1000:0x1000 + len(blob)] = blob
    values = (d['bitmap'], d['mask'] or 0,
              (d['destination'] * 8 + d['phase'] + shift) & 2047,
              d['source_stride'], d['destination_stride'] * 8)
    for n, value in enumerate(values):
        data[0x1D00 + n * 2:0x1D02 + n * 2] = list((value & 65535).to_bytes(2, 'little'))
    data[0x1D0A:0x1D0F] = [d['width'], d['height'], int(d['mirror']), int(d['mask'] is not None), int(live)]
    data[0x1F00:0x1F02] = [0x80, 0x3C]

    class Mem:
        def __init__(self):
            self.page = 0
            self.data = data
            self.pages = pages

        def __len__(self):
            return 65536

        def __getitem__(self, a):
            if isinstance(a, slice):
                return [self[i] for i in range(*a.indices(65536))]
            return self.pages[self.page][a & 8191] if 0x4000 <= a < 0x6000 else self.data[a]

        def __setitem__(self, a, value):
            if 0x4000 <= a < 0x6000:
                raise AssertionError('Colour cache must be read-only')
            self.data[a] = value

    mem = Mem()
    sim = simpool.machine(_rw_simulator(), mem, slot='movie-kernel')
    sim.low_writes = True
    sim.registers[:] = [0] * len(sim.registers)
    sim.registers[12], sim.registers[24] = 0x1F00, 0x0800

    def nextreg(n, value):
        if n != 0x52:
            raise AssertionError(('Unexpected primitive NextREG', n, value))
        mem.page = value

    z80n.install(sim, nextreg)
    steps = 0
    while sim.registers[24] != 0x3C80:
        sim.opcodes[mem[sim.registers[24]]]()
        steps += 1
        if steps > 250000:
            raise RuntimeError(('Companion primitive did not return', sim.registers[24]))
    return mem.data[:2048], sim.registers[25]


CHUNKS = ((0xF421, 'C367F5', 'h_masked', 0xF567),
          (0xF42B, 'C382F5', 'h_mirror', 0xF582),
          (0xF4A0, 'C3A0F5', 'h_shifted', 0xF5A0),
          (0xF4BF, 'C3E6F5', 'h_shift_mirror', 0xF5E6),
          (0xF39A, '23F9EB', 'h_plain_two', 0xF39D),
          (0xF3A9, 'F9EB1600', 'h_plain_one', 0xF3AF),
          (0xF3BC, 'F9EB1680', 'h_plain_mirror', 0xF3C0),
          (0xF3D5, 'F9EB1680', 'h_plain_mirror_one', 0xF3D9))


class DrawingMemory:
    """Only the mappings used by the Movie hooks; raster time excludes contention."""
    def __init__(self, memory, colours=None, clock=0, hooks=None):
        from .dma import DMA
        self.data = list(memory)
        self.private = [0] * 8192
        self.nr = {7: clock, 0x50: 255, 0x52: 10}
        self.selected, self.elapsed = 0, 0
        self.pages = {p: [255] * 8192 for p in range(28, 90)}
        if colours is not None:
            colours = initial_speech(colours, memory)
            for p in range(34, 62):
                self.pages[p][:] = colours[(p - 34) * 8192:(p - 33) * 8192]
                self.pages[p+28][:] = [0 if v==255 else v for v in self.pages[p]]
        self.private[0x1E00:0x1F00] = speech_cache_bits(colours) if colours is not None else memory[0xD200:0xD300]
        hooks = hooks or load_profile()['hooks']
        for key, at in (('kernel', 0x800), ('helper', 0xA00), ('bulk', 0x1000), ('library', 0x1800)):
            blob = bytes.fromhex(hooks[key]); self.private[at:at + len(blob)] = blob
        blob = bytes.fromhex(hooks['resident'])
        self.data[0x3B20:0x3B20 + len(blob)] = blob
        self.core, self.hardware_im2 = 0x33, 0
        self.dma = DMA(self.__getitem__,self.__setitem__,self.dma_io,
                       blitter=True,stall=self.dma_stall)

    def dma_io(self, port, value):
        raise AssertionError('Unexpected DMA I/O')

    def dma_stall(self, count):
        self.elapsed += count / 4  # Injected model timing, not a hardware measurement.

    def __len__(self): return 65536

    def __getitem__(self, a):
        if isinstance(a, slice): return [self[i] for i in range(*a.indices(65536))]
        if a < 8192 and self.nr[0x50] == 26: return self.private[a]
        if 0x4000 <= a < 0x6000 and self.nr[0x52] in self.pages:
            return self.pages[self.nr[0x52]][a & 8191]
        return self.data[a]

    def __setitem__(self, a, value):
        if a < 8192 and self.nr[0x50] == 26: self.private[a] = value
        elif 0x4000 <= a < 0x6000 and self.nr[0x52] in self.pages:
            self.pages[self.nr[0x52]][a & 8191] = value
        else: self.data[a] = value

    def nextreg(self, n, value): self.nr[n] = value

    def write_port(self, r, port, value, *extra):
        if port == 0x243B: self.selected = value
        elif port == 0x253B: self.nextreg(self.selected, value)
        elif port & 255 == 0x6B: self.dma.feed(value)
        else: raise AssertionError(('Unexpected hook output', port, value))

    def read_port(self, r, port):
        if port != 0x253B: raise AssertionError(('Unexpected hook input', port))
        line = int(self.elapsed // 224) % 312
        if self.selected == 0x1E: return line >> 8
        if self.selected == 0x1F: return line & 255
        if self.selected == 1: return self.core
        if self.selected == 0xC0: return self.hardware_im2
        return self.nr.get(self.selected, 0)


def chunk_trial(memory, case, clock=0, iff=None):
    """Native original versus the complete assembled entry/body/exit hook."""
    from .dizzy6 import _rw_simulator
    from . import simpool, z80n
    pc, expected, label, _ = next(c for c in CHUNKS if c[3] == case['pc'])
    kind = [c[0] for c in CHUNKS].index(pc)
    r = list(case['registers']); d = case['descriptor']
    if kind >= 4:
        source = r[12] - (1 if kind == 4 else 0)
        r[4:6], r[6:8] = r[6:8], [source >> 8, source & 255]
        r[12] = 0x93E0
    r[15] = (r[15] & 128) | ((r[15] - (5 if kind == 5 else 3 if kind >= 4 else 1)) & 127)
    r[24], r[25] = pc, 0
    if iff is not None: r[26] = iff
    native = simpool.machine(CSimulator, list(memory), slot='movie-native-chunk')
    for i, value in enumerate(r): native.registers[i] = value
    end = 0xF523 if kind >= 4 else word(memory, 0xF5E4)
    native.run(stop=end)
    mem = DrawingMemory(memory, clock=clock)
    for y in range(d['height']):
        for col in range(d['width']):
            delta = y * d['source_stride'] + (-col if d['mirror'] else col)
            a = (d['bitmap'] + delta) & 65535
            mask = REVERSE[memory[(d['mask'] + delta) & 65535]] if d['mask'] is not None else 0
            pixels = [1 if memory[a] & (128 >> b) else 255 if mask & (128 >> b) else 0 for b in range(8)]
            p, offset = (a >> 10) + 6, (a & 1023) * 8
            mem.pages[p][offset:offset + 8] = pixels
            mem.pages[p+28][offset:offset + 8] = [0 if v==255 else v for v in pixels]
    mem.private[:2048] = [(memory[0x9500 + i // 8] >> (7 - i % 8)) & 1 for i in range(2048)]
    syms = {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}
    sites = [(pc, bytes.fromhex(expected), syms[label]), (0xF3D2 if kind >= 4 else 0xF5E3,
             bytes(memory[0xF3D2 if kind >= 4 else 0xF5E3: (0xF3D2 if kind >= 4 else 0xF5E3) + 3]), syms['post_chunk'])]
    ignored = set()
    for at, old, target in sites:
        assert bytes(mem.data[at:at + len(old)]) == old
        mem.data[at:at + len(old)] = [0xC3, target & 255, target >> 8] + [0] * (len(old) - 3)
        ignored.update(range(at, at + len(old)))
    mem.data[0x3E0C:0x3E0E] = [end & 255, end >> 8]
    sim = simpool.machine(_rw_simulator(), mem, slot='movie-patched-chunk')
    sim.low_writes = True; sim.registers[:] = r; sim.set_tracer(mem)
    z80n.install(sim, mem.nextreg)
    steps = 0
    while sim.registers[24] != end:
        t, speed = sim.registers[25], mem.nr[7]
        sim.opcodes[mem[sim.registers[24]]]()
        mem.elapsed += (sim.registers[25] - t) / (1 << speed)
        steps += 1
        if steps > 500000:
            raise RuntimeError(('Hook did not return', kind, hex(sim.registers[24])))
    bad = [('register', i, native.registers[i], sim.registers[i]) for i in CMP
           if native.registers[i] != sim.registers[i]]
    diffs = [i for i in range(0x4000, 65536) if i not in ignored and native.memory[i] != mem[i]]
    if diffs: bad.append(('RAM', len(diffs), diffs[:8]))
    pixels = [(native.memory[0x9500 + i // 8] >> (7 - i % 8)) & 1 for i in range(2048)]
    diffs = [i for i in range(2048) if pixels[i] != mem.private[i]]
    if diffs: bad.append(('pixels', len(diffs), diffs[:8]))
    if mem.nr != {7: clock, 0x50: 255, 0x52: 10}: bad.append(('NextREG', mem.nr))
    return bad, {'original_t': native.registers[25] / (1 << clock), 'hook_t': mem.elapsed,
                 'debt': word(mem.private, 0x1D44), 'target': word(mem.data, 0x3E10)}


def snapshot_simulator(snap):
    """Native machine from the converter's snapshot, without executing a loader."""
    regs = {n.upper(): getattr(snap, n) for n in ('a', 'f', 'bc', 'de', 'hl', 'ix', 'iy', 'sp', 'i', 'r', 'pc')}
    regs.update({'^' + n.upper(): getattr(snap, n + '_') for n in ('a', 'f', 'bc', 'de', 'hl')})
    return CSimulator(list(Z.rom48() + snap.banks[5] + snap.banks[2] + snap.banks[0]),
                      regs, {'iff': snap.iff1, 'im': snap.im})


def normalize_source(snap):
    """Finish only the snapshot's in-flight native chunk before installing hooks.

    The supported archive snapshot pauses at F56C with SP as a graphics pointer.
    Its remaining 3796 T-states have no I/O, interrupts or gameplay updates, and
    change only 33 scratch bytes. A fresh chunk boundary is safe for hook state.
    """
    if snap.pc != 0xF56C: return
    if snap.iff1 or snap.sp != 0: raise ValueError('Unexpected Movie source draw state')
    sim = snapshot_simulator(snap)
    before = list(sim.memory)
    for _ in range(2000):
        if sim.registers[24] == 0xF526: break
        sim.run()
    else: raise ValueError('Movie source prelude did not finish')
    changed = [i for i in range(65536) if before[i] != sim.memory[i]]
    if sim.registers[25] != 3796 or len(changed) != 33 or any(not 0x9500 <= i < 0x9600 for i in changed):
        raise ValueError('Movie source prelude differs from the verified native drawing')
    r = sim.registers
    for name, index in (('a', 0), ('f', 1), ('sp', 12), ('i', 14), ('r', 15),
                        ('a_', 16), ('f_', 17), ('pc', 24), ('iff1', 26), ('iff2', 26), ('im', 27)):
        setattr(snap, name, r[index])
    for name, index in (('bc', 2), ('de', 4), ('hl', 6), ('ix', 8), ('iy', 10),
                        ('bc_', 18), ('de_', 20), ('hl_', 22)):
        setattr(snap, name, r[index] * 256 + r[index + 1])
    for bank, at in ((5, 0x4000), (2, 0x8000), (0, 0xC000)):
        snap.banks[bank] = bytes(sim.memory[at:at + 16384])


class OriginalPatch:
    name = 'Movie original presentation'
    tail_addr = 0x5B00
    uses_printer_buffer = False
    setup_call = None
    stub_extra = b''
    hook_page_data = b''
    ram_slot1_after_alt = True

    def __init__(self):
        self.slot1 = (24, 0x3B00)
        self.altrom = (0x3900, 0x3B14)
        self.page = Z.rom48()[8192:]
        self.extra_banks = {13: bytes(8192) + Z.rom48()[:8192]}
        self.sites = []

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Movie requires the supported 48K release')
        normalize_source(snap)
        self.entry = snap.pc
        tail, _, restore, _ = Z.build_tail(snap, self.tail_addr, self.slot1, True, self.ram_slot1_after_alt)
        if len(tail) > 256:
            raise ValueError('Temporary startup tail exceeds its restored workspace')
        page = bytearray(self.page)
        page[0x1900:0x1A00] = snap.banks[5][0x1B00:0x1C00]
        low_rom = Z.nextreg(0x50, 27) if self.ram_slot1_after_alt else b''
        resume = bytes.fromhex('F321003911005B010001EDB0') + low_rom + tail[restore:]
        if 0x3A00 + len(resume) > 0x3B00:
            raise ValueError('Resume code overlaps the register block')
        page[0x1A00:0x1A00 + len(resume)] = resume
        self.page = bytes(page)
        self.extra_banks[12] = self.page + bytes(8192)
        snap.pc = 0x3A00


def build_original(source, destination):
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Unsupported Movie source')
    patch = OriginalPatch()
    Z.convert(str(source), str(destination), patch=patch, quiet=True)
    return patch


def speech_cache_bits(colours):
    return bytes(sum((128>>bit) for bit,v in enumerate(colours[(a-0x7000)*8:(a-0x7000+1)*8]) if v not in (0,255))
                 for a in range(0xD200,0xD300))


def initial_speech(colours, memory):
    """A mid-game replay snapshot may already contain text in the mutable bubble."""
    result=bytearray(colours)
    pixels,owners=decode_graphic(memory,0xD201)
    for row,own in zip(pixels,owners):
        for p,(address,bit) in zip(row,own):
            i=(address-0x7000)*8+bit
            if p==2: result[i]=result[i] if result[i] not in (0,255) else 1
            else: result[i]=0 if p==1 else 255
    return bytes(result)


class EnhancedPatch(OriginalPatch):
    """Companion dirty rectangles preserve original native clipping and depth order."""
    name = 'Movie Enhanced'
    ram_slot1_after_alt = True
    entries = tuple((pc, old, label) for pc, old, label, _ in CHUNKS) + (
        (0xF18A, '210095', 'h_clear'), (0xF700, 'ED4B3EF2', 'h_commit'),
        (0xF29B, 'ED7324F5', 'h_plot'), (0x7279, '7DC60700', 'h_speech_write'),
        (0xFFA6, '2B1B0618', 'h_clear_screen'))

    def __init__(self, assets, enabled=True, dma=True):
        super().__init__()
        self.enabled, self.dma_enabled = enabled, dma
        self.hooks = hooks = copy.deepcopy(load_profile()['hooks'])
        self.syms = {k: int(v, 16) for k, v in hooks['syms'].items()}
        self.altrom = (0x3900, 0x3E30)
        page = bytearray(self.page)
        blob = bytes.fromhex(hooks['resident']); page[0x1B20:0x1B20 + len(blob)] = blob
        page[0x1E00:0x2000] = bytes(512)
        self.page = bytes(page)
        private = bytearray(16384)
        private[8192:] = Z.rom48()[:8192]
        for key, at in (('kernel', 0x800), ('helper', 0xA00), ('bulk', 0x1000), ('library', 0x1800)):
            blob = bytes.fromhex(hooks[key]); private[at:at + len(blob)] = blob
        private[self.syms['bulk_policy']] = int(dma)
        self.extra_banks[13] = bytes(private)
        self.assets = Path(assets)
        self.colours = (self.assets / 'colours.bin').read_bytes()
        private[0x1E00:0x1F00] = speech_cache_bits(self.colours)
        self.extra_banks[13] = bytes(private)
        palette = (self.assets / 'palette.bin').read_bytes()
        if len(self.colours) != 229376 or len(palette) != 512:
            raise ValueError('Movie drawing asset length mismatch')
        for bank in range(14, 17): self.extra_banks[bank] = bytes([255]) * 16384
        for n in range(14): self.extra_banks[17 + n] = self.colours[n * 16384:(n + 1) * 16384]
        for n in range(14): self.extra_banks[31+n] = bytes(0 if v==255 else v for v in self.colours[n*16384:(n+1)*16384])
        values = [int.from_bytes(palette[i:i + 2], 'little') for i in range(0, 512, 2)]
        if values[255] != 0x1C7 or any(v > 511 or (v >> 1 == 0xE3 and i != 255)
                                      for i, v in enumerate(values)):
            raise ValueError('Movie palette transparency reservation')
        setup = bytearray()
        def nr(n, v): setup.extend((0xED, 0x91, n, v))
        for n, v in ((0x69, 0), (0x12, 14), (0x70, 0), (0x16, 0), (0x17, 0),
                     (0x15, 0), (0x1C, 1), (0x18, 0), (0x18, 255), (0x18, 0), (0x18, PLAY_HEIGHT - 1),
                     (0x43, 0x10), (0x40, 0)):
            nr(n, v)
        for value in values: nr(0x44, value >> 1); nr(0x44, value & 1)
        nr(0x14, 0xE3); nr(0x69, 0x80 if enabled else 0); setup.append(0xC9)
        self.setup_call, self.stub_extra = 0xD000, bytes(setup)

    def apply(self, snap):
        normalize_source(snap)
        self.colours=initial_speech(self.colours,list(Z.rom48()+snap.banks[5]+snap.banks[2]+snap.banks[0]))
        for n in range(14):
            data=self.colours[n*16384:(n+1)*16384]
            self.extra_banks[17+n]=data
            self.extra_banks[31+n]=bytes(0 if v==255 else v for v in data)
        self.sites = []
        if not self.enabled:
            super().apply(snap)
            return
        changes = []
        for pc, old, label in self.entries:
            at = self.syms[label]
            changes.append((pc, bytes.fromhex(old), bytes((0xC3, at & 255, at >> 8)) + bytes(len(bytes.fromhex(old)) - 3)))
        post = self.syms['post_chunk']
        for pc in (0xF3D2, 0xF5E3):
            old=bytes(snap.banks[0][pc&16383:(pc&16383)+3])
            permitted=(bytes.fromhex('C323F5'),) if pc==0xF3D2 else (bytes.fromhex('C323F5'),bytes.fromhex('C309F5'))
            if old not in permitted: raise ValueError('Unexpected native Movie chunk return')
            changes.append((pc, old, bytes((0xC3, post & 255, post >> 8))))
        for pc in (0xF379, 0xF4C5): changes.append((pc, bytes.fromhex('ED53E4F5'), bytes.fromhex('ED530C3E')))
        post = self.syms['post_commit']
        changes.append((0xF733, bytes.fromhex('E1010082'), bytes((0xC3, post & 255, post >> 8, 0))))
        post = self.syms['post_clear']
        changes.append((0xF1B1, bytes.fromhex('113B84'), bytes((0xC3, post & 255, post >> 8))))
        post = self.syms['h_plot_exit']
        old = bytes([snap.banks[0][0x3523 + i] for i in range(3)])
        if old[0] != 0x31: raise ValueError('Movie native plot exit differs')
        changes.append((0xF523, old, bytes((0xC3, post & 255, post >> 8))))
        for pc, old, new in changes:
            bank = 5 if pc < 0x8000 else 2 if pc < 0xC000 else 0
            at = pc & 16383
            actual = bytes(snap.banks[bank][at:at + len(old)])
            if actual != old: raise ValueError(f'Movie hook {pc:04X}: {actual.hex()} != {old.hex()}')
            data = bytearray(snap.banks[bank]); data[at:at + len(old)] = new; snap.banks[bank] = bytes(data)
            self.sites.append((pc, old, new))
        super().apply(snap)


def build(source, destination, assets=None, enhanced=True, loading=None, dma=True):
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Unsupported Movie source')
    patch = EnhancedPatch(assets, enabled=enhanced, dma=dma) if assets else OriginalPatch()
    Z.convert(str(source), str(destination), patch=patch, quiet=True)
    if loading is not None:
        scr = Path(loading).read_bytes()
        if len(scr) != 6912: raise ValueError('Movie loading screen must be 6912 bytes')
        data = Path(destination).read_bytes(); head = bytearray(data[:512])
        head[10], head[133] = 2, 50
        Path(destination).write_bytes(bytes(head) + scr + data[512:])
    return patch


def boot_problems(nex, source, patch):
    """All registers including R, all RAM, full hidden ROM and NEXLOAD recovery."""
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    from . import nextboot
    expected = Z.Z80Snapshot(str(source))
    normalize_source(expected)
    original = snapshot_simulator(expected)
    q = copy.deepcopy(patch)
    q.apply(expected)
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), q.entry, nexload=nexload, sysrom=nextboot.system_rom3()[0])
        bad.extend(('ROM', nexload, v) for v in st['bad'])
        for i in CMP:
            a, b = original.registers[i], st['R'][i]
            if (bool(a) != bool(b)) if i == 26 else (a != b):
                bad.append(('register', nexload, i, a, b))
        ram = expected.banks[5] + expected.banks[2] + expected.banks[0]
        diffs = [i for i in range(49152) if st['mem'][16384 + i] != ram[i]]
        if diffs:
            bad.append(('RAM', nexload, len(diffs), diffs[:8]))
        image = bytearray(nextboot.alt_image(q, nextboot.system_rom3()[0]))
        regs = Z.build_tail(expected, q.tail_addr, q.slot1, True, q.ram_slot1_after_alt)[3]
        if q.ram_slot1_after_alt: image[8192:] = q.page
        image[q.slot1[1]:q.slot1[1] + len(regs)] = regs
        diffs = [i for i in range(16384) if st['mem'][i] != image[i]]
        if diffs:
            bad.append(('hidden ROM', nexload, len(diffs), diffs[:8]))
    return bad


# Native-code pixel oracles and replay checks remain game-specific.
def graphics_spans(m, src):
    header, height = m[src - 1], m[src]
    width = (header & 7) + 1
    fmt = header >> 6
    if fmt == 3: return [(src - 1, 2 + width * height)]
    if fmt == 2: return [(src - 1, 2 + 2 * width * height)]
    if fmt == 1: return [(src - 1, 4 + width * height), (word(m, src + 1), width * height)]
    count = (((header + 8) >> 4) + 1) & 7
    spans = [(src - 1, 2 + count * 5)]
    for part in range(count):
        at = src + 1 + part * 5
        size = m[at] * width
        spans += [(word(m, at + 1), size), (word(m, at + 3), size)]
    return spans


def graphic_fingerprint(m, src):
    return hashlib.sha256(b''.join(bytes(m[a:a + n]) for a, n in graphics_spans(m, src))).hexdigest()[:16]


def census(recording, out, stop):
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    seen = {}
    calls = 0

    def hit(pc, sim):
        nonlocal calls
        r, m = sim.registers, sim.memory
        bc, hl = r[2] * 256 + r[3], r[6] * 256 + r[7]
        src = word(m, bc)
        header = m[src - 1]
        w, h = ((header & 7) + 1) * 8, m[src]
        key = f'{src:04x}_{w}_{h}'
        calls += 1
        counts[key] += 1
        if key not in seen:
            seen[key] = {'source': src, 'width': w, 'height': h, 'header': header,
                         'flags': [], 'rects': [], 'count': 0,
                         'first_registers': list(r), 'first_rect': list(m[hl:hl + 4])}
            (out / (key + '.ram')).write_bytes(bytes(m))
        v = seen[key]
        if r[14] not in v['flags']: v['flags'].append(r[14])
        rect = list(m[hl:hl + 4])
        if rect not in v['rects']: v['rects'].append(rect)

    frames, err = rzx.trace(str(recording), {0xF29B}, hit, stop=stop)
    for key, v in seen.items(): v['count'] = counts[key]
    result = {'recording': str(recording), 'md5': hashlib.md5(recording.read_bytes()).hexdigest(),
              'frames': frames, 'error': err, 'calls': calls, 'assets': seen}
    (out / 'census.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': frames, 'error': err, 'calls': calls, 'unique': len(seen),
                      'formats': dict(Counter(v['header'] >> 6 for v in seen.values()))}))


def render(mem, src, width, height, flags=0):
    """Use the original Z80 plotter, twice per strip, to recover ink and transparency.

    Each dirty rectangle is <= 8 scanlines, so its original 256-byte scratch page
    cannot overflow. Black/white backgrounds distinguish masked paper from holes.
    """
    result = [[0] * width for _ in range(height)]
    for bottom in range(0, height, 8):
        rows = min(8, height - bottom)
        pictures = []
        for fill in (0, 255):
            m = list(mem)
            m[0x9500:0x9600] = [fill] * 256
            m[0xF241:0xF245] = [0, width, 0, height]
            m[0xF245:0xF247] = [src & 255, src >> 8]
            m[0xF23D:0xF241] = [0, width, bottom, bottom + rows]
            m[0x93F0:0x93F2] = [0, 0x5B]
            sim = CSimulator(m, {'PC': 0xF29B, 'SP': 0x93F0, 'BC': 0xF245,
                                'HL': 0xF241, 'I': flags}, {'iff': 0},
                             {'int_active': 0})
            sim.run(stop=0x5B00)
            pictures.append(list(sim.memory[0x9500:0x9500 + rows * (width // 8)]))
        # 0 transparent, 1 opaque zero/paper, 2 opaque one/ink.
        for row in range(rows):
            for x in range(width):
                n, bit = row * (width // 8) + x // 8, 128 >> (x & 7)
                a, b = bool(pictures[0][n] & bit), bool(pictures[1][n] & bit)
                result[height - (bottom + rows) + row][x] = 2 if a else (0 if b else 1)
    return result


def atlas(out):
    from PIL import Image, ImageDraw
    data = json.loads((out / 'census.json').read_text())
    pixels = {}
    for key, entry in data['assets'].items():
        if not 0 < entry['height'] <= 192:
            print('UNSUPPORTED', key)
            continue
        mem = (out / (key + '.ram')).read_bytes()
        pixels[key] = render(mem, entry['source'], entry['width'], entry['height'])
    cells = sorted(pixels)
    cols, cw, ch, scale = 8, 76, 100, 3
    sheet = Image.new('RGB', (cols * cw, ((len(cells) + cols - 1) // cols) * ch), '#30343a')
    draw = ImageDraw.Draw(sheet)
    palette = [(82, 88, 96), (0, 0, 0), (235, 215, 125)]
    for n, key in enumerate(cells):
        p = pixels[key]
        im = Image.new('RGB', (len(p[0]), len(p)))
        im.putdata([palette[v] for row in p for v in row])
        x, y = n % cols * cw, n // cols * ch
        sheet.paste(im, (x + 2, y + 14))
        draw.text((x + 2, y + 1), key, fill='white')
    sheet.resize((sheet.width * scale, sheet.height * scale), Image.Resampling.NEAREST).save(out / 'MOVIE_NATIVE_ASSET_CENSUS.png')
    (out / 'native_pixels.json').write_text(json.dumps(pixels) + '\n')
    print('rendered', len(pixels), 'assets', sum(len(p) * len(p[0]) for p in pixels.values()), 'pixels')


def check(recording, out, stop):
    """Independent pixel-coordinate compositor versus every original native plot."""
    cache = json.loads((out / 'native_pixels.json').read_text())
    counts, failures, pending = Counter(), [], []
    failkeys = Counter()
    fingerprints = {}
    for key in cache:
        saved = out / (key + '.ram')
        if saved.exists(): fingerprints[key] = graphic_fingerprint(saved.read_bytes(), int(key[:4], 16))
    changes = Counter()

    def hit(pc, sim):
        r, m = sim.registers, sim.memory
        if pc == 0xF29B:
            bc, hl = r[2] * 256 + r[3], r[6] * 256 + r[7]
            src = word(m, bc)
            w, h = ((m[src - 1] & 7) + 1) * 8, m[src]
            key = f'{src:04x}_{w}_{h}'
            fingerprint = graphic_fingerprint(m, src)
            if key not in cache or fingerprint != fingerprints.get(key):
                cache[key] = render(bytes(m), src, w, h)
                fingerprints[key] = fingerprint
                changes[key] += 1
                if changes[key] == 1:
                    (out / (key + '_changed.ram')).write_bytes(bytes(m))
            pixels = cache[key]
            before = list(m[0x9500:0x9600])
            rect, clip = list(m[hl:hl + 4]), list(m[0xF23D:0xF241])
            x, _, y, _ = rect
            x0, x1, y0, y1 = clip
            stride = ((x1 - x0) & 255) // 8
            predicted = before[:]
            left = -8 if x0 == 248 else x0
            byte_left = max(left, x & 248)
            byte_right = min(x + w, x1 or 256)
            first_col = ((byte_left - x + 7) & 248)
            last_col = first_col + ((byte_right - byte_left) & 248)
            for row in range(h):
                sy = y + h - 1 - row
                if not y0 <= sy < y1: continue
                dy = y1 - 1 - sy
                for col in range(first_col, min(w, last_col)):
                    sx = x + col
                    dx = (sx - x0) & 255
                    v = pixels[row][w - 1 - col if r[14] & 1 else col]
                    if not v: continue
                    n, bit = dy * stride + dx // 8, 128 >> (dx & 7)
                    if n >= 256: n &= 255
                    if v == 2: predicted[n] |= bit
                    else: predicted[n] &= 255 ^ bit
            pending.append((key, rect, clip, r[14], predicted, before))
        elif pending:
            key, rect, clip, flags, predicted, before = pending.pop()
            actual = list(m[0x9500:0x9600])
            counts['plots'] += 1
            if actual != predicted:
                counts['mismatch'] += 1
                counts['format_' + str(m[int(key[:4], 16) - 1] >> 6)] += 1
                failkeys[key] += 1
                if failkeys[key] <= 2 and len(failures) < 24:
                    failures.append({'key': key, 'rect': rect, 'clip': clip, 'flags': flags,
                                     'diff': [(i, predicted[i], actual[i], before[i]) for i in range(256) if predicted[i] != actual[i]][:16]})
            else: counts['matched'] += 1
    frames, err = rzx.trace(str(recording), {0xF29B, 0xF526}, hit, stop=stop)
    result = {'frames': frames, 'error': err, 'counts': counts, 'changes': changes,
              'fail_keys': failkeys, 'examples': failures}
    (out / 'compositor-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


def backend_check(recording, out, stop):
    from nexclash.movie import REVERSE
    starts = {0xF567, 0xF582, 0xF5A0, 0xF5E6, 0xF39D, 0xF3AF, 0xF3C0, 0xF3D9}
    ends = {0xF580, 0xF59B, 0xF5E1, 0xF3D2}
    counts, examples, pending, descriptors = Counter(), [], [], {}
    cases = {}

    def hit(pc, sim):
        r, m = sim.registers, sim.memory
        if pc not in starts:
            if pending:
                start, d, prediction, t0, fixture = pending.pop()
                actual = list(m[0x9500:0x9600])
                counts[f'{start:04x}'] += 1
                if fixture:
                    fixture['expected'] = actual
                    fixture['original_t'] = r[25] - t0
                if prediction != actual:
                    counts['mismatch'] += 1
                    if len(examples) < 12:
                        examples.append({'pc': f'{start:04x}', 'descriptor': d,
                          'diff': [(i, prediction[i], actual[i]) for i in range(256) if prediction[i] != actual[i]][:10]})
            return
        main_hl, alt_hl = r[6] * 256 + r[7], r[22] * 256 + r[23]
        if pending:
            return
        main_bc = r[2] * 256 + r[3]
        if pc in (0xF567, 0xF582):
            mirror = pc == 0xF582
            d = dict(bitmap=main_hl if mirror else alt_hl, mask=alt_hl if mirror else main_hl,
                     width=r[19], height=r[2], destination=r[21], phase=0, mirror=mirror,
                     source_stride=((r[12] + (-r[19] if mirror else r[19])) & 65535),
                     destination_stride=r[19] + r[3])
        elif pc in (0xF5A0, 0xF5E6):
            mirror = pc == 0xF5E6
            width = r[3] if mirror else r[19]
            skip = word(m, 0xF618 if mirror else 0xF5D2)
            d = dict(bitmap=main_hl if mirror else main_bc, mask=alt_hl,
                     width=width, height=r[0], destination=r[12] & 255,
                     phase=m[0xF409], mirror=mirror,
                     source_stride=(skip + (-width if mirror else width)) & 65535,
                     destination_stride=width + word(m, 0xF61C if mirror else 0xF5D8))
        else:
            mirror = pc in (0xF3C0, 0xF3D9)
            width = 1 if pc in (0xF3AF, 0xF3D9) else 2
            d = dict(bitmap=r[12] + (1 if width == 1 or mirror else 0), mask=None,
                     width=width, height=r[18] if pc == 0xF3C0 else r[2],
                     destination=main_hl & 255, phase=0, mirror=mirror, source_stride=2,
                     destination_stride=width + (r[19] if pc == 0xF3C0 else r[3]))
        descriptors.setdefault(f'{pc:04x}', dict(descriptor=d, registers=list(r)))
        prediction = list(m[0x9500:0x9600])
        for y in range(d['height']):
            for col in range(d['width']):
                delta = (y * d['source_stride'] + (-col if d['mirror'] else col)) & 65535
                bits = m[(d['bitmap'] + delta) & 65535]
                mask = m[(d['mask'] + delta) & 65535] if d['mask'] is not None else 0
                if d['mirror']: bits = REVERSE[bits]
                elif d['mask'] is not None: mask = REVERSE[mask]
                for bit in range(8):
                    target = ((d['destination'] + y * d['destination_stride'] + col) * 8 + d['phase'] + bit) & 2047
                    index, b = target // 8, 128 >> (target & 7)
                    if not (mask & (128 >> bit)): prediction[index] &= b ^ 255
                    if bits & (128 >> bit): prediction[index] |= b
        case_key = f'{pc:04x}_{d["phase"]}_{d["width"]}_{min(d["height"], 9)}'
        fixture = None
        if case_key not in cases:
            fixture = {'descriptor': d, 'ram': case_key + '.ram', 'pc': pc,
                       'registers': list(r)}
            native = CSimulator(list(m))
            for i, value in enumerate(r): native.registers[i] = value
            native.registers[25] = 0
            native.run(stop=0xF3D2 if pc in (0xF39D, 0xF3AF, 0xF3C0, 0xF3D9) else 0xF5E3)
            prefix = {0xF39D: 16, 0xF3AF: 25, 0xF3C0: 17, 0xF3D9: 17}.get(pc, 10)
            fixture['native_total_t'] = native.registers[25] + prefix + 10
            fixture['native_body_m1_mod128'] = (native.registers[15] - r[15]) & 127
            cases[case_key] = fixture
            (out / (case_key + '.ram')).write_bytes(bytes(m))
        pending.append((pc, d, prediction, r[25], fixture))
    frames, err = rzx.trace(str(recording), starts | ends, hit, stop=stop)
    result = dict(frames=frames, error=err, counts=dict(counts), examples=examples, first=descriptors)
    (out / 'backend-check.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'kernel-cases.json').write_text(json.dumps(cases, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'first'}))


def screen_check(recording, out, stop):
    """Native dirty-screen commit versus the assembled Layer 2 companion copy."""
    from .dizzy6 import _rw_simulator
    from . import simpool, z80n
    cases, failures, counts = {}, [], Counter()
    syms = {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}
    def pixels(m):
        return [(m[0x4000 + ((y & 192) << 5) + ((y & 7) << 8) + ((y & 56) << 2) + x // 8]
                 >> (7 - (x & 7))) & 1 for y in range(192) for x in range(256)]
    def hit(pc, game):
        counts[f'{pc:04x}'] += 1
        m, r = list(game.memory), list(game.registers)
        key = (pc, m[0xF70D], m[0xF713], m[0xF716], m[0xF71A], m[0xF23E], m[0xF23F], m[0xF240])
        if key in cases: return
        cases[key] = 1
        mem = DrawingMemory(m)
        mem.private[:2048] = [(m[0x9500 + i // 8] >> (7 - i % 8)) & 1 for i in range(2048)]
        before = pixels(m)
        for p in range(28, 34): mem.pages[p][:] = before[(p - 28) * 8192:(p - 27) * 8192]
        label = 'h_clear' if pc == 0xF18A else 'h_commit'
        at = syms[label]
        mem.data[pc:pc + 3] = [0xC3, at & 255, at >> 8]
        post = syms['post_commit']
        mem.data[0xF733:0xF737] = [0xC3, post & 255, post >> 8, 0]
        post = syms['post_clear']
        mem.data[0xF1B1:0xF1B4] = [0xC3, post & 255, post >> 8]
        sim = simpool.machine(_rw_simulator(), mem, slot='movie-screen-hook')
        sim.low_writes = True; sim.registers[:] = r; sim.set_tracer(mem); z80n.install(sim, mem.nextreg)
        end = 0xF1B4 if pc == 0xF18A else 0xF737
        steps = 0
        while sim.registers[24] != end:
            t, speed = sim.registers[25], mem.nr[7]
            sim.opcodes[mem[sim.registers[24]]]()
            mem.elapsed += (sim.registers[25] - t) / (1 << speed)
            steps += 1
            if steps > 150000: raise RuntimeError(('Screen hook did not return', hex(sim.registers[24]), key))
        native = simpool.machine(CSimulator, m, slot='movie-screen-native')
        for i, value in enumerate(r): native.registers[i] = value
        native.run(stop=end)
        bad = [('register', i, native.registers[i], sim.registers[i]) for i in CMP if native.registers[i] != sim.registers[i]]
        if pc == 0xF18A:
            size = ((m[0xF70D] >> 1) + 1) * 16
            if mem.private[:size] != [255] * size: bad.append(('clear pixels', size))
        else:
            wanted = pixels(native.memory)
            actual = sum((mem.pages[p] for p in range(28, 34)), [])
            diffs = [i for i in range(49152) if wanted[i] != actual[i]]
            if diffs: bad.append(('screen pixels', len(diffs), diffs[:12]))
        if mem.nr != {7: 0, 0x50: 255, 0x52: 10}: bad.append(('NextREG', mem.nr))
        if bad and len(failures) < 12: failures.append((key, bad))
    frames, error = rzx.trace(str(recording), {0xF18A, 0xF700}, hit, stop=stop)
    result = dict(frames=frames, error=error, counts=dict(counts), cases=len(cases), failures=failures)
    (out / 'screen-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    if failures or error: raise SystemExit(1)


def verify_renderer(recording, assets, out=None, stop=None, patch=None, collect=0, progress=None):
    """Replay-fed complete native plot calls, preserving companion state between calls."""
    from .dizzy6 import _rw_simulator
    from . import simpool, z80n
    if out is not None:
        out = Path(out); out.mkdir(parents=True, exist_ok=True)
    patch = patch or EnhancedPatch(assets)
    state, pending, counts, failures, last_plot = [], [], Counter(), [], []
    states, collecting, seen, collected_keys = [], [], Counter(), set()
    hook_pcs = {pc for pc, _, _ in patch.entries}
    replaced = set()
    def refresh(mem, m):
        mem.data[0x4000:] = m[0x4000:]
        changes = []
        for pc, old, label in patch.entries:
            at = patch.syms[label]
            changes.append((pc, [0xC3, at & 255, at >> 8] + [0] * (len(bytes.fromhex(old)) - 3)))
        for pc in (0xF3D2, 0xF5E3):
            at = patch.syms['post_chunk']; changes.append((pc, [0xC3, at & 255, at >> 8]))
        for pc in (0xF379, 0xF4C5): changes.append((pc, list(bytes.fromhex('ED530C3E'))))
        at = patch.syms['post_commit']
        changes.append((0xF733, [0xC3, at & 255, at >> 8, 0]))
        at = patch.syms['post_clear']
        changes.append((0xF1B1, [0xC3, at & 255, at >> 8]))
        at = patch.syms['h_plot_exit']
        changes.append((0xF523, [0xC3, at & 255, at >> 8]))
        for pc, new in changes:
            mem.data[pc:pc + len(new)] = new; replaced.update(range(pc, pc + len(new)))
    def hit(pc, original):
        r, m = original.registers, original.memory
        if failures: return
        if pc in (0xF526, 0xF737, 0xF1B4, 0x727D, 0xFFAD):
            if not pending: return
            mem, sim = state[0]
            pending.pop()
            if collecting:
                entry, before, registers = collecting.pop()
                states.append(dict(pc=entry, end=pc, memory=before, registers=registers,
                                   expected=copy.deepcopy(mem), expected_registers=list(r)))
            bad = [('register', i, r[i], sim.registers[i]) for i in CMP if r[i] != sim.registers[i]]
            wanted, actual = bytes(m[0x4000:]), bytearray(mem.data[0x4000:])
            for i in replaced: actual[i-0x4000]=m[i]
            diff = [] if wanted == actual else [i for i in range(0x4000,65536) if i not in replaced and m[i] != mem[i]]
            if diff: bad.append(('RAM', len(diff), diff[:8]))
            diff = [i for i in range((m[0xF70D] + 1) * 8) if ((m[0x9500 + i // 8] >> (7 - i % 8)) & 1) != int(mem.private[i] not in (0, 255))] if pc == 0xF526 else []
            if diff: bad.append(('scratch pixels', len(diff), diff[:8]))
            if bad:
                failures.append((counts['plots'], bad))
                if last_plot and out is not None:
                    (out/'failure-entry.ram').write_bytes(last_plot[0][0])
                    (out/'failure-entry.json').write_text(json.dumps({'registers':last_plot[0][1],'frame':original.tracer.frame_index,'bad':bad},indent=2)+'\n')
            if pc != 0xF737: return
        if pc == 0xF737:
            if not state: return
            mem, _ = state[0]
            diff = []
            for y in range(PLAY_HEIGHT):
                base = 0x4000 + ((y & 192) << 5) + ((y & 7) << 8) + ((y & 56) << 2)
                page = mem.pages[28 + y // 32]; offset = (y & 31) * 256
                for x in range(256):
                    value = page[offset + x]
                    if value != 255 and int(value != 0) != ((m[base + x // 8] >> (7 - x % 8)) & 1):
                        diff.append((x, y, value))
            if diff:
                failures.append(('screen', counts['commit'], len(diff), diff[:8]))
                if out is not None:
                    (out/'failure-original.ram').write_bytes(bytes(m))
                    (out/'failure-layer2.bin').write_bytes(bytes(sum((mem.pages[p] for p in range(28,34)),[])))
                    (out/'failure-state.json').write_text(json.dumps({'frame':original.tracer.frame_index,'registers':list(r),'rect':list(m[0xF23D:0xF241]),'pixels':diff},indent=2)+'\n')
            return
        if not state:
            mem = DrawingMemory(list(m), patch.colours, hooks=patch.hooks)
            mem.private[:2048] = [(m[0x9500+i//8] >> (7-i%8)) & 1 for i in range(2048)]
            mem.private[patch.syms['bulk_policy']] = int(patch.dma_enabled)
            sim = simpool.machine(_rw_simulator(), mem, slot='movie-renderer')
            sim.low_writes = True; sim.set_tracer(mem); z80n.install(sim, mem.nextreg)
            state.append((mem, sim))
        mem, sim = state[0]
        if pc == 0xF29B: last_plot[:] = [(bytes(m),list(r))]
        refresh(mem, list(m)); sim.registers[:] = list(r)
        unit_key = (pc, word(m, r[2]*256+r[3])) if pc == 0xF29B else (pc,)
        if collect and unit_key not in collected_keys and seen[pc] < (collect if pc == 0xF29B else 1):
            collecting.append((pc, copy.deepcopy(mem), list(r))); seen[pc] += 1
            collected_keys.add(unit_key)
        end = {0xF18A: 0xF1B4, 0xF700: 0xF737, 0xF29B: 0xF526, 0x7279: 0x727D, 0xFFA6:0xFFAD}[pc]
        counts[{0xF18A: 'clear', 0xF700: 'commit', 0xF29B: 'plots', 0x7279: 'text_write',0xFFA6:'screen_erase'}[pc]] += 1
        if pc == 0xF29B and counts['plots'] % 10000 == 0:
            if progress: progress(dict(frame=original.tracer.frame_index, plots_checked=counts['plots']))
            elif out is not None: print(json.dumps({'frame':original.tracer.frame_index,'plots_checked':counts['plots']}),flush=True)
        steps = 0
        while sim.registers[24] != end or (pc==0xFFA6 and sim.registers[12]!=r[12]):
            here = sim.registers[24]
            if here in hook_pcs: counts[f'hook_{here:04x}'] += 1
            t, speed = sim.registers[25], mem.nr[7]
            sim.opcodes[mem[here]]()
            mem.elapsed += (sim.registers[25] - t) / (1 << speed)
            steps += 1
            if steps > 1000000: raise RuntimeError(('Plot hook did not return', hex(here), counts))
        pending.append(1)
        if mem.nr != {7: 0, 0x50: 255, 0x52: 10}: failures.append(('NextREG', mem.nr))
    frames, error = rzx.trace(str(recording), {0xF18A, 0xF1B4, 0xF700, 0xF737, 0xF29B, 0xF526, 0x7279, 0x727D,0xFFA6,0xFFAD}, hit, stop=stop)
    result = dict(frames=frames, error=error, counts=dict(counts), failures=failures)
    if out is not None:
        (out / 'renderer-check.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        if failures or error: raise SystemExit(1)
    return result, states


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    result, states = verify_renderer(rzx_path, patch.assets, stop=stop, patch=patch,
                                    collect=collect, progress=progress)
    counts = Counter(result['counts']); counts['frames'] = result['frames']
    if result['error']: counts['replay!'] += 1
    if result['failures']: counts['differential!'] += len(result['failures'])
    examples = {'replay': result['error'], 'differential': result['failures']}
    return (counts, examples, states) if collect else (counts, examples)


def state_trial(patch, state, clock=0, iff=0, core=0x33, hardware_im2=0, dma=True, raw=False):
    """Replay a captured complete hook with the supplied build's own code/tables."""
    from .dizzy6 import _rw_simulator
    from . import simpool, z80n
    mem = copy.deepcopy(state['memory'])
    # Restore run-time data first, then the tested build, never the good tables.
    for key, at in (('kernel',0x800),('helper',0xA00),('bulk',0x1000),('library',0x1800)):
        code = bytes.fromhex(patch.hooks[key]); mem.private[at:at+len(code)] = code
    code = bytes.fromhex(patch.hooks['resident']); mem.data[0x3B20:0x3B20+len(code)] = code
    mem.private[patch.syms['bulk_ready']] = 0
    mem.private[patch.syms['bulk_policy']] = int(dma)
    mem.core, mem.hardware_im2 = core, hardware_im2
    mem.nr.update({7:clock,0x50:255,0x52:10})
    sim = simpool.machine(_rw_simulator(), mem, slot='movie-state-test')
    sim.low_writes=True; sim.set_tracer(mem); z80n.install(sim,mem.nextreg)
    sim.registers[:] = state['registers']; sim.registers[26] = iff
    for step in range(1000000):
        if sim.registers[24] == state['end'] and (state['pc']!=0xFFA6 or sim.registers[12]==state['registers'][12]): break
        t,speed=sim.registers[25],mem.nr[7]
        sim.opcodes[mem[sim.registers[24]]]()
        mem.elapsed += (sim.registers[25]-t)/(1<<speed)
    else: return ['did not return']
    if raw: return mem, list(sim.registers)
    wanted=list(state['expected_registers']); wanted[26]=iff
    bad=[('register',i,wanted[i],sim.registers[i]) for i in CMP
         if i==26 and bool(wanted[i])!=bool(sim.registers[i])]
    bad += [('register',i,wanted[i],sim.registers[i]) for i in CMP if i!=26 and wanted[i]!=sim.registers[i]]
    expected=state['expected']
    if mem.data[0x4000:] != expected.data[0x4000:]: bad.append('game RAM')
    if mem.private[:2048] != expected.private[:2048]: bad.append('scratch colour pixels')
    if any(mem.pages[p]!=expected.pages[p] for p in range(28,34)): bad.append('screen colour pixels')
    if mem.nr!={7:clock,0x50:255,0x52:10}: bad.append(('NextREG',mem.nr))
    return bad


def unit_tests(patch, states):
    counts=Counter()
    for state in states:
        for speed in range(4):
            for iff in (0,1):
                bad=state_trial(patch,state,speed,iff)
                counts['speed/IFF cases']+=1
                if bad: counts['speed/IFF!']+=1
        if state['pc'] in (0xF700,0xFFA6):
            for core,im2,dma in ((0x32,0,True),(0x33,1,True),(0x33,0,False),(0x33,0,True)):
                bad=state_trial(patch,state,core=core,hardware_im2=im2,dma=dma)
                counts['DMA/fallback cases']+=1
                if bad: counts['DMA/fallback!']+=1
    changes=(('position','helper','22041d','22051d'),
             ('transparency','kernel','3eff','3efe'),
             ('R','helper','3ef2cd','3ef3cd'),
             ('speed','resident','ed9207','ed9206'))
    for label,block,old,new in changes:
        broken=copy.copy(patch);broken.hooks=copy.deepcopy(patch.hooks)
        raw=bytes.fromhex(broken.hooks[block]);before=bytes.fromhex(old)
        if before not in raw: raise AssertionError('Missing negative-control site: '+label)
        broken.hooks[block]=raw.replace(before,bytes.fromhex(new),-1 if label=='transparency' else 1).hex()
        controls=states
        if label=='transparency':
            # First encounters can have empty surroundings. Give the captured
            # geometry a coloured background so ignored transparency is visible.
            controls=[]
            for s in states:
                if s['pc']!=0xF29B: continue
                one=dict(s);one['memory']=copy.deepcopy(s['memory'])
                one['memory'].private[:2048]=[19]*2048
                one['memory'].data[0x9500:0x9600]=[255]*256
                one['expected'],one['expected_registers']=state_trial(patch,one,clock=1,raw=True)
                controls.append(one)
        detected=any(state_trial(broken,s,clock=1) for s in controls)
        counts[label+' negative detected' if detected else label+' negative missed!']+=1
    return counts


def auto(a, z80, name, out, say):
    """Rebuild from the owner's source and external editable colour assets."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    beside=Path(z80).resolve().parent
    default_art=beside/'movie_art' if (beside/'movie_art').is_dir() else beside
    assets=Path(os.environ.get('NEXCLASH_MOVIE_ART',str(default_art)))
    if not (assets/'colours.bin').is_file():
        raise ValueError('Movie Enhanced requires the local painting assets; set NEXCLASH_MOVIE_ART')
    loading=Path(z80).resolve().parent/'movie-loading.scr'
    if not loading.is_file() or hashlib.sha256(loading.read_bytes()).hexdigest()!=LOADING_SHA256:
        raise ValueError('The verified original movie-loading.scr is required beside the snapshot')
    if not getattr(a,'publisher',None): a.publisher='Imagine, 1986'
    if not getattr(a,'fix_label',None): a.fix_label='Presentation'
    trainer_path=out/(name+'_verified.pok')
    trainer_path.write_text(''.join('N'+title+'\n'+''.join(
        ('Z' if i==len(items)-1 else 'M')+f' 8 {address} {value} {old}\n'
        for i,(address,old,value) in enumerate(items)) for title,items in TRAINERS.items())+'Y\n')
    supplied=getattr(a,'pok',None)
    if supplied and Path(supplied).read_bytes()!=trainer_path.read_bytes():
        if hashlib.md5(Path(supplied).read_bytes()).hexdigest()!='7955ff07ce077ac391c4c7ab3bfc3c58':
            raise ValueError('Unverified Movie trainers; use the archive POK or movie_verified.pok')
        say('Trainers  : archive shooting/final-item cheats translated to verified release sites')
    a.pok=str(trainer_path)
    say('Game      : '+name)
    say('Engine    : movie; original monochrome default, optional ordered Layer 2 colours')
    ok=True;painted=None
    for label,enabled,suffix in (('Plain',None,''),('Sprites',False,'_sprites'),('Enhanced',True,'_enhanced')):
        path=out/(name+suffix+'.nex')
        p=build(z80,path,assets if enabled is not None else None,enhanced=bool(enabled))
        bad=boot_problems(path,z80,p);ok &= not bad
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK' if not bad else bad))
        if enabled is not None:
            loaded=out/(name+suffix+'_loading.nex')
            build(z80,loaded,assets,enhanced=enabled,loading=loading)
            bad=boot_problems(loaded,z80,p);ok &= not bad
            if bad:say('Loading   : '+str(bad))
        if enabled:painted=p
    for recording in list(getattr(a,'rzx',None) or []):
        counts,examples,states=verify(painted,recording,stop=getattr(a,'quick',None),collect=16)
        units=unit_tests(painted,states)
        bad={k:v for k,v in (counts+units).items() if k.endswith('!')}
        ok &= not bad
        say('Verify    : %s %d frames; %d complete native plots, all registers/R/RAM/pixels: %s'%(
            Path(recording).name,counts['frames'],counts['plots'],'IDENTICAL' if not bad else bad))
        say('Unit      : '+str(dict(units)))
        (out/(name+'_'+Path(recording).stem+'_verification.json')).write_text(json.dumps(dict(
            recording=Path(recording).name,counts=dict(counts),examples=examples,units=dict(units)),indent=2)+'\n')
    recordings=list(getattr(a,'rzx',None) or [])
    if recordings:
        from . import nextboot,runchecks
        from .machine import Machine
        runtime=Z.Z80Snapshot(str(z80));normalize_source(runtime)
        machine=Machine(str(z80));machine.sim=snapshot_simulator(runtime);machine.sim.set_tracer(machine)
        runtime_file=out/(name+'_runtime.z80');runtime_file.write_bytes(machine.z80_bytes())
        nexes=sorted(str(p) for p in out.glob('*.nex'))
        # The exact boot proof above establishes F526, including R and all RAM.
        # The source snapshot itself is 3796 native T-states earlier, inside a
        # draw. Generic boot-to-source-PC would enter patched drawing mid-hook.
        report=nextboot.rom_paths(nexes,recordings,stop=getattr(a,'quick',None),
                                 z80=str(runtime_file),start_pc=runtime.pc)
        status,why,coverage=runchecks.rom_paths(report,recordings,nexes)
        for result in report.values():
            for line in result[1]:say('ROM paths : '+line)
        runchecks.add(runchecks.RUN,'rom_paths',status,why,coverage=coverage)
        ok &= status=='pass'
    sheet=out/(name+'_PAINTING_SPRITES.png')
    if not sheet.exists():painting_sheet(z80,assets,sheet)
    say('Result    : '+('PASSED' if ok else 'FAILED'))
    return bool(ok)


def analyse_main():

    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['census', 'atlas', 'check', 'backend-check', 'screen-check'])
    p.add_argument('--recording', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--stop', type=int)
    a = p.parse_args()
    if a.mode != 'atlas' and a.recording is None:
        p.error('--recording is required for replay modes')
    if a.mode == 'census': census(a.recording, a.out, a.stop)
    elif a.mode == 'atlas': atlas(a.out)
    elif a.mode == 'check': check(a.recording, a.out, a.stop)
    elif a.mode == 'backend-check': backend_check(a.recording, a.out, a.stop)
    else: screen_check(a.recording, a.out, a.stop)


if __name__ == '__main__':
    analyse_main()
