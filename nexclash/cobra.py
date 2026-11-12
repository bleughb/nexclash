"""Cobra (Ocean, 1986, 48K) engine 'cobra'. Additive module: reachable only through is_cobra().

Game facts (games/cobra.md): the play area is redrawn whole every game loop (compiled PUSH blits), then
one masked plotter draws every figure (39865 loop). The figure's light pixels are the cell's PAPER, so a
figure takes the colours of the cells it crosses (menu option 5, COLOUR, the default). Hooks
(asm/cobra_hooks.asm): the plotter writes sprites instead of the screen; a bullet likewise; ULA otherwise
as the original. The game raster-syncs on the floating bus (IN A,(255) at 38402): recordings need a
model of it (tools/probes/cobra_rec.py), since the toolkit's Machine reads 0xFF there and the game hangs.

Verify (PLAYBOOK 6): replay the recording; at each hook site run the patched code from the same state with the
next-side state (scratch page, sprites, patterns, palette) carried across sites. Compare CMP registers at
each hook's return, all game memory (hooks may write only dead stack), every screen byte the original's
plotter writes against the decoded mask/gfx, and at each frame's end the picture: patched ULA + sprites =
the original's pixels, in the visible window, bit for bit.
"""
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
SCRPAGE, ULAPAGE = 26, 10
TAIL_ADDR = 0xAE00          # zero in the snapshot, never touched in any recording (scan, games/cobra.md)
MAXP = 16
WIN = (24, 239, 0, 143)     # x1, x2, y1, y2: sprite clip = the cells that are not black on black
PLOTEND = 39922             # the plotter's RET, after LD SP,(41721)
SITES_ORIG = {39865: 'd17ea3', 40714: '732472', 36427: 'cde39a', 36599: 'cde39a', 43524: 'cde39a',
              36317: '21388d', 45046: 'cd69a3', 45731: 'cd69a3'}
SITE_SYM = {39865: 'e_plot', 40714: 'e_bul', 36427: 'e_frame', 36599: 'e_frd', 43524: 'e_frame',
            36317: 'e_rnd', 45046: 'e_txt', 45731: 'e_txt'}
SITE_OP = {36427: 0xCD, 36599: 0xCD, 43524: 0xCD, 45046: 0xCD, 45731: 0xCD}
SCREEN_PATCHES = [(40733, '72', '00'), (40735, '73', '00')]
FRAME_SITES = (36427, 36599, 43524)
INTERIORS = (36428, 36429, 36600, 36601, 43525, 43526, 36318, 36319, 45047, 45048, 45732, 45733)
SEQUELS = {39866: 39865, 39867: 39865, 40715: 40714, 40716: 40714}
READERS = (41075, 41080)    # the stars' LD A,(DE): the only game reads of the play area outside the plotter
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
PC, TS = 24, 25
SP = 12
RR = 15                     # R: the game reads only bit 7 (LD A,R / RET M, the ISR's LD R,255 frame flag); hooks never write R
V_PACE = 0x60               # HLIB_V_PACE in the hook page (26 bytes)
HSTK0 = 0x80                # the hook stack's lowest use (HSTK 0x4100, about 40 bytes deep)
VSPD = 0x5E                 # the hook page's speed latch (asm vspd): holds the incoming clock, left out of the matrix compare
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'cobra_colours.json')
PALETTE = [0x00, 0xFF, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6]   # as asm .pal
CPG, NCP = 28, 8            # colour planes: pages 28-35 (banks 14-17), mapped at slot 6 only for one LDIR
COLOUR_BANKS = (14, 15, 16, 17)
OVIDX = 0x1000              # index, offset in the hook page
PIDX, PENT = 0x1800, 0x1240 # the prepared-pattern store's index and entries, offsets in the hook page (asm PIDX / PENT)
PBASE, PIDXN = 46544, 1812  # asm PBASE / PIDXN: (address - PBASE) / 8 indexes PIDX
SPG, NSP = 36, 6            # store pages 36-41 (banks 18-20), mapped at slot 6 only for its OTIR
STORE_BANKS = (18, 19, 20)


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'cobra.json'), os.path.join(_HERE, 'cobra.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('cobra.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_cobra(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def class_table(a=1, b=2):
    """Default pixels: index gggg mmmm -> 2 bytes of 4 pixels. gfx 1 = dark (b), mask 0 + gfx 0 = body (a), else
    transparent."""
    t = bytearray(0x200)
    for i in range(256):
        g, m = i >> 4, i & 15
        px = [b if g >> (3 - k) & 1 else (0 if m >> (3 - k) & 1 else a) for k in range(4)]
        t[i] = px[0] << 4 | px[1]
        t[0x100 + i] = px[2] << 4 | px[3]
    return bytes(t)


def page_image(prof, index=b'', a=1, b=2):
    """The hook page (0x4000 when mapped): state 0, class table 0x200, KEEP 0x600, CLR 0x700, code 0x800, index 0x1000."""
    p = bytearray(8192)
    p[0x200:0x400] = class_table(a, b)
    for v in range(256):
        p[0x600 + v] = (0 if v >> 4 else 0xF0) | (0 if v & 15 else 0x0F)
    p[0x700:0x704] = bytes((0xFF, 0xF0, 0x0F, 0x00))
    code = bytes.fromhex(prof['hooks']['page'])
    p[0x800:0x800 + len(code)] = code
    p[OVIDX:OVIDX + len(index)] = index
    si, se = store_index(prof)
    p[PIDX:PIDX + len(si)] = si
    p[PENT:PENT + len(se)] = se
    return bytes(p)


def image_patterns(get, start, pairs, a=1, b=2):
    """What upload's slow path writes for an unpainted image (asm upload / em): per band of 8 row pairs, pattern 0
    (columns 0-1, 16 x 16) then pattern 1 (column 2 + 8 transparent pixels), 4-bit; rows past the image are 0."""
    cls = class_table(a, b)

    def em(w):
        e, d = get(w), get(w + 1)
        i1, i2 = (d & 0xF0) | (e >> 4), ((d << 4) & 0xF0) | (e & 15)
        return bytes((cls[i1], cls[0x100 + i1], cls[i2], cls[0x100 + i2]))
    out = bytearray()
    for band in range((pairs + 7) // 8):
        p0, p1 = bytearray(), bytearray()
        for i in range(8):
            k = 8 * band + i
            if k < pairs:
                w = start + 12 * k
                p0 += em(w) + em(w + 2) + em(w + 10) + em(w + 8)
                p1 += em(w + 4) + bytes(4) + em(w + 6) + bytes(4)
            else:
                p0 += bytes(16)
                p1 += bytes(16)
        out += p0 + p1
    return bytes(out)


def store_layout(prof=None):
    """[(start, pairs, page, offset)] for every listed image the store holds (its start 8-aligned from PBASE): 256
    bytes a band, packed in pages SPG.. (8K each, an image never across two)."""
    out, pg, off = [], SPG, 0
    for start, pairs in images(prof):
        d = start - PBASE
        if d < 0 or d % 8 or d // 8 >= PIDXN:
            continue
        n = 256 * ((pairs + 7) // 8)
        if off + n > 8192:
            pg, off = pg + 1, 0
            if pg >= SPG + NSP:
                raise ValueError('pattern store needs more than %d pages' % NSP)
        out.append((start, pairs, pg, off))
        off += n
    if len(out) > 255:
        raise ValueError('pattern store: more than 255 images')
    return out


def store_index(prof=None):
    """-> (PIDX bytes, PENT bytes) for the hook page."""
    idx, ent = bytearray(PIDXN), bytearray()
    for n, (start, pairs, pg, off) in enumerate(store_layout(prof)):
        idx[(start - PBASE) // 8] = n + 1
        a = 0xC000 + off
        ent += bytes((start & 255, start >> 8, pairs, pg, a & 255, a >> 8))
    return bytes(idx), bytes(ent)


def store_pages(get, prof=None, a=1, b=2):
    """{page: 8192 bytes} of prepared patterns, from the build's own graphics bytes."""
    pages = {p: bytearray(8192) for p in range(SPG, SPG + NSP)}
    for start, pairs, pg, off in store_layout(prof):
        d = image_patterns(get, start, pairs, a, b)
        pages[pg][off:off + len(d)] = d
    return {p: bytes(v) for p, v in pages.items()}


def images(prof=None):
    """[(start, row pairs)]: every image the plotter draws (profile colour_images: the frame table's 4 phases + capture)."""
    return [tuple(x) for x in (prof or load_profile()).get('colour_images', [])]


def bullets(prof=None):
    """[address of the bullet's E byte; D is the next]."""
    return list((prof or load_profile()).get('colour_bullets', []))


def image_key(ptr, y, col):
    """Staging row y, column byte col (0-2) -> the graphics byte's address (its mask is the byte before)."""
    i, r = y >> 1, y & 1
    return ptr + 12 * i + (6 + 2 * (2 - col) if r else 2 * col) + 1


def bullet_start(e):
    return 0x100 + 12 * (e & 255)


def colour_tables(get, cmap, prof=None):
    """Colour map -> (index bytes, {page: 8192 bytes}, info). A plane per image with any override: 15 bytes a staging
    row: for each of 3 columns 4 bytes of 2 nibbles (0 = default) and a transparent mask. An entry whose check
    byte is not the graphic's byte is ignored."""
    prof = prof or load_profile()
    pages = {p: bytearray(8192) for p in range(CPG, CPG + NCP)}
    idx, used, bad = [], set(), set()
    pg, off = CPG, 0

    def plane(start, pairs, cells):
        nonlocal pg, off
        n = 30 * pairs
        data = bytearray(n)
        any_ = False
        for y, col, bit, a in cells:
            key = '%04X' % a
            e = cmap.get(key)
            if not e:
                continue
            if e[0] != get(a):
                bad.add(key)
                continue
            used.add(key)
            o = 15 * y + 5 * col
            if len(e) > 3 and e[3] & (0x80 >> bit):
                data[o + 4] |= 0x80 >> bit
                any_ = True
            elif e[2][bit]:
                data[o + bit // 2] |= e[2][bit] << 4 if not bit & 1 else e[2][bit]
                any_ = True
        if not any_:
            return
        if off + n > 8192:
            pg, off = pg + 1, 0
            if pg >= CPG + NCP:
                raise ValueError('colour tables need more than %d pages' % NCP)
        pages[pg][off:off + n] = data
        idx.append((start, pairs, pg, 0xC000 + off))
        off += n

    for ptr, pairs in images(prof):
        plane(ptr, pairs, [(y, col, bit, image_key(ptr, y, col)) for y in range(2 * pairs) for col in range(3) for bit in range(8)])
    for e_ in bullets(prof):
        plane(bullet_start(e_), 2, [(y, 0, bit, e_ + (1 if y in (1, 2) else 0)) for y in range(4) for bit in range(8)])
    index = bytes([len(idx)]) + b''.join(bytes((s & 255, s >> 8, n, p, a & 255, a >> 8)) for s, n, p, a in idx)
    info = {'images with colours': len(idx), 'map entries used': len(used),
            'map entries ignored (check byte differs)': len(bad),
            'map entries for no known image': len(set(cmap) - used - bad)}
    return index, pages, info


def load_colours(path=None):
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(path or build_colours_path(COLOURS))


def colour_inputs_md5(get, prof=None):
    """MD5 + count of the graphics bytes the colour map is keyed by (every known image, masks included)."""
    seen = set()
    for ptr, pairs in images(prof):
        seen.update(range(ptr, ptr + 12 * pairs))
    for e in bullets(prof):
        seen.update((e, e + 1))
    return hashlib.md5(bytes(get(a) for a in sorted(seen))).hexdigest(), len(seen)


def colour_identity(peek, prof=None):
    """docs/COLOURS.md "Identity": keys = graphics byte (%04X), bit = pixel, one per preshifted phase."""
    prof = prof or load_profile()
    geo = hashlib.md5(json.dumps([prof.get('colour_images', []), prof.get('colour_bullets', [])]).encode()).hexdigest()
    return {'schema': 1, 'game': 'cobra', 'engine': 'cobra', 'keys': 'cobra-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': colour_inputs_md5(peek, prof)[0], 'geometry': geo}


# The archive's snapshot stops inside BASIC at line 5 PAUSE 0; line 6 is RANDOMIZE USR 44816. A .nex runs on NextZXOS's
# ROM3, whose BASIC is laid out differently: the stacked return address 0x1B76 (the 48K ROM's statement loop) holds DEC SP
# bytes there, which slide into a RET at 0x1BAB that pops a stale word and lands in the game's define-keys code (games/cobra.md
# "Start-up"). The game uses no ROM code after 44816. So both builds start here: the same wait on the
# loading screen, without BASIC, then the game's entry. The toolkit's boot check models the 48K ROM and cannot see this.
START = 0xAE60              # in the zero, never-touched area, after the tail
ENTRY = 44816
START_CODE = bytes([
    0xF3,                   # DI
    0xAF, 0xDB, 0xFE, 0xF6, 0xE0, 0x3C, 0x20, 0xF8,    # wait until no key is held (from the browser)
    0xAF, 0xDB, 0xFE, 0xF6, 0xE0, 0x3C, 0x28, 0xF8,    # wait for a key, as PAUSE 0
    0xC3, ENTRY & 255, ENTRY >> 8])


def apply_start(snap):
    b = bytearray(snap.banks[2])
    o = START - 0x8000
    if any(b[o:o + len(START_CODE)]):
        raise ValueError('start stub area is not empty in this snapshot')
    b[o:o + len(START_CODE)] = START_CODE
    snap.banks[2] = bytes(b)
    snap.pc = START


START_STUB = False          # 2026-11-05: the whole alt ROM image (Sinclair's ROM) runs the snapshot's own BASIC return, as
                            # on a 48K, so neither build needs the stub (games/cobra.md "Start-up"); True = the 2026-11-02 start


def _whole_rom_page(code=b''):
    """Image of 0x2000-0x3FFF for alt ROM image 1: Sinclair's ROM with `code` at ROM_ORG (its 0xFF area)."""
    from .build import rom48
    rom = rom48()
    if any(b != 0xFF for b in rom[ROM_ORG:ROM_ORG + len(code) + 20]):
        raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
    page = bytearray(rom[0x2000:0x4000])
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(code)] = code
    return bytes(page)


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 1 = Sinclair's 48K ROM (+ the tail's 20-byte register block in its
    0xFF area), so the snapshot's BASIC (PAUSE 0, then RANDOMIZE USR 44816) runs as on a 48K."""
    name = 'Cobra plain conversion, Sinclair\'s ROM as the alt ROM'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    sites = []

    def __init__(self):
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page()
        self.extra_banks = {12: self.page + bytes(8192)}

    def apply(self, snap):
        if START_STUB:
            apply_start(snap)


class CobraPatch:
    name = 'Cobra figures -> hardware sprites (altrom hooks, state in a Next page at slot 2)'

    def __init__(self, prof=None, rom_code=None, colours=None):
        self.prof = prof or load_profile()
        self.colours = load_colours() if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = _whole_rom_page(self.rom_code)
        self.sites = []
        for a, old in SITES_ORIG.items():
            self.sites.append((a, bytes.fromhex(old), bytes([SITE_OP.get(a, 0xC3)]) +
                               self.syms[SITE_SYM[a]].to_bytes(2, 'little')))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.num_patterns = 0
        self.scratch0 = page_image(self.prof)
        self.colour_pages = {}
        self.store = {}
        self.classes = (1, 2)
        self.cinfo = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Cobra patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('tail area is not empty in this snapshot')
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        if START_STUB:
            apply_start(snap)
        self.prepare(lambda a: ram[a - 0x4000] if a >= 0x4000 else 0)

    def prepare(self, peek):
        """The banks that depend on the colour map: 13 (hook page, index), 14-17 (planes)."""
        index, pages, self.cinfo = colour_tables(peek, self.colours, self.prof)
        self.scratch0 = page_image(self.prof, index)
        self.colour_pages = pages
        self.peek = peek
        self.store = store_pages(peek, self.prof, *self.classes)
        self.extra_banks = {12: self.page + bytes(8192), 13: self.scratch0 + bytes(8192)}
        for k, bk in enumerate(STORE_BANKS):
            self.extra_banks[bk] = self.store[SPG + 2 * k] + self.store[SPG + 2 * k + 1]
        for b in COLOUR_BANKS:
            self.extra_banks[b] = bytes(pages[2 * b]) + bytes(pages[2 * b + 1])


# ---------------------------------------------------------------------------------------------
# Next-side state: survives from hook to hook, as on the machine
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch=None):
        self.nr = {7: 0, 0x52: ULAPAGE, 0x56: 0}
        self.colour_pages = {}                          # slot 6 pages: colour planes and the pattern store
        if patch is not None:
            self.colour_pages.update(getattr(patch, 'colour_pages', {}) or {})
            self.colour_pages.update(getattr(patch, 'store', {}) or {})
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pal = {1: 0xFF, 2: 0x00}
        self.palidx = 0
        self.scratch = bytearray(8192)
        if patch is not None:
            self.scratch[:len(patch.scratch0)] = patch.scratch0
        self.ptr = 0
        self.uploads = 0
        self.fast = self.slow = 0
        self.mark = 0
        self.R = None
        self.sel = 0
        self.speed_in = 0                       # the clock a hook is entered at (the every-site matrix sets 1-3)
        self.rt = self.rt_mark = 0              # time model for the pace limiter: real time in a hook (3.5 MHz T)
        self.cur = 0
        self.t_entry = 0                        # the build's frame T at the hook's entry: the original's + skew
        self.skew = 0                           # the build's time over the original's so far this frame (T)
        self.fast28 = 8.0                       # 28 MHz in 3.5 MHz T (no wait states modelled)

    def div(self):
        """The recording's 3.5 MHz T -> real time at the game's clock (verify clock=)."""
        return (1.0, 2.0, 4.0, self.fast28)[self.speed_in & 3]

    def now(self):
        m = self.fast28 if self.cur == 3 else (1.0, 2.0, 4.0)[self.cur]
        return self.rt + ((self.R[TS] if self.R is not None else self.rt_mark) - self.rt_mark) / m

    def line(self):
        return int((self.t_entry + self.now() - 14336) // 224) % 312

    def clone(self):
        import copy
        q = copy.copy(self)
        q.nr, q.pal = dict(self.nr), dict(self.pal)
        q.attr = [list(a) for a in self.attr]
        q.pat, q.scratch = bytearray(self.pat), bytearray(self.scratch)
        q.R = None
        return q

    def nextreg(self, reg, val):
        if reg == 7 and self.R is not None:
            self.rt = self.now()
            self.rt_mark, self.cur = self.R[TS], val & 3
        if reg == 7 and self.R is not None:
            t = self.R[TS]
            if val == 3:
                self.slow += t - self.mark
            else:
                self.fast += t - self.mark
            self.mark = t
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            self.palidx = val
        elif reg == 0x41:
            self.pal[self.palidx] = val
            self.palidx = (self.palidx + 1) & 255

    def read_port(self, regs, port):
        if port & 0xFFFF == 0x253B and self.sel == 7:
            s = self.nr.get(7, 0) & 3
            return s << 4 | s                   # actual speed 5:4, programmed 1:0 (hooklib.NextModel)
        if port & 0xFFFF == 0x253B and self.sel in (0x1E, 0x1F):
            ln = self.line()                    # NR 0x1E / 0x1F: the video line (0 = the first pixel row)
            return ln >> 8 & 1 if self.sel == 0x1E else ln & 255
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port & 0xFFFF == 0x243B:
            self.sel = value
        elif port & 0xFFFF == 0x303B:
            self.ptr = (value & 0x3F) * 256 + (128 if value & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.ptr & 0x3FFF] = value
            self.ptr += 1
            self.uploads += 1

    def composite(self):
        """{(x, y): 1 body / 2 dark} of the visible sprites, in slot order, inside the clip window."""
        out = {}
        for a in self.attr[:MAXP * 4]:
            if not a[3] & 0x80:
                continue
            x0 = a[0] + (a[2] & 1) * 256 - 32
            y0 = a[1] + (a[4] & 1) * 256 - 32
            base = (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)
            pat = self.pat
            for j in range(16):
                y = y0 + j
                if not WIN[2] <= y <= WIN[3]:
                    continue
                for k in range(8):
                    b = pat[base + j * 8 + k]
                    if b:
                        x = x0 + 2 * k
                        if b >> 4 and WIN[0] <= x <= WIN[1]:
                            out[(x, y)] = b >> 4
                        if b & 15 and WIN[0] <= x + 1 <= WIN[1]:
                            out[(x + 1, y)] = b & 15
        return out


def _overlay(patch, get, ns, alt):
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}

    class P:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if a < 0x6000 and ns.nr[0x52] == SCRPAGE:
                return ns.scratch[a - 0x4000]
            if 0xC000 <= a < 0xE000 and ns.nr[0x56]:
                return ns.colour_pages[ns.nr[0x56]][a - 0xC000]
            v = s.ov.get(a)
            if v is not None:
                return v
            v = psite.get(a)
            if v is not None:
                return v
            return get(a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                return
            if a < 0x6000 and ns.nr[0x52] == SCRPAGE:
                ns.scratch[a - 0x4000] = v
            else:
                s.ov[a] = v

        def __len__(s):
            return 65536
    return P


_POV = {}


def _hook_run(patch, get, ns, alt, regs, stop, ov=None, limit=400000):
    """Run patched code from regs until PC is in stop. -> (registers, game memory written, ok)."""
    from skoolkit.simulator import Simulator
    from .simpool import machine
    from . import z80n
    cls = _overlay(patch, get, ns, alt)
    m = cls()
    if ov:
        m.ov.update(ov)
    sim = machine(Simulator, m, regs, 'p')
    R = sim.registers
    sim.set_tracer(ns)
    z80n.install(sim, ns.nextreg)
    ops, n = sim.opcodes, 0
    ns.R, ns.mark = R, R[TS]
    ns.rt, ns.rt_mark, ns.cur, ns.t_entry = 0, R[TS], ns.speed_in, regs[TS] / ns.div() + ns.skew
    ns.nextreg(7, ns.speed_in)                   # the hook is entered at the game's clock (verify clock=, the matrix)
    while R[PC] not in stop:
        ops[m[R[PC]]]()
        n += 1
        if n > limit:
            return list(R), m.ov, False
    ns.last_real = ns.now()
    ns.R = None
    return list(R), m.ov, True


def _alt(patch):
    """Alt ROM image 1 as the stub leaves it on the Next (nextboot.alt_image: the whole image, Sinclair's ROM + hooks)."""
    from .nextboot import alt_image
    return alt_image(patch)


def scr_addr(x_col, y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | x_col


def addr_xy(a):
    a -= 0x4000
    h, l = a >> 8, a & 255
    return l & 31, ((h & 0x18) << 3) | (h & 7) | ((l & 0xE0) >> 2)


def plot_model(hl, rows, gfx):
    """The plotter's writes in order: [(screen addr, mask, gfx byte)]. gfx(i) = byte at SP+i."""
    h, l = hl >> 8, hl & 255
    out = []
    i = 0
    for _ in range(rows):
        for st in ('ll', 'd'):
            for k in range(3):
                out.append(((h << 8) | l, gfx(i), gfx(i + 1)))
                i += 2
                if k < 2:
                    l = (l + (1 if st == 'll' else -1)) & 255
            h = (h + 1) & 255
        if h & 6 == 0:
            l = l + 32
            if l > 255:
                l &= 255
            else:
                h = (h - 8) & 255
    return out


def _png(mem_get, ps, ns, path, attr_get=None):
    from PIL import Image
    n = [(0, 0, 0), (0, 0, 192), (192, 0, 0), (192, 0, 192), (0, 192, 0), (0, 192, 192), (192, 192, 0), (192, 192, 192)]
    b = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

    def ula(px_get):
        im = Image.new('RGB', (256, 192))
        px = im.load()
        for y in range(192):
            for col in range(32):
                v = px_get(scr_addr(col, y))
                at = mem_get(0x5800 + (y >> 3) * 32 + col)
                tab = b if at & 0x40 else n
                ink, paper = tab[at & 7], tab[at >> 3 & 7]
                for k in range(8):
                    px[col * 8 + k, y] = ink if v >> (7 - k) & 1 else paper
        return im
    left = ula(mem_get)
    right = ula(lambda a: ps[a - 0x4000])
    rp = right.load()
    rgb = lambda v: ((v >> 5) * 255 // 7, ((v >> 2) & 7) * 255 // 7, (v & 3) * 85)
    for (x, y), c in ns.composite().items():
        rp[x, y] = rgb(ns.pal.get(c, 0))
    sh = Image.new('RGB', (2 * 256 + 8, 192), (64, 64, 64))
    sh.paste(left, (0, 0))
    sh.paste(right, (264, 0))
    sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(path)


# ---------------------------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, shots=None, clock=0):
    """Replay the RZX (original game); see the module docstring. shots: {frame: png path}, written at
    the first frame end from that frame on. -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    has = {a for a, old, new in patch.sites}
    ns = NextState(patch)
    ns.speed_in = clock                          # the game's clock (NR 7): 0 = 3.5 MHz as recorded
    st = {'frame': 0, 'on': False, 'plot': None, 'bul': None, 'fr': None, 'death': False}
    ps = bytearray(0x1800)
    dirty = set()
    fresh = set()
    stale = set()
    writes = []
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS) | set(SEQUELS) | set(READERS) | {PLOTEND, 40736, 39810} | \
        {a + 3 for a in FRAME_SITES}
    states = []
    shots = dict(shots or {})

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    mxn = collections.Counter()

    def mx(name, regs, stop_, ov_=None, mem_=None):
        """A hook entry for the every-site matrix (unit_tests): registers, memory, the Next-side state."""
        if collect and mxn[name] < collect:
            mxn[name] += 1
            states.append(('mx', name, list(regs), bytes(G(mem_, a) for a in range(65536)), ns.clone(), set(stop_),
                           dict(ov_ or {})))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                if 0x4000 <= a < 0x5800:
                    if st['plot'] is not None or st['bul'] is not None:
                        writes.append((a, G(s, a), v))
                    else:
                        ps[a - 0x4000] = v
                        dirty.discard(a)
            S(s, a, v)

    def check_regs(kind, R, Rp, skip=()):
        for i in CMP:
            if i not in skip and R[i] != Rp[i]:
                fail('%s: register %d differs' % (kind, i), (R[i], Rp[i], R[PC]))
        if (R[RR] ^ Rp[RR]) & 0x80:              # the game's frame flag (games/cobra.md "R"); bits 6:0 are never read
            fail('%s: R bit 7 differs' % kind, (R[RR], Rp[RR], R[PC]))

    def check_ov(kind, ov, sp):
        for a in ov:
            if not (sp - 64 <= a < sp) and a not in patch_bytes:
                fail('%s: hook wrote game memory' % kind, (a, ov[a]))

    patch_bytes = site_bytes

    def check_mapped(kind):
        if ns.nr[0x52] != ULAPAGE or ns.nr.get(7, 0) != ns.speed_in or ns.nr[0x56]:
            fail('%s: left slot 2, slot 6 or not the incoming speed' % kind, (ns.nr[0x52], ns.nr.get(7), ns.nr[0x56]))
            ns.nr[0x52], ns.nr[7], ns.nr[0x56] = ULAPAGE, ns.speed_in, 0

    def frame_end(get):
        comp = ns.composite()
        seen = set()
        npx = 0
        for a in dirty:
            col, y = addr_xy(a)
            real, base = get(a), ps[a - 0x4000]
            for k in range(8):
                x = col * 8 + k
                if not (WIN[0] <= x <= WIN[1] and WIN[2] <= y <= WIN[3]):
                    continue
                cl = comp.get((x, y))
                seen.add((x, y))
                if cl and cl > 2:
                    c['painted pixels (colour not modelled by the picture check)'] += 1
                    continue
                bit = 7 - k
                exp = (1 if cl == 2 else 0) if cl else (base >> bit) & 1
                npx += 1
                if exp != (real >> bit) & 1:
                    if st['death'] and (a in stale or a in fresh):
                        c['death loop: trail pixels the original accumulates, build has not'] += 1
                    elif a in fresh and a not in stale:
                        fail('picture differs', (x, y, cl))
                    elif cl:
                        fail('picture differs under a sprite', (x, y, cl))
                    elif 5 <= col <= 28:
                        fail('trail pixel inside the redrawn columns', (x, y))
                    else:
                        c['edge trail pixels (columns the redraw skips; original keeps, build has not)'] += 1
        for xy in comp:
            if xy not in seen:
                fail('sprite pixel where the original plotted nothing', xy)
        c['picture pixels compared'] += npx
        stale.clear()
        stale.update(dirty)
        fresh.clear()
        c['sprite pixels shown'] += len(comp)
        mono = get(64729)
        c['frames mono' if mono else 'frames colour'] += 1
        want = SPECCY[(get(0x5803) >> 3) & 15] if mono else 0xFF
        if mono and not get(0x5803):
            c['mono frames before the play area is painted'] += 1     # a new life's first plot: attributes still 0
        elif ns.pal.get(1) != want:
            fail('body colour', (ns.pal.get(1), want))
        for (x, y), cl in comp.items():
            if cl == 1:
                at = get(0x5800 + (y >> 3) * 32 + (x >> 3))
                if SPECCY[(at >> 3) & 15] != want:
                    c['body pixels the original showed in another colour'] += 1
                else:
                    c['body pixels the original showed in this colour'] += 1
        if shots:
            for f in sorted(shots):
                if st['frame'] >= f:
                    _png(get, ps, ns, shots.pop(f))
                    c['shots'] += 1
                break

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)
            for a in range(0x1800):
                ps[a] = G(mem, 0x4000 + a)

            def mk(fn):
                def g():
                    pc = R[PC]
                    if pc in WATCH:
                        cnt[pc] += 1
                        event(pc, R, mem, get)
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    def event(pc, R, mem, get):
        if pc == 39865 and 39865 in has:
            if st['plot'] is not None:
                cnt[39865] += 0
                return
            if collect and c['collected plot'] < collect:
                c['collected plot'] += 1
                states.append(('plot', list(R), bytes(G(mem, a) for a in range(65536)), None))
            hl, rows, sp = R[6] << 8 | R[7], R[2], R[SP]
            gfx = bytes(get((sp + i) & 0xFFFF) for i in range(12 * rows))
            ns.fast = ns.slow = 0
            u0 = ns.uploads
            mx('plot', R, {PLOTEND}, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, list(R), {PLOTEND})
            if ns.uploads != u0:
                c['plot uploads (cache misses)'] += 1
            if not ok:
                fail('plot: hook did not finish', (hl, rows))
            check_mapped('plot')
            c['plot'] += 1
            st['last_fast'], st['last_slow'] = ns.fast, ns.slow + Rp[TS] - ns.mark
            st['last_kind'] = 'upload' if ns.uploads != u0 else 'hit'
            st['plot_real'] = ns.last_real
            st['plot'] = (hl, rows, gfx, Rp, ov, R[TS])
            del writes[:]
        elif pc == PLOTEND:
            if st['plot'] is None:
                return
            hl, rows, gfx, Rp, ov, t0 = st['plot']
            st['plot'] = None
            check_regs('plot', R, Rp)
            check_ov('plot', ov, R[SP])
            if R[TS] > t0:
                ns.skew += st['plot_real'] - (R[TS] - t0) / ns.div()
                c['T plot windows, original'] += (R[TS] - t0) / ns.div()
                c['T plot windows, build (model)'] += st['plot_real']
                c['T original plot'] += R[TS] - t0
                c['T patched for those plots'] += st['last_fast'] / 6 + st['last_slow']
                k = st['last_kind']
                c['T original, %s plots' % k] += R[TS] - t0
                c['T patched 28 MHz part, %s plots' % k] += st['last_fast']
                c['T patched 3.5 MHz part, %s plots' % k] += st['last_slow']
                c['%s plots timed' % k] += 1
            else:
                c['plots across a frame boundary (T not counted)'] += 1
            scr = [w for w in writes]
            model = plot_model(hl, rows, lambda i: gfx[i])
            if len(scr) != len(model):
                fail('plot: writes differ from the model in number', (hl, rows, len(scr), len(model)))
            for w, m in zip(scr, model):
                if w[0] != m[0] or w[2] != (w[1] & m[1]) | m[2]:
                    fail('plot: write differs from the model', (hl, rows, w, m))
                    break
                dirty.add(w[0])
                fresh.add(w[0])
            for w in scr:
                col, y = addr_xy(w[0])
                if y >= 144:
                    c['plot bytes below the play area'] += 1
                if y >= 152:
                    c['plot bytes in the panel rows (y >= 152)'] += 1
        elif pc == 39810:
            c['plot top clip'] += 1
        elif pc == 40714 and 40714 in has:
            if collect and c['collected bul'] < collect:
                c['collected bul'] += 1
                states.append(('bul', list(R), bytes(G(mem, a) for a in range(65536)), None))
            mx('bullet', R, {40717}, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, list(R), {40717})
            if not ok:
                fail('bullet: hook did not finish')
            check_mapped('bullet')
            ns.skew += ns.last_real - 24 / ns.div()  # LD (HL),E / INC H / LD (HL),D, and the two writes made NOPs
            c['T outside hooks over the original (model)'] += ns.last_real - 24 / ns.div()
            c['bullet'] += 1
            st['bul'] = (R[6] << 8 | R[7], R[4], R[5], Rp, ov)
            del writes[:]
        elif pc == 40736:
            if st['bul'] is None:
                return
            hl, d, e, Rp, ov = st['bul']
            st['bul'] = None
            for k, (w, v) in enumerate(zip(writes, (e, d, d, e))):
                if w[2] != v:
                    fail('bullet: write differs from the model', (hl, w, v))
                dirty.add(w[0])
                fresh.add(w[0])
            if len(writes) != 4:
                fail('bullet: writes', (len(writes),))
            for i in (2, 3, 4, 5):      # BC, DE at the hook's exit against the original's at its end
                if R[i] != Rp[i]:
                    fail('bullet: register %d differs' % i, (R[i], Rp[i]))
            check_ov('bullet', ov, R[SP])
        elif pc in FRAME_SITES and pc in has:
            sp = R[SP]
            Rb = list(R)
            mx('frame %d' % pc, Rb, {39651}, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, Rb, {39651})
            if not ok:
                fail('frame: hook did not finish')
            check_mapped('frame')
            st['fig0'] = (ns.skew, R[TS])
            ns.skew += ns.last_real - 17 / ns.div()  # its CALL 39651
            c['T outside hooks over the original (model)'] += ns.last_real - 17 / ns.div()
            if Rp[SP] != sp - 4:
                fail('frame: stack', (sp, Rp[SP]))
            check_regs('frame', R, Rp, skip=(0, 1, SP, PC))    # 39651 starts LD A,(nn): A, F dead
            c['frame'] += 1
            st['fr'] = (pc + 3, sp)
            st['death'] = pc == 36599
            if st['death']:
                c['frame in the death loop'] += 1
        elif st['fr'] is not None and pc == st['fr'][0] and R[SP] == st['fr'][1]:
            ret, sp = st['fr']
            st['fr'] = None
            Rb = list(R)
            Rb[PC] = patch.syms['e_fend']
            Rb[SP] = sp - 2
            sv = {sp - 2: ret & 255, sp - 1: ret >> 8}
            mx('frame end', Rb, {ret}, sv, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, Rb, {ret}, ov=sv)
            if not ok:
                fail('frame end: hook did not finish')
            check_mapped('frame end')
            ns.skew += ns.last_real
            c['T outside hooks over the original (model)'] += ns.last_real
            if st.get('fig0') and R[TS] > st['fig0'][1]:
                d, t = ns.skew - st['fig0'][0], (R[TS] - st['fig0'][1]) / ns.div()
                c['figure phases timed'] += 1
                c['T figure phases, original'] += t
                c['T figure phases, build over the original (model)'] += d
                c['figure phase, worst over the original (T, model)'] = max(c['figure phase, worst over the original (T, model)'], round(d))
                c['figure phase, worst under the original (T, model)'] = min(c['figure phase, worst under the original (T, model)'], round(d))
            st['fig0'] = None
            check_regs('frame end', R, Rp, skip=(PC,))
            c['frame end'] += 1
            frame_end(get)
        elif pc == 36317 and pc in has:
            mx('round', R, {36320}, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, list(R), {36320})
            check_mapped('round')
            if not ok:
                fail('round: hook did not finish')
            c['round'] += 1
            if ns.composite():
                fail('round: sprites still shown')
            for i in CMP:
                if i not in (6, 7, PC) and R[i] != Rp[i]:
                    fail('round: register %d differs' % i, (R[i], Rp[i]))
            if Rp[6] << 8 | Rp[7] != 36152:
                fail('round: HL')
        elif pc in (45046, 45731) and pc in has:
            mx('text %d' % pc, R, {41833}, mem_=mem)
            Rp, ov, ok = _hook_run(patch, get, ns, alt, list(R), {41833})
            check_mapped('text')
            if not ok:
                fail('text: hook did not finish')
            c['text %d' % pc] += 1
            if ns.composite():
                fail('text: sprites still shown')
            for i in CMP:
                if i not in (SP, PC) and R[i] != Rp[i]:
                    fail('text: register %d differs' % i, (R[i], Rp[i]))
            if Rp[SP] != R[SP] - 2:
                fail('text: stack', (R[SP], Rp[SP]))
        elif pc in READERS:
            a = R[4] << 8 | R[5]
            c['star reads'] += 1
            if a in dirty and G(mem, a) != ps[a - 0x4000]:
                col = addr_xy(a)[0]
                if 5 <= col <= 28:
                    fail('star read a figure byte inside the redrawn columns', (a,))
                else:
                    c['star read a trail byte (A dead after 41037; star pixel only)'] += 1

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        ns.skew = 0                                  # each frame starts at its interrupt in both
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a, b in SEQUELS.items():
        if cnt[a] != cnt[b]:
            c['%d reached other than from %d!' % (a, b)] += 1
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (%d)!' % a] += 1
    for a, k in ((39865, 'plot'), (36427, 'frame')):
        if not c[k]:
            c['hook %s never ran!' % k] += 1
    for a in SITES_ORIG:
        if cnt[a] and a not in has:
            c['site %d reached, its hook is not in this build!' % a] += 1
    c['frames'] = st['frame']
    if c['T figure phases, original']:
        pen = 100.0 * c['T figure phases, build over the original (model)'] / c['T figure phases, original']
        c['figure phase time over the original, %% x 100 (model)'] = round(100 * pen)
        if abs(pen) > 2 and not clock:                 # ORIGINAL pace is the game's own clock; at 7-28 MHz informative
            c['figure phases %+.1f%% of the original\'s time (pace limiter, model)!' % pen] += 1
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit cases: what the recordings may not reach
# ---------------------------------------------------------------------------------------------

def _orig_run(mem0, regs, stop, limit=200000):
    from skoolkit.simulator import Simulator
    sim = Simulator(bytearray(mem0), {})
    sim.registers[:] = regs
    R, ops, m = sim.registers, sim.opcodes, sim.memory
    n = 0
    while R[PC] != stop:
        ops[m[R[PC]]]()
        n += 1
        if n > limit:
            raise RuntimeError('original did not finish')
    return list(R), m


def _plot_case(patch, alt, mem0, regs0, ns, rows, col, y, seed, c, tag, neg=False):
    """Run the original on 0x00 and 0xFF canvases and the hook; registers and classes must agree."""
    import random
    rng = random.Random(seed)
    mem = bytearray(mem0)
    gfx = 0xC000
    for i in range(12 * rows):
        mem[gfx + i] = rng.choice((0, 0xFF, rng.randrange(256)))
    hl = scr_addr(col, y)
    mem[41721] = 0xF0
    mem[41722] = 0x61
    R = list(regs0)
    R[6], R[7] = hl >> 8, hl & 255
    R[2], R[12], R[PC] = rows, gfx, 39865
    res = {}
    out = None
    for canvas in (0, 0xFF):
        m = bytearray(mem)
        m[0x4000:0x5800] = bytes([canvas]) * 0x1800
        out, mm = _orig_run(m, R, PLOTEND)
        res[canvas] = mm
    ns.attr[:MAXP * 4] = [[0, 0, 0, 0, 0] for _ in range(MAXP * 4)]
    ns.scratch[0] = 0
    ns.scratch[0x20:0x20 + 3 * MAXP] = bytes(3 * MAXP)     # new graphics at the same address: not a cache case
    Rp, ov, ok = _hook_run(patch, lambda a: mem[a], ns, alt, list(R), {PLOTEND})
    bad = not ok or any(Rp[i] != out[i] for i in CMP)
    bad = bad or any(not (0x61F0 - 64 <= a < 0x61F0) for a in ov)
    comp = ns.composite()
    seen = set()
    for w in plot_model(hl, rows, lambda i: mem[gfx + i]):
        a = w[0]
        if not 0x4000 <= a < 0x5800:
            continue
        cx, cy = addr_xy(a)
        for k in range(8):
            x = cx * 8 + k
            if not (WIN[0] <= x <= WIN[1] and WIN[2] <= cy <= WIN[3]):
                continue
            seen.add((x, cy))
            b0 = res[0][a] >> (7 - k) & 1
            bf = res[0xFF][a] >> (7 - k) & 1
            want = 2 if b0 else (1 if not bf else 0)
            if comp.get((x, cy), 0) != want:
                bad = True
    if any(xy not in seen for xy in comp):
        bad = True
    return bad


def clock_matrix(patch, states):
    """The every-site matrix (hooklib.every_site; card patch.restore-speed): each captured hook entry run at NR 7 =
    0-3 from the same state must exit at its incoming clock with the same registers (CMP + R bit 7), game memory
    written, sprite attributes, patterns, palette, MMU slots and hook page (less the latch). -> (Counter, rows)."""
    from .hooklib import every_site
    alt = _alt(patch)
    cases = [s for s in states if s[0] == 'mx']

    def run(i, k):
        _, name, regs, mem, ns0, stop_, ov_ = cases[i]
        ns = ns0.clone()
        ns.speed_in = k
        Rp, ov, ok = _hook_run(patch, lambda a: mem[a], ns, alt, list(regs), stop_, ov=dict(ov_))
        page = bytearray(ns.scratch)
        page[VSPD] = 0
        page[V_PACE:V_PACE + 26] = bytes(26)     # the limiter's lines, held time and debt: timing state, not results
        page[HSTK0:0x100] = bytes(0x100 - HSTK0)   # the hook stack, and below the game's SP only the addresses:
        return ns.nr.get(7, 0), (ok, [Rp[j] for j in CMP], Rp[RR] & 0x80, sorted(ov),   # dead stack holds timing values
                                 [tuple(a) for a in ns.attr], bytes(ns.pat), sorted(ns.pal.items()),
                                 ns.nr[0x52], ns.nr[0x56], bytes(page))
    c, rows = every_site(range(len(cases)), run)
    for r in rows:
        r['site'] = cases[r['site']][1]
    c['sites'] = len({cases[i][1] for i in range(len(cases))})
    return c, rows


def unit_tests(patch, states, neg=None):
    """Plot geometry x edges, guard, cache, bullets, hide, mono palette. neg: broken patches that must fail."""
    c = collections.Counter()
    plots = [s for s in states if s[0] == 'plot']
    if not plots:
        c['no captured plot state!'] += 1
        return c
    mem0, regs0 = plots[0][2], plots[0][1]
    alt = _alt(patch)
    ns = NextState(patch)
    n = 0
    for rows in (1, 2, 4, 8, 9, 12, 16):
        for col in (0, 3, 15, 28, 29, 30):
            for y in (0, 8, 14, 62, 104):
                n += 1
                if _plot_case(patch, alt, mem0, regs0, ns, rows, col, y, n, c, 'geom'):
                    c['plot case FAILED!'] += 1
                else:
                    c['plot geometry cases ok'] += 1
    # guard: plot index full -> no sprite, same registers, no upload
    get = lambda a: mem0[a]
    ns = NextState(patch)
    ns.scratch[0] = MAXP
    R = list(regs0)
    R[PC] = 39865
    up = ns.uploads
    Rp, ov, ok = _hook_run(patch, get, ns, alt, list(R), {PLOTEND})
    if ok and ns.uploads == up and not ns.composite():
        c['slot guard ok'] += 1
    else:
        c['slot guard FAILED!'] += 1
    # cache: the same plot twice uploads once; another row count uploads again
    ns = NextState(patch)
    _hook_run(patch, get, ns, alt, list(R), {PLOTEND})
    u1 = ns.uploads
    ns.scratch[0] = 0
    _hook_run(patch, get, ns, alt, list(R), {PLOTEND})
    if u1 and ns.uploads == u1:
        c['cache hit ok'] += 1
    else:
        c['cache hit FAILED!'] += 1
    ns.scratch[0] = 0
    R2 = list(R)
    R2[2] = R[2] + 1 if R[2] < 16 else R[2] - 1
    _hook_run(patch, get, ns, alt, list(R2), {PLOTEND})
    if ns.uploads > u1:
        c['cache miss ok'] += 1
    else:
        c['cache miss FAILED!'] += 1
    # bullets
    for e, d in ((0x18, 0x3C), (0, 0xFF), (0xFF, 0), (0x81, 0x42)):
        ns = NextState(patch)
        mem = bytearray(mem0)
        for y, col in ((10, 12), (0, 3), (62, 28)):
            ns.attr[:MAXP * 4] = [[0, 0, 0, 0, 0] for _ in range(MAXP * 4)]
            ns.scratch[0] = 0
            hl = scr_addr(col, y)
            r = list(regs0)
            r[6], r[7], r[4], r[5], r[PC] = hl >> 8, hl & 255, d, e, 40714
            Rp, ov, ok = _hook_run(patch, lambda a: mem[a], ns, alt, r, {40717})
            comp = ns.composite()
            good = ok and Rp[4] == d and Rp[5] == e and Rp[2] == r[2] and Rp[3] == r[3] and Rp[6] == (hl >> 8) + 1
            for j, v in enumerate((e, d, d, e)):
                for k in range(8):
                    want = 2 if v >> (7 - k) & 1 else 1
                    x, yy = col * 8 + k, y + j
                    if WIN[0] <= x <= WIN[1] and comp.get((x, yy), 0) != want:
                        good = False
            if len(comp) != 32:
                good = False
            c['bullet cases ok' if good else 'bullet case FAILED!'] += 1
    # hide: text and round entries clear everything; frame end hides what was not plotted
    ns = NextState(patch)
    ns.scratch[1] = MAXP
    for s in range(MAXP * 4):
        ns.attr[s] = [40, 40, 0, 0xC0, 0x80]
    ns.pat[0:128] = bytes([0x11]) * 128
    r = list(regs0)
    r[PC] = patch.syms['e_txt']
    Rp, ov, ok = _hook_run(patch, get, ns, alt, r, {41833})
    good = ok and all(not a[3] & 0x80 for a in ns.attr[:MAXP * 4]) and ns.scratch[1] == 0
    c['hide cases ok' if good else 'hide case FAILED!'] += 1
    ns = NextState(patch)
    ns.scratch[0], ns.scratch[1] = 2, 5
    for s in range(48):
        ns.attr[s] = [40, 40, 0, 0xC0, 0x80]
    r = list(regs0)
    r[PC], r[SP] = patch.syms['e_fend'], 0x61F0
    Rp, ov, ok = _hook_run(patch, get, ns, alt, r, {mem0[0x61F0] | mem0[0x61F1] << 8})
    good = ok and all(ns.attr[s][3] & 0x80 for s in range(8)) and \
        not any(ns.attr[s][3] & 0x80 for s in range(8, 20)) and ns.scratch[1] == 2
    c['frame end hide ok' if good else 'frame end hide FAILED!'] += 1
    # palette: colour mode white, mono the play area's paper
    for flag, at, want in ((0, 0x68, 0xFF), (1, 0x70, 0xFC), (1, 0x28, 0xB6 and SPECCY[5]), (1, 0x60, 0x1C)):
        ns = NextState(patch)
        mem = bytearray(mem0)
        mem[64729] = flag
        mem[0x5803] = at
        r = list(regs0)
        r[PC], r[SP] = patch.syms['e_frame'], 0x61F0
        Rp, ov, ok = _hook_run(patch, lambda a: mem[a], ns, alt, r, {39651})
        good = ok and ns.pal.get(1) == want and ns.scratch[0] == 0
        c['palette cases ok' if good else 'palette case FAILED!'] += 1
    # colour map: painted, transparent and clear-made-opaque pixels per image geometry, positions, a wrong check byte
    get0 = lambda a: mem0[a]
    prof = patch.prof
    for ptr, pairs in images(prof)[::9] + [images(prof)[0]]:
        cm = {}
        a0, a1, a2 = image_key(ptr, 0, 0), image_key(ptr, 2 * pairs - 1, 1), image_key(ptr, pairs, 2)
        cm['%04X' % a0] = [mem0[a0], 'g', [3, 0, 0, 0, 0, 0, 0, 9]]
        cm['%04X' % a1] = [mem0[a1], 'g', [0, 4, 0, 0, 0, 0, 15, 0], 0x08]
        cm['%04X' % a2] = [(mem0[a2] + 1) & 255, 'g', [5] * 8]       # wrong check: ignored
        q = CobraPatch(prof, colours=cm)
        q.prepare(get0)
        altq = _alt(q)
        for col, y in ((10, 8), (4, 0), (20, 62)):
            ns = NextState(q)
            r = list(regs0)
            hl = scr_addr(col, y)
            r[6], r[7], r[2], r[12], r[PC] = hl >> 8, hl & 255, pairs, ptr, 39865
            _, _, ok = _hook_run(q, get0, ns, altq, r, {PLOTEND})
            comp = ns.composite()
            good = ok
            for yy in range(2 * pairs):
                for cc in range(3):
                    a = image_key(ptr, yy, cc)
                    m_, g_ = mem0[a - 1], mem0[a]
                    for bit in range(8):
                        x, sy = col * 8 + cc * 8 + bit, y + yy
                        if not (WIN[0] <= x <= WIN[1] and WIN[2] <= sy <= WIN[3]):
                            continue
                        d = 2 if g_ >> (7 - bit) & 1 else (0 if m_ >> (7 - bit) & 1 else 1)
                        e = cm.get('%04X' % a)
                        if e and e[0] == g_:
                            if len(e) > 3 and e[3] & (0x80 >> bit):
                                d = 0
                            elif e[2][bit]:
                                d = e[2][bit]
                        if comp.get((x, sy), 0) != d:
                            good = False
            c['colour map cases ok' if good else 'colour map case FAILED!'] += 1
        # the same image with the map left out must not look painted
        ns = NextState(patch)
        r = list(regs0)
        hl = scr_addr(10, 8)
        r[6], r[7], r[2], r[12], r[PC] = hl >> 8, hl & 255, pairs, ptr, 39865
        _hook_run(patch, get0, ns, alt, r, {PLOTEND})
        painted = ns.composite()
        ns2 = NextState(q)
        _hook_run(q, get0, ns2, altq, list(r), {PLOTEND})
        c['colour negative detected (map left out)' if painted != ns2.composite() else 'colour negative NOT DETECTED!'] += 1
    # a top-clipped plot starts inside the image: its plane rows must follow
    ptr, pairs = next(x for x in images(prof) if x[1] == 16)
    a0 = image_key(ptr, 8, 1)
    cm = {'%04X' % a0: [mem0[a0], 'g', [7] * 8]}
    q = CobraPatch(prof, colours=cm)
    q.prepare(get0)
    ns = NextState(q)
    r = list(regs0)
    hl = scr_addr(10, 0)
    r[6], r[7], r[2], r[12], r[PC] = hl >> 8, hl & 255, pairs - 2, ptr + 24, 39865
    _hook_run(q, get0, ns, _alt(q), r, {PLOTEND})
    comp = ns.composite()
    good = all(comp.get((88 + bit, 4), 0) == 7 for bit in range(8))
    c['colour top clip ok' if good else 'colour top clip FAILED!'] += 1
    # a painted bullet
    if bullets(prof):
        e_ = bullets(prof)[0]
        cm = {'%04X' % e_: [mem0[e_], 'g', [6] * 8]}
        q = CobraPatch(prof, colours=cm)
        q.prepare(get0)
        ns = NextState(q)
        r = list(regs0)
        hl = scr_addr(12, 10)
        r[6], r[7], r[2], r[3], r[4], r[5], r[PC] = hl >> 8, hl & 255, e_ >> 8, (e_ + 1) & 255, mem0[e_ + 1], mem0[e_], 40714
        _hook_run(q, get0, ns, _alt(q), r, {40717})
        comp = ns.composite()
        good = all(comp.get((96 + b, y)) == 6 for b in range(8) for y in (10, 13))
        c['colour bullet ok' if good else 'colour bullet FAILED!'] += 1
    # start stub: waits for release, waits for a key, enters the game with interrupts off
    from skoolkit.simulator import Simulator
    mem = bytearray(65536)
    mem[START:START + len(START_CODE)] = START_CODE
    sim = Simulator(mem, {})
    R = sim.registers
    R[PC], R[26] = START, 1
    seq = iter([0xE0, 0xE0, 0xFF, 0xFF, 0xFF, 0xFE])    # held, held, released, none, none, a key

    class T_:
        def read_port(s, regs, port):
            return next(seq)

        def write_port(s, *x):
            pass
    sim.set_tracer(T_())
    n = 0
    while R[PC] != ENTRY and n < 200:
        sim.opcodes[mem[R[PC]]]()
        n += 1
    good = R[PC] == ENTRY and R[26] == 0 and next(seq, None) is None
    c['start stub (START_STUB, not in these builds) ok' if good else 'start stub FAILED!'] += 1
    mc, rows = clock_matrix(patch, states)
    c['clock matrix cases ok'] += sum(r['ok'] for r in rows)
    c['clock matrix sites'] = mc['sites']
    if not rows:
        c['clock matrix: no captured hook entries!'] += 1
    for k, v in mc.items():
        if k.endswith('!'):
            c['clock matrix: ' + k] += v
    if neg:
        for name, q in neg.items():
            altq = _alt(q)
            ns = NextState(q)
            det = False
            n = 0
            for rows, col, y in ((16, 10, 8), (8, 15, 62), (4, 20, 104)):
                n += 1
                if _plot_case(q, altq, mem0, regs0, ns, rows, col, y, n, c, 'neg'):
                    det = True
            if not det:
                det = any(k.endswith('!') for k in clock_matrix(q, states)[0])
            c['negative detected in unit (%s)' % name if det else 'negative not seen in unit (%s)' % name] += 1
    return c


def _clone(patch, edits, drop=()):
    """A broken copy: edits [(address, bytes)] in the alt ROM hooks, or in the hook page's code (0x4800-)."""
    import copy
    q = copy.copy(patch)
    rom = bytearray(patch.rom_code)
    pg = bytearray(patch.scratch0)
    for a, b in edits:
        if a >= 0x4000:
            pg[a - 0x4000:a - 0x4000 + len(b)] = b
            continue
        rom[a - ROM_ORG:a - ROM_ORG + len(b)] = b
    q.scratch0 = bytes(pg)
    q.rom_code = bytes(rom)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rom)] = rom
    q.page = bytes(page)
    q.sites = [s for s in patch.sites if s[0] not in drop]
    return q


def negative_patches(patch):
    s = patch.syms
    out = {}
    # ULA keeps figures, sprites never shown: the plot hook is not installed
    out['plot hook never runs'] = _clone(patch, [], drop=(39865,))
    out['bullet hook never runs'] = _clone(patch, [], drop=(40714,))
    # the hook jumps straight to its exit: no sprites
    d = s['plot_exit'] - (s['n_show'] + 2)
    out['no sprites shown'] = _clone(patch, [(s['n_show'], bytes([0x18, d]))])
    # sprites one row low
    out['sprites one row low'] = _clone(patch, [(s['n_y'] + 1, bytes([33]))])
    # body and dark swapped in the class table
    q = _clone(patch, [])
    q.scratch0 = page_image(patch.prof, a=2, b=1)
    q.classes = (2, 1)
    if getattr(patch, 'peek', None):
        q.store = store_pages(patch.peek, patch.prof, 2, 1)
    out['pixel classes swapped'] = q
    # the limiter never waits: pace_plot's JP hlib_pace_wait -> RET (hooklib.NEGATIVES "a limiter that never waits")
    out['limiter never waits'] = _clone(patch, [(s['dbt_open'] - 3, bytes([0xC9, 0, 0]))])
    # a stale store: every entry points at the next entry's patterns (optimise.pattern-cache: missing invalidation)
    q = _clone(patch, [])
    pg = bytearray(patch.scratch0)
    ent = [bytes(pg[PENT + 6 * k:PENT + 6 * k + 6]) for k in range(len(store_layout(patch.prof)))]
    for k, e in enumerate(ent):
        nxt = ent[(k + 1) % len(ent)]
        pg[PENT + 6 * k + 3:PENT + 6 * k + 6] = nxt[3:6]
    q.scratch0 = bytes(pg)
    out['store entries point at other images'] = q
    # hook loses register C
    out['hook loses a register'] = _clone(patch, [(s['n_c'], bytes(5))])
    # stale patterns: the cache key ignores the graphics address
    out['cache key ignores the graphics'] = _clone(patch, [(s['n_k1'], bytes(2)), (s['n_k2'], bytes(2))])
    # frame end hides nothing
    out['leftover sprites not hidden'] = _clone(patch, [(s['n_hide'] + 1, bytes([0x18]))])
    # a plane left mapped at slot 6 (only seen when something is painted: unit colour cases)
    # hook leaves its page mapped over the screen
    out['hook leaves slot 2 mapped'] = _clone(patch, [(s['n_map'] + 3, bytes([SCRPAGE]))])
    # every exit forces 3.5 MHz (the old convention): spd_out's LD A,(vspd) -> LD A,0 / NOP (patch.restore-speed)
    out['forced 3.5 MHz exit'] = _clone(patch, [(s['spd_out'] + 1, bytes([0x3E, 0x00, 0x00]))])
    return out


# nexclash/recolour.py: `python nexclash.py recolour cobra_sprites.nex PAINTED.png` (seconds, no rebuild): only the
# hook page's index and the colour planes change; the game never reads them.
NOTE = ('Cobra colour map (docs/COLOURS.md): key = graphics byte (hex address, one per preshifted phase; check = its '
        'value); 8 nibbles, 0 = default (1 white body, or the paper in MONO; 2 black; clear transparent); '
        'optional 4th = transparent mask')
RECOLOUR = {'game': 'cobra', 'output': 'sprites', 'colours': 'docs/profiles/cobra_colours.json', 'clear': True, 'note': NOTE}


def recolour(nex, cmap):
    """Built Cobra sprite .nex bytes + colour map -> (new .nex bytes, info). Refuses a .nex that is not this
    engine's build of the expected snapshot (sites, hook code, hook page, graphics)."""
    from .recolour import banks, nex_peek, splice
    have = banks(nex)
    need = set(COLOUR_BANKS) | {5, 2, 0, 12, 13}
    if not need <= set(have):
        raise ValueError('not a Cobra sprite build: banks %s missing' % sorted(need - set(have)))
    peek = nex_peek(nex)
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    got = colour_inputs_md5(peek, prof)
    if [want.get('md5'), want.get('bytes')] != list(got):
        raise ValueError('game graphics differ from the expected snapshot (%s / %d bytes, expected %s)' % (got[0], got[1], want))
    p = CobraPatch(prof, colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s hook' % a)
    if have[12] != p.page + bytes(8192):
        raise ValueError('alt ROM image / hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if have[13][:OVIDX] != page_image(prof)[:OVIDX]:
        raise ValueError('hook page differs from this version\'s (rebuild with nexclash.py auto)')
    p.prepare(peek)
    out, changed = splice(nex, {b: p.extra_banks[b] for b in (13,) + COLOUR_BANKS})
    info = {'banks changed': changed}
    info.update({k: v for k, v in p.cinfo.items() if v})
    return out, info


def image_part(get, ptr, pairs):
    """The coloursheet part of one image: every staging pixel: body code 1, dark code 2, transparent code 0."""
    px, ent = [], {}
    for y in range(2 * pairs):
        for col in range(3):
            a = image_key(ptr, y, col)
            m, g = get(a - 1), get(a)
            ent['%04X' % a] = [g, 'g']
            for bit in range(8):
                gb, mb = g >> (7 - bit) & 1, m >> (7 - bit) & 1
                code, dflt = (2, 2) if gb else ((0, 0) if mb else (1, 1))
                px.append((col * 8 + bit, y, '%04X' % a, bit, code, dflt))
    return {'id': '%04X:%d' % (ptr, pairs), 'size': 1, 'w': 24, 'h': 2 * pairs, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px,
            'entries': ent, 'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def bullet_part(get, e):
    px, ent = [], {}
    for y in range(4):
        a = e + (1 if y in (1, 2) else 0)
        g = get(a)
        ent['%04X' % a] = [g, 'g']
        for bit in range(8):
            gb = g >> (7 - bit) & 1
            px.append((bit, y, '%04X' % a, bit, 2 if gb else 1, 2 if gb else 1))
    return {'id': 'B%04X' % e, 'size': 1, 'w': 8, 'h': 4, 'x': 0, 'y': 0, 'mir': 0, 'pixels': px, 'entries': ent,
            'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def capture(rzx_paths):
    """The images and bullets the recordings draw (C simulator): ({(start, pairs): count}, {E address: count})."""
    from . import rzx as RZ
    seen, bul = collections.Counter(), collections.Counter()

    def on(pc, sim):
        R = sim.registers
        if pc == 39864:
            seen[(R[12], R[0])] += 1
        elif pc == 39810:
            seen[(R[12], R[2], 'clip')] += 1
        else:
            bul[(R[2] << 8 | R[3]) - 1] += 1
    for r in rzx_paths:
        RZ.trace(r, [39864, 39810, 40714], on)
    return seen, bul


def sheets(z80, out_dir, prefix='cobra', colours=None, say=print):
    """The colour sheets: <prefix>_PAINTING_SPRITES.png (the fewest whole figures showing every graphics byte) +
    _REFERENCE_ALL_SPRITES.png, each with its _layout.json. One figure per image and preshifted phase."""
    from . import coloursheet as cs
    from skoolkit.snapshot import Snapshot
    mem = Snapshot.get(z80).memory
    get = lambda a: mem[a & 0xFFFF]
    prof = load_profile()
    comps = [{'count': 1, 'group': 0, 'parts': [image_part(get, p, n)]} for p, n in images(prof)]
    comps += [{'count': 1, 'group': 0, 'parts': [bullet_part(get, e)]} for e in bullets(prof)]
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(PALETTE)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get, prof)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, paint_clear=True, identity=ident)
    say('Sheets    : %d images + bullets; painting sheet %d figures, reference %d' % (len(comps), n1, n2))
    return n1, n2


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : cobra (Cobra: masked plotter 39865 and bullets -> sprites; full redraw stays on the ULA)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    pp = PlainPatch()
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=pp)
    bad = check(plain, z80, pp, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CobraPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        cc, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in cc.items() if k.endswith('!')}
        ok = ok and not fails
        est = cc['T patched for those plots']
        say('Verify    : %s  %d frames (colour %d, mono %d), plot %d (top clip %d), bullet %d, frame %d/%d, round %d, '
            'text %d+%d, star reads %d, %d picture pixels -> %s' % (
                os.path.basename(r), cc['frames'], cc['frames colour'], cc['frames mono'], cc['plot'],
                cc['plot top clip'], cc['bullet'], cc['frame'], cc['frame end'], cc['round'], cc['text 45046'],
                cc['text 45731'], cc['star reads'], cc['picture pixels compared'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Cache     : %s  plots that uploaded patterns %d of %d' % (os.path.basename(r), cc['plot uploads (cache misses)'], cc['plot']))
        say('Clash     : %s  body pixels the original showed in another colour %d, in this colour %d' % (
            os.path.basename(r), cc['body pixels the original showed in another colour'],
            cc['body pixels the original showed in this colour']))
        say('Speed     : %s  plots: original %d T, patched %d T (estimate: fast T / 6 + slow T), plot bytes below the play area %d (panel rows %d)' % (
            os.path.basename(r), cc['T original plot'], est, cc['plot bytes below the play area'], cc['plot bytes in the panel rows (y >= 152)']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())), 'PASS' if not uf else 'FAIL %s' % uf))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
