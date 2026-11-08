"""Alien 8 (Ultimate, 1985; 48K): the Filmation renderer on Next hardware sprites over a Layer 2 room, in the
original look (default) or with the owner's painted figures and a floor (Enhanced, off by default).
games/alien_8.md has the design and results.

Everything the build needs is here or in the user's own copy of the game: the original graphics are decoded from the
snapshot's graphic table (docs/profiles/alien_8.json), and docs/profiles/alien_8_colours.json holds the owner's
painting of the original figures and the floor. With the original tape beside the snapshot (same name, .tap) the
original loading screen is added to the .nex, as in the published release.

    python -m nexclash.alien_8 SNAPSHOT OUT.nex [--enhanced]

`nexclash.py auto` (nexclash/engines.py: is_alien_8) builds GAME.nex (default) and GAME_enhanced.nex and boots both.
"""
import hashlib, json, sys
from collections import deque, Counter
from pathlib import Path
from PIL import Image, ImageDraw
from .build import rom48
from .machine import Machine
from . import z80tonex as Z
from .hooklib import CMP_R as CMP     # the pilot's replay compared every register, R included

ROOT = Path(__file__).resolve().parents[1]
COLOURS = ROOT / 'docs/profiles/alien_8_colours.json'
TAPE_SHA256 = 'ab08ab65d1e086aa34ab8cce70e7499f234f1033084304ccea322028790e0c2f'
TAPE_SCREEN = 479                     # the 6,912-byte loading screen's offset in that tape
SOURCE0 = 58
FLOORS = (82, 88, 46)
PAL = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
       (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
SITES = {0xD02A: ('dd7e1a', 's_plot', 0xCD), 0xCE7B: ('010018', 's_clear', 0xCD),
         0xCF4F: ('cd83bf', 's_rect', 0xCD), 0xCE85: ('2100d2', 's_full', 0xCD),
         0xCF82: ('dde1c9', 's_part', 0xC3),
         0xA6F1: ('cd1cc7', 's_window_in', 0xCD), 0xA6F7: ('3a245b', 's_window_out', 0xCD), 0xA70B: ('210003', 's_delay', 0xCD),
         0xA68E: ('dd21885b', 's_actor', 0xC3), 0xA647: ('21085b', 's_cancel', 0xCD),
         0xB761: ('cd05af', 's_gameover', 0xCD)}
BACKUP = 0x3900     # self-erasing start-up tail: its backup and an exact register restore in unused ROM space
ENTRY = 0x3940


def load_profile():
    return json.loads((ROOT / 'docs/profiles/alien_8.json').read_text())


def is_alien_8(snap):
    """48K snapshot with Alien 8's actor-update entry at the profile's signature address."""
    ram = bytes(snap.ram(-1))
    if len(ram) != 49152:
        return False
    s = load_profile()['signature']
    want = bytes.fromhex(s['hex'])
    return ram[s['addr'] - 16384:s['addr'] - 16384 + len(want)] == want


def original_graphics(mem):
    """The game's masked graphic table -> (records, {id: RGBA image}): ink (232,232,232), mask-only black, clear.
    Rows run as the source stores them, bottom row first; the header's flip bits are applied at run time."""
    table = int(load_profile()['graphics_table'], 16)
    records, images = [], {}
    for i in range(256):
        a = mem[table + i * 2] | mem[table + i * 2 + 1] << 8
        if not 16384 <= a < 65535: continue
        w, h = mem[a] & 15, mem[a + 1]
        if not 0 < w <= 8 or not 0 < h <= 100 or a + 2 + w * h * 2 > 65536: continue
        im = Image.new('RGBA', (w * 8, h)); px = im.load()
        for y in range(h):
            for x in range(w * 8):
                b = a + 2 + (y * w + x // 8) * 2; bit = 0x80 >> (x & 7)
                if (mem[b] | mem[b + 1]) & bit: px[x, h - 1 - y] = (232, 232, 232, 255) if mem[b + 1] & bit else (0, 0, 0, 255)
        images[i] = im
        records.append(dict(id=i, addr=a, width=w * 8, height=h, flags=mem[a] & 0xf0))
    assert len(records) == 130, ('not the Alien 8 graphic table', len(records))
    return records, images


def load_colours():
    """docs/profiles/alien_8_colours.json -> ({id: RGBA image}, floor RGBA image)."""
    c = json.loads(COLOURS.read_text())
    pal = [tuple(p) for p in c['palette']]
    def image(rows):
        im = Image.new('RGBA', (len(rows[0]), len(rows))); px = im.load()
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != '.': px[x, y] = pal[int(ch, 36)] + (255,)
        return im
    return {int(k, 16): image(v) for k, v in c['figures'].items()}, image(c['floor'])


def tight(col, original):
    """Accepted player rule: remove only exterior mask-only black."""
    w, h = col.size; seen = set(); q = deque()

    def visit(x, y):
        if 0 <= x < w and 0 <= y < h and (x, y) not in seen and original.getpixel((x, y))[0] == 0 and (col.getpixel((x, y))[:3] == (0, 0, 0) or col.getpixel((x, y))[3] == 0):
            seen.add((x, y)); q.append((x, y))
    for x in range(w): visit(x, 0); visit(x, h - 1)
    for y in range(h): visit(0, y); visit(w - 1, y)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)): visit(x + dx, y + dy)
    out = col.copy()
    for p in seen: out.putpixel(p, (0, 0, 0, 0))
    return out


def compile_assets(game, enhanced=True):
    """The renderer's pages from the game snapshot and the colour profile: {page: 8192 bytes}, report."""
    mem = Machine(str(game)).sim.memory
    records, originals = original_graphics(mem)
    painted, floor = load_colours()
    for gid, im in painted.items(): assert im.size == originals[gid].size, hex(gid)
    accepted_painted = painted
    if not enhanced: painted = {}; floor = Image.new('RGBA', (256, 192))
    # Fixed global indices give every saved flat colour an exact RGB333 entry.
    paint_rgb = sorted({p[:3] for im in accepted_painted.values() for p in im.getdata() if p[3]})
    assert paint_rgb[0] == (0, 0, 0) and len(paint_rgb) <= 15
    rgb = paint_rgb + sorted({p[:3] for p in floor.getdata() if p[3]} - set(paint_rgb))
    original_ink = []
    for c in PAL:
        if c not in rgb: rgb.append(c)
        original_ink.append(rgb.index(c))
    assert len(rgb) < 64
    lookup = {p: i for i, p in enumerate(rgb)}
    palettes = bytearray(512)
    for i, (r, g, b) in enumerate(rgb):
        rr, gg, bb = (round(v * 7 / 255) for v in (r, g, b))
        palettes[i * 2] = rr << 5 | gg << 2 | bb >> 1
        palettes[i * 2 + 1] = bb & 1
    palettes[256:508] = palettes[:252]          # static colours use bit 7, with identical physical RGB entries
    ula333 = (0, 5, 320, 325, 40, 45, 360, 365, 0, 7, 448, 463, 56, 63, 504, 511)
    for i, value in enumerate(ula333): palettes[(64 + i) * 2:(65 + i) * 2] = bytes((value >> 1, value & 1))
    for i in (126, 254, 255): palettes[i * 2:i * 2 + 2] = bytes((0xe3, 0))
    pages = {22: bytearray(8192), 23: bytearray(8192), 24: bytearray(8192), 25: bytearray(8192), 27: bytearray([255] * 8192)}
    directory = pages[24]; directory[6144:6160] = bytes(original_ink)
    directory[6160:6163] = bytes(FLOORS)
    pages[25][:512] = palettes
    static = {int(x, 16) for x in load_profile()['static_scenery_ids']}
    directory[6656:6912] = bytes(int(i in static) for i in range(256))
    pages[25][4096:4608] = palettes
    for p in range(28, 58): pages[p] = bytearray([255] * 8192)
    # Exact source image and orientation packing; aliases share one copy.
    p, off = SOURCE0, 0; dedup = {}; detail = []
    for r in records:
        gid = r['id']; original = originals[gid]
        im = painted.get(gid, original)
        if enhanced and (gid in range(0x14, 0x18) or gid in range(0x24, 0x28)): im = tight(im, original)
        for orient in range(4):
            delta = r['flags'] ^ (orient << 6)
            pic = im
            if delta & 64: pic = pic.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if delta & 128: pic = pic.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            pic = pic.transpose(Image.Transpose.FLIP_TOP_BOTTOM)    # source rows ascend from the buffer's bottom edge
            raw = bytes(255 if not px[3] else (lookup[px[:3]] if gid in painted else 126 if px[0] else 0) | (128 if gid in static else 0) for px in pic.getdata())
            encoded = bytearray()
            for y in range(r['height']):
                row = raw[y * r['width']:(y + 1) * r['width']]; runs = []; x = 0; last = 0
                while x < len(row):
                    if row[x] == 255: x += 1; continue
                    start = x
                    while x < len(row) and row[x] != 255: x += 1
                    runs.append(bytes((start - last, x - start)) + row[start:x]); last = x
                encoded += bytes((len(runs),)) + b''.join(runs)
            raw = bytes(encoded)
            if raw not in dedup:
                if off + len(raw) > 8192: p += 1; off = 0
                assert p < 81, (p, gid, 'source pages reach auxiliary code')
                pages.setdefault(p, bytearray(8192))[off:off + len(raw)] = raw
                dedup[raw] = (p, off); off += len(raw)
            pg, at = dedup[raw]
            start = (gid * 4 + orient) * 6
            directory[start:start + 6] = bytes((pg, at & 255, at >> 8, r['width'], r['height'], gid in painted))
        detail.append(dict(id=gid, painted=gid in painted, width=r['width'], height=r['height']))
    rooms = {}; pos = 25705
    while pos < 29640:
        room, n, flags = mem[pos:pos + 3]
        assert n >= 2, (pos, n)
        selector = flags >> 6
        assert selector < 3, (pos, selector)
        rooms[room] = selector; pos += n + 1
    assert pos == 29640, pos
    for room, selector in rooms.items(): directory[6400 + room] = FLOORS[selector]
    # The approved square floor is a stable coordinate field; narrow rooms crop it at the original world bounds.
    def project(x, y): return (round(x + y - 128), round(167 - (y - x + 128) / 2))
    for selector, (rx, ry) in enumerate(((64, 64), (32, 64), (64, 32))):
        mask = Image.new('1', (256, 192)); ImageDraw.Draw(mask).polygon([project(128 - rx, 128 + ry), project(128 + rx, 128 + ry), project(128 + rx, 128 - ry), project(128 - rx, 128 - ry)], fill=1)
        raw = bytes(lookup[px[:3]] | 128 if px[3] and mask.getpixel((i % 256, i // 256)) else 255 for i, px in enumerate(floor.getdata()))
        for k in range(6): pages[FLOORS[selector] + k] = bytearray(raw[k * 8192:(k + 1) * 8192])
    pages[25][512:768] = bytes(i if i < len(paint_rgb) else 15 for i in range(256))    # 4-bit colour translation
    report = dict(enhanced=enhanced, colours_sha256=hashlib.sha256(COLOURS.read_bytes()).hexdigest(),
                  paint_colours=paint_rgb, palette_colours=rgb, graphics=detail, rooms=len(rooms),
                  room_floor_counts=dict(Counter(rooms.values())), highest_page=max(pages), unique_oriented_graphics=len(dedup))
    return {k: bytes(v) for k, v in pages.items()}, report


def apply_restore(p, s):
    """Restore every temporary tail byte before entering the game: the tail's backup and an exact register restore sit
    in an unused span of the Sinclair ROM image, so no game memory is assumed dead."""
    tail, _, restore, _ = Z.build_tail(s, p.tail_addr, p.slot1, True)
    assert len(tail) <= 64
    original = bytes(s.read(p.tail_addr + i) for i in range(len(tail)))
    code = b'\xF3\x21' + Z.w16(BACKUP) + b'\x11' + Z.w16(p.tail_addr) + b'\x01' + Z.w16(len(tail)) + b'\xED\xB0' + tail[restore:]
    assert ENTRY + len(code) < 0x3A00
    assert set(rom48()[BACKUP:ENTRY + len(code)]) == {255}
    page = bytearray(p.page); page[BACKUP - 8192:BACKUP - 8192 + len(original)] = original
    page[ENTRY - 8192:ENTRY - 8192 + len(code)] = code
    p.page = bytes(page)
    p.extra_banks[13] = p.page + p.extra_banks[13][8192:]
    p.altrom = (BACKUP, p.altrom[1])
    p.original_pc = s.pc; p.tail_restore_bytes = len(tail); s.pc = ENTRY


class AlienPatch:
    name = 'Alien 8 Filmation renderer'

    def __init__(self, game, enhanced=True, self_erase=True):
        prof = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in prof['syms'].items()}
        self.page = bytes.fromhex(prof['page']); self.stub_extra = bytes.fromhex(prof['setup']); self.setup_call = 0xD000
        self.slot1 = (26, 0x3DF0); self.altrom = (0x3B00, 0x3E04)
        self.tail_addr = 0x5B00; self.uses_printer_buffer = False; self.keep_printer_buffer = True; self.hook_page_data = b''
        self.self_erase = self_erase
        pages, self.assets = compile_assets(game, enhanced=enhanced)
        pages[26] = self.page; pages[81] = bytes.fromhex(prof['auxiliary'])
        self.extra_banks = {}
        for p, raw in pages.items():
            bank = bytearray(self.extra_banks.get(p // 2, bytes(16384)))
            bank[(p & 1) * 8192:(p & 1) * 8192 + 8192] = raw
            self.extra_banks[p // 2] = bytes(bank)
        self.sites = [(at, bytes.fromhex(old), (bytes((opcode,)) + self.syms[sym].to_bytes(2, 'little')).ljust(len(bytes.fromhex(old)), b'\0')) for at, (old, sym, opcode) in SITES.items()]
        for e in json.loads((ROOT / 'docs/profiles/alien_8_sound_sites.json').read_text())['edges']:
            opcode = 0xC4 if e['op'].startswith('CALL NZ,') else 0xFC if e['op'].startswith('CALL M,') else 0xCD
            self.sites.append((e['pc'], bytes((opcode,)) + e['target'].to_bytes(2, 'little'), bytes((opcode,)) + self.syms['s_sound'].to_bytes(2, 'little')))

    def apply(self, s):
        assert not s.is128
        ram = bytearray(s.banks[5] + s.banks[2] + s.banks[0])
        for at, old, new in self.sites:
            assert bytes(s.read(at + i) for i in range(len(old))) == old, hex(at)
            ram[at - 0x4000:at - 0x4000 + len(new)] = new
        for k, b in enumerate((5, 2, 0)): s.banks[b] = bytes(ram[k * 16384:(k + 1) * 16384])
        if self.self_erase: apply_restore(self, s)


def loading_screen(snapshot):
    """The original 6,912-byte loading screen from the original tape beside the snapshot (same name, .tap), or None."""
    tape = Path(snapshot).with_suffix('.tap')
    if tape.exists() and hashlib.sha256(tape.read_bytes()).hexdigest() == TAPE_SHA256:
        return tape.read_bytes()[TAPE_SCREEN:TAPE_SCREEN + 6912]
    return None


def build(snapshot, out, enhanced=False):
    """One .nex: the converter's build, then the original loading screen (NEX header: ULA screen, start delay 50) when
    the tape is beside the snapshot. -> the patch (original_pc, tail_restore_bytes, assets)."""
    p = AlienPatch(snapshot, enhanced=enhanced)
    Z.convert(str(snapshot), str(out), quiet=True, patch=p)
    scr = loading_screen(snapshot)
    if scr is not None:
        b = Path(out).read_bytes(); h = bytearray(b[:512]); h[10] = 2; h[133] = 50
        Path(out).write_bytes(bytes(h) + scr + b[512:])
    p.loading_screen = scr is not None
    return p


def boot_problems(nex, z80, patch):
    """Boot NEX (as the converter's loader and as NEXLOAD leaves the machine) to the game's own entry, after the tail
    restorer: every register including R, and RAM 0x4000-0xFFFF, must equal the snapshot after patch.apply."""
    from . import nextboot
    import copy
    s = Z.Z80Snapshot(str(z80)); q = copy.deepcopy(patch); q.apply(s)
    ram = s.banks[5] + s.banks[2] + s.banks[0]
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), q.original_pc, nexload=nexload); R = st['R']; w = lambda n: R[n] * 256 + R[n + 1]
        bad += [('nexload' if nexload else 'loader',) + tuple(x) for x in st['bad']]
        for k, v in ((0, s.a), (1, s.f), (12, s.sp), (14, s.i), (15, s.r), (26, s.iff1), (27, s.im)):
            if R[k] != v: bad.append(('register', k, R[k], v))
        for k, v in ((2, s.bc), (4, s.de), (6, s.hl), (8, s.ix), (10, s.iy), (16, s.a_ * 256 + s.f_), (18, s.bc_), (20, s.de_), (22, s.hl_)):
            if w(k) != v: bad.append(('register', k, w(k), v))
        diff = [a for a in range(0x4000, 0x10000) if st['mem'][a] != ram[a - 0x4000]]
        if diff: bad.append(('RAM differs', len(diff), diff[:6]))
    return bad


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Not an RZX verifier yet: Alien 8's proof is the pilot run's replay oracle, soaks and negatives
    (games/alien_8.md "Evidence"). Porting that harness is the open item; until then this says so."""
    raise NotImplementedError('alien_8: no RZX verifier yet (games/alien_8.md "Evidence")')


def unit_tests(patch, states, neg=None):
    """No unit tests in the engine yet: the ABI, whole-sound, IRQ and negative cases ran in the pilot run
    (games/alien_8.md "Evidence")."""
    raise NotImplementedError('alien_8: no unit tests yet (games/alien_8.md "Evidence")')


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default (original look, hardware figures) and Enhanced (the owner's painting) builds, each
    with its boot check. The replay proof is the pilot run's (verify above)."""
    import os
    say('Game      : %s' % name)
    say('Engine    : alien_8 (Filmation renderer on Next sprites over Layer 2; default original look, Enhanced painted)')
    ok = True
    for label, enhanced, suffix in (('Default', False, ''), ('Enhanced', True, '_enhanced')):
        nex = os.path.join(out, name + suffix + '.nex')
        p = build(z80, nex, enhanced=enhanced)
        bad = boot_problems(nex, z80, AlienPatch(z80, enhanced=enhanced))
        ok &= not bad
        say('%-10s: %s  %s  tail %d bytes restored; loading screen %s' % (label, os.path.basename(nex), hashlib.md5(open(nex, 'rb').read()).hexdigest(),
                                                                        p.tail_restore_bytes, 'from the original tape' if p.loading_screen else 'none (no original .tap beside the snapshot)'))
        say('Boot      : %s' % ('OK (registers with R, RAM; converter loader and NEXLOAD)' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    enhanced = '--enhanced' in a
    a = [x for x in a if x != '--enhanced']
    if len(a) != 2: raise SystemExit(__doc__)
    snapshot, out = a
    build(snapshot, out, enhanced=enhanced)


if __name__ == '__main__':
    main()
