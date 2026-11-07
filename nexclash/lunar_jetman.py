"""Lunar Jetman (Ultimate Play The Game, 1983, 48K) - engine `lunar_jetman`.

Figures leave the ULA: the XOR stores of the two figure plotters are NOPs (one byte for one, the
plot code still runs), the object colour painters are NOPs, and every object's current image is
shown as hardware sprites from images precomputed at build time (ink, black fill for enclosed
paper, one-pixel outline). Hooks in alt ROM image 1 (0x386E-); state and images in Next pages
mapped at slot 4 only while a hook runs. See games/lunar_jetman.md.
"""
import os, json

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
OBJ0, OBJSZ, NOBJ = 0x6078, 24, 27
TRUCKS = (0x6090, 0x6180)
GTAB1, GTAB2 = 47812, 61054
STATE_PAGE = 26          # bank 13 lower: caches + graphic lists
IDX_PAGE = 27            # figure graphic & 0x1FFF -> id + 1
TP0 = 28                 # truck images, 6 per page (1280 bytes each)
FP0 = 36                 # figure images, 16 per page (512 bytes each)
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
WHITE_INKS = (7, 15)

# (address, original, new, hook symbol or None)
SITES = [
    (34558, '0ec9', None, 'h_new'),        # LD C,0 / RET (end of the plotter's new-image setup) -> JP
    (34462, '0ec9', None, 'h_clr'),        # LD C,0 / RET (object left the window: state cleared)
    (34368, 'af32595e', None, 'h_eo'),     # XOR A / LD (24153),A (erase-only entry)
    (34383, 'af32595e', None, 'h_teo'),    # XOR A / LD (24153),A (truck erase-only entry)
    (34958, '0ec9', None, 'h_tnew'),       # LD C,0 / RET (end of the truck plotter's setup)
    (34011, 'cdad84', None, 'h_cls'),      # CALL 33965 (pixel clear of the whole screen, 34008)
    (35749, '21bf57', None, 'h_msg'),      # LD HL,22463 (entry of the play-area clear: missile warning, new screens)
]
SITES[0] = (34558, '0e00c9', None, 'h_new')
SITES[1] = (34462, '0e00c9', None, 'h_clr')
SITES[4] = (34958, '0e00c9', None, 'h_tnew')
SITE_OP = {'h_cls': 0xCD}
STORE_NOPS = [34245, 34249, 34282, 34286, 34290, 34314, 34318, 34755, 34793]   # LD (HL),A figure XOR
PAINT_NOPS = [(34663, 0x72), (35127, 0x72), (35104, 0x77)]                    # object colour over cells
INTERIORS = (34559, 34560, 34463, 34464, 34369, 34370, 34371, 34384, 34385, 34386, 34959, 34960,
             34012, 34013, 35750, 35751)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, '..')


def _profile_path():
    return os.path.join(_ROOT, 'docs', 'profiles', 'lunar_jetman.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_lunar_jetman(snap):
    try:
        ram = snap.ram()
    except Exception:
        return False
    if len(ram) != 49152:
        return False
    m = bytes(16384) + bytes(ram)
    ok = lambda m: all(m[a:a + len(bytes.fromhex(o))] == bytes.fromhex(o) for a, o, _, _ in SITES)
    if ok(m):
        return True
    # the file's own state at the decrypter (the build input, rzx/s_pre.z80): the sites after decryption
    return m[0x5B80:0x5B80 + len(DECRYPTER)] == DECRYPTER and ok(decrypt(m)[0])


def w16(m, a):
    return m[a] | m[a + 1] << 8


# The tape's code is stored nibble-rotated: the printer-buffer decrypter at 0x5B80 (XOR A; RRD from 0x7FFF up,
# 0x7C00 bytes; JP 0x8000) restores it at the start. A build from the archive file (stopped at 0x5B80) keeps it so:
# the patched bytes are written in the same rotation, so the decrypter yields the patched game, and the file and
# the .nex differ only where the patch does.
CRYPT_LO, CRYPT_N = 0x7FFF, 0x7C00
DECRYPTER = bytes.fromhex('21ff7f017c00afed67231 0fb0d20f8c30080'.replace(' ', ''))


def decrypt(m):
    """m: 64K image (encrypted) -> decrypted copy (and A's low nibble left over)."""
    d = bytearray(m)
    a = 0
    for i in range(CRYPT_N):
        x = CRYPT_LO + i
        old = m[x]
        d[x] = (a << 4 | old >> 4) & 0xFF
        a = old & 15
    return d, a


def encrypt(d, last_lo):
    e = bytearray(d)
    for i in range(CRYPT_N):
        x = CRYPT_LO + i
        nxt = d[x + 1] >> 4 if i + 1 < CRYPT_N else last_lo
        e[x] = (d[x] & 15) << 4 | nxt
    return e


def graphic_lists(m):
    t1 = [w16(m, GTAB1 + 2 * i) for i in range(255)]
    t2 = [w16(m, GTAB2 + 2 * i) for i in range(30)]
    # every graphic in the truck plotter's format ([W <= 8, H <= 30]): the rover's frames (types 18-41) and the
    # destroyed rover's debris (types 224-226, drawn by the truck plotter on record 0x6090)
    trucks = sorted({p for p in t1 if p >= 0x8000 and 1 <= m[p] <= 8 and 1 <= m[p + 1] <= 30})
    figs = sorted({p for p in t1 + t2 if p >= 0x8000 and 1 <= m[p] <= 30})
    return figs, trucks


def _shape(ink, Wd, Hd, outline=True):
    """ink: set of (x, y) in a Wd x Hd box -> {(x, y): code} 1 ink, 2 enclosed paper, 3 outline."""
    out = {p: 1 for p in ink}
    ext = set()
    todo = [(x, y) for x in range(Wd) for y in (0, Hd - 1)] + [(x, y) for y in range(Hd) for x in (0, Wd - 1)]
    while todo:
        p = todo.pop()
        if p in ext or p in ink or not (0 <= p[0] < Wd and 0 <= p[1] < Hd):
            continue
        ext.add(p)
        x, y = p
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    for x in range(Wd):
        for y in range(Hd):
            if (x, y) not in ink and (x, y) not in ext:
                out[(x, y)] = 2
    if outline and len(ink) >= 12:
        solid = set(out)
        for (x, y) in list(ext):
            if any((x + dx, y + dy) in solid for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                out[(x, y)] = 3
    return out


def fig_image(m, p):
    """32 x 32 image (outline margin 1): graphic rows bottom first, 2 bytes per row."""
    H = m[p]
    ink = set()
    for k in range(H):
        r = 1 + (H - 1 - k)
        for j in range(2):
            b = m[p + 1 + 2 * k + j]
            for i in range(8):
                if b & (0x80 >> i):
                    ink.add((1 + 8 * j + i, r))
    return _shape(ink, 32, 32), H


def truck_image(m, p):
    """80 x 32 image: W bytes x H rows, bottom row first; bottom 16 rows bright white, rest bright cyan."""
    W, H = m[p], m[p + 1]
    ink = {}
    for k in range(H):
        r = 1 + (H - 1 - k)
        for j in range(W):
            b = m[p + 2 + k * W + j]
            for i in range(8):
                if b & (0x80 >> i):
                    ink[(1 + 8 * j + i, r)] = 15 if k < 16 else 13
    sh = _shape(set(ink), 80, 32)
    out = {}
    for q, c in sh.items():
        out[q] = ink[q] if c == 1 else (8 if c == 2 else 8)     # fill black; outline black (white figure)
    return out, W, H


def patterns(img, cols, rows):
    """{(x, y): nibble} -> 4-bit patterns, row-major tiles."""
    out = bytearray()
    for tr in range(rows):
        for tc in range(cols):
            for y in range(16):
                for x in range(0, 16, 2):
                    a = img.get((16 * tc + x, 16 * tr + y), 0)
                    b = img.get((16 * tc + x + 1, 16 * tr + y), 0)
                    out.append(a << 4 | b)
    return bytes(out)


def build_data(m):
    """-> (state page, {page: bytes}, info)"""
    figs, trucks = graphic_lists(m)
    pages = {}
    st = bytearray(8192)
    # 0x0000: figure caches (NOBJ), 0x0020: truck caches (2); 0x0040: figure list; 0x0400: truck list
    o = 0x40
    for p in figs:
        st[o:o + 2] = p.to_bytes(2, 'little'); o += 2
    assert o < 0x400
    o = 0x400
    for p in trucks:
        st[o:o + 2] = p.to_bytes(2, 'little'); o += 2
    idx = bytearray(8192)
    for k, p in enumerate(figs):
        assert idx[p & 0x1FFF] == 0, 'index collision at %x' % p
        idx[p & 0x1FFF] = k + 1
    pages[IDX_PAGE] = idx
    for k, p in enumerate(figs):
        img, H = fig_image(m, p)
        img = {q: c for q, c in img.items()}
        pat = patterns(img, 2, 2)
        pg = FP0 + k // 16
        pages.setdefault(pg, bytearray(8192))[(k % 16) * 512:(k % 16) * 512 + 512] = pat
    for k, p in enumerate(trucks):
        img, W, H = truck_image(m, p)
        pat = patterns(img, 5, 2)
        pg = TP0 + k // 6
        pages.setdefault(pg, bytearray(8192))[(k % 6) * 1280:(k % 6) * 1280 + 1280] = pat
    assert max(pages) < 96 and FP0 + (len(figs) - 1) // 16 < 96 and TP0 + (len(trucks) - 1) // 6 < FP0
    return bytes(st), {k: bytes(v) for k, v in pages.items()}, {'figs': figs, 'trucks': trucks}


RGB = [(0, 0, 0), (0, 0, 0xD7), (0xD7, 0, 0), (0xD7, 0, 0xD7), (0, 0xD7, 0), (0, 0xD7, 0xD7), (0xD7, 0xD7, 0), (0xD7, 0xD7, 0xD7),
       (0, 0, 0), (0, 0, 0xFF), (0xFF, 0, 0), (0xFF, 0, 0xFF), (0, 0xFF, 0), (0, 0xFF, 0xFF), (0xFF, 0xFF, 0), (0xFF, 0xFF, 0xFF)]
# Enhanced fixed entries 6-15 of every block: Jetman's suit and pack as the Spec256 Jetpac paints him
FIXED = [(255, 190, 97), (255, 157, 60), (255, 117, 28), (255, 72, 0), (202, 48, 48),
         (198, 198, 198), (170, 170, 170), (141, 141, 141), (255, 255, 255), (90, 90, 90)]
# Enhanced truck (block 0): 1-3 cyan light/mid/dark, 4 white, 5-7 grey light/mid/dark, 8 black, 9 blue,
# 10 wheel fill, 11 body fill (8, 10, 11 are never ink)
TRUCK_ENH = [None, (150, 255, 255), (0, 215, 215), (0, 130, 150), (255, 255, 255), (200, 200, 200), (140, 140, 140),
             (80, 80, 80), (0, 0, 0), (40, 90, 220), (70, 70, 70), (0, 110, 130)]
TRUCK_FILL = (8, 10, 11)


def rgb8(c):
    r, g, b = c
    return (round(r * 7 / 255) << 5) | (round(g * 7 / 255) << 2) | round(b * 3 / 255)


def dark(c, k=0.5):
    return tuple(int(v * k) for v in c)


def light(c, k=0.45):
    return tuple(int(v + (255 - v) * k) for v in c)


def palette(enhanced=False):
    if enhanced:
        return palette_enh()
    return _palette_default()


def _palette_default():
    """256 sprite palette bytes. Block 0: the trucks. Block p (1-15, the object's ink + 8 * bright):
    1 = colour p, 2 = its darker shade (enclosed paper: a solid body), 3 = outline (white; black for
    a white figure); Enhanced adds 4 = dark shade, 5 = light shade, 6-15 FIXED."""
    pal = [0xE3] * 256
    for i in range(16):
        pal[i] = SPECCY[i]
    for p in range(1, 16):
        c = RGB[p] if p != 8 else (40, 40, 40)
        pal[16 * p + 1] = rgb8(c) if p != 8 else 0x00
        pal[16 * p + 2] = rgb8(dark(c, 0.45))
        pal[16 * p + 3] = 0x00 if p in WHITE_INKS else 0xFF
    pal[0] = 0xE3
    for b in range(16):
        pal[16 * b] = 0xE3
    return bytes(pal)


def colour_offset(attr):
    p = (attr & 7) | ((attr & 64) >> 3)
    return p or 8


class LunarJetmanPatch:
    name = 'Lunar Jetman figures -> hardware sprites (altrom hooks, stores NOP)'

    def __init__(self, prof=None, enhanced=False, encrypted=False, j256=None):
        self.enhanced = enhanced
        self.j256 = j256 or J256
        self.encrypted = encrypted
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        dp = palette(False)
        i = self.stub_extra.find(dp)
        if i < 0:
            raise ValueError('setup does not hold the default palette (asm/lunar_jetman_palette.asm stale)')
        if enhanced:
            self.stub_extra = self.stub_extra[:i] + palette(True) + self.stub_extra[i + 256:]
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 128
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build: Sinclair's 48K ROM + hooks (2026-11-04, altrom_audit). The Next's
        # stub fills image 1 from the system ROM3 first, which is NextZXOS's: its IM 1 handler CALLs 0x386E (0x004A)
        # and its UDG print JPs to 0x387E (0x0B52), both into these hooks. Writing only 0x386E.. was safe only while
        # NextZXOS's DivMMC trap takes every 0x0038. altrom_low = Sinclair 0x0000-0x1FFF, in page 25 (bank 12, upper).
        self.altrom = (0x2000, 0x4000)
        self.hook_range = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.sites = []
        for a, old, _, sym in SITES:
            self.sites.append((a, bytes.fromhex(old), bytes([SITE_OP.get(sym, 0xC3)]) + self.syms[sym].to_bytes(2, 'little')))
        for a in STORE_NOPS:
            self.sites.append((a, b'\x77', b'\x00'))
        for a, o in PAINT_NOPS:
            self.sites.append((a, bytes([o]), b'\x00'))
        self.extra_banks = {}

    def apply(self, snap):
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        if self.encrypted:
            if bytes(ram[0x5B80 - 0x4000:0x5B80 - 0x4000 + len(DECRYPTER)]) != DECRYPTER:
                raise ValueError('no decrypter at 0x5B80')
            enc = bytes(0x4000) + bytes(ram)
            dec, lo = decrypt(enc)
            ram = bytearray(dec[0x4000:])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + self.max_tail]):
            raise ValueError('printer buffer 0x5B00-0x5B7F is not empty')
        m0 = bytes(0x4000) + bytes(ram)
        self.state, self.pages, self.info = build_data_enh(m0, self.j256) if self.enhanced else build_data(m0)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        if self.encrypted:
            e2 = encrypt(bytes(0x4000) + bytes(ram), lo)
            if decrypt(e2)[0][0x4000:] != bytes(ram):
                raise ValueError('re-encryption does not round-trip')
            ram = bytearray(e2[0x4000:])
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        banks = {12: self.page + (self.altrom_low[1] if getattr(self, 'altrom_low', None) else bytes(8192))}
        allp = dict(self.pages)
        allp[STATE_PAGE] = self.state
        for pg, data in allp.items():
            b = pg // 2
            cur = bytearray(banks.get(b, bytes(16384)))
            cur[(pg & 1) * 8192:(pg & 1) * 8192 + 8192] = data
            banks[b] = bytes(cur)
        self.extra_banks = banks


def rom3():
    """The system ROM3 the Next pages as ROM 3: NextZXOS's (the last 16K of enNextZX.rom, MD5 8c34d957, from the
    card's /machines/next) via $NEXCLASH_NEXT_ROM / --next-rom (nextboot.system_rom3, imported 2026-11-04: the
    pilot read $NEXCLASH_ROM3 or its work/rom); without it Sinclair's ROM stands in (rom3left then undetectable)."""
    from .nextboot import system_rom3
    return system_rom3()[0]


def alt_image(patch):
    """The alt ROM image as the Next's stub fills it (z80tonex.altrom_fill): the SYSTEM ROM3 copied first (NextZXOS's,
    with code at 0x386E-0x3CFE that its IM 1 handler and UDG print call), then bytes lo..hi of the patch page, then
    altrom_low over 0x0000-0x1FFF."""
    alt = bytearray(rom3())
    lo, hi = patch.altrom
    alt[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    low = getattr(patch, 'altrom_low', None)
    if low:
        alt[0:0x2000] = low[1]
    return bytes(alt)


def alt_outside_hooks(patch):
    """Addresses of the alt ROM image, outside the hook bytes, that are not Sinclair's 48K ROM (empty = whole image)"""
    from .build import rom48
    alt, rom = alt_image(patch), rom48()
    h0, h1 = getattr(patch, 'hook_range', patch.altrom)
    return [a for a in range(0x4000) if not h0 <= a < h1 and alt[a] != rom[a]]


def rom3_left(patch):
    """The build before 2026-11-04 (b0fde37e/ee41fbe1): only the hook bytes 0x386E.. written over NextZXOS's ROM3"""
    patch.altrom = patch.hook_range
    patch.altrom_low = None
    return patch


# ---------------------------------------------------------------------------------------------
# Build and auto (imported 2026-11-04: the pilot built with work/build2.py, loading/work/mknex.py and
# packed with work/pack2.sh; the same bytes). Inputs beside the snapshot (the record lists them with the
# recordings): the snapshot = the archive file's own state at the decrypter (rzx/s_pre.z80), S0_NAME the
# stepped start (plain build, verifier), LOADING the tape's screen, J256_NAME the Spec256 Jetpac (Enhanced).
# ---------------------------------------------------------------------------------------------

S0_NAME = 'lunar_jetman_s0.z80'
LOADING = 'lunar_jetman.scr'
LOAD_BANK = 34


def loading_nex(nex, scr):
    """A sprite build with the tape's loading screen (the approved .nxc's builds): bank 5's screen area holds the
    picture, bank 34 (asm loading: the hold, then bank 5's own screen put back) is the entry bank."""
    h = load_profile()['hooks']
    o = bytes(nex)
    if len(scr) != 6912:
        raise ValueError('loading screen: %d bytes, want 6912' % len(scr))
    hd = bytearray(o[:512])
    if hd[18 + LOAD_BANK] or hd[139] != 10:
        raise ValueError('not a lunar_jetman sprite build: bank 34 in use or entry bank %d' % hd[139])
    code, end = bytes.fromhex(h['loading']), bytes.fromhex(h['loadend'])
    stub = code + o[512:512 + 6912]
    stub += bytes(0x4000 - len(end) - len(stub)) + end
    hd[9] += 1
    hd[18 + LOAD_BANK] = 1
    hd[139] = LOAD_BANK
    off, parts = 512, []
    for k in [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112)):     # bank order in the file: 34 among the others
        if k == LOAD_BANK:
            parts.append(stub)
        elif o[18 + k]:
            parts.append(o[off:off + 16384])
            off += 16384
    body = b''.join(parts)
    return bytes(hd) + scr + body[6912:] + o[off:]


DECRYPT_STEPS = 400000         # the file's decrypter takes 95,484 instructions to 0x8000
# s0 was stepped in an emulator with interrupts on (IM 1): the ROM's handler ran during the decrypter and left its
# footprint, which the shipped build's run (no interrupts here) cannot reproduce: the keyboard state KSTATE
# 0x5C00-0x5C07, LAST_K 0x5C08, FLAGS 0x5C3B, FRAMES 0x5C78-0x5C7A, and the dead stack below s0's SP (the handler's
# pushes). Only these may differ; any other byte is a decrypter MISMATCH.
ISR_VARS = set(range(0x5C00, 0x5C09)) | {0x5C3B} | set(range(0x5C78, 0x5C7B))
ISR_STACK = 0x20               # dead stack bytes below s0's SP the handler may have written


def decrypt_check(z80, s0, steps=DECRYPT_STEPS, mutate=None):
    """The shipped build starts at the file's own decrypter: the patched encrypted memory, run through it to
    0x8000 (at most steps instructions), against s0 + the patch sites. mutate(mem): a negative control's change before
    the run. -> (instructions or None if 0x8000 was never reached, differing addresses, accepted addresses: the IM 1
    handler's footprint in s0, ISR_VARS + ISR_STACK)."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simulator import Simulator
    ram = bytes(Snapshot.get(z80).ram())

    class S:
        banks = {5: ram[:16384], 2: ram[16384:32768], 0: ram[32768:]}
    q = LunarJetmanPatch(encrypted=True)
    sn = S()
    q.apply(sn)
    mem = bytearray(16384) + bytearray(sn.banks[5] + sn.banks[2] + sn.banks[0])
    if mutate:
        mutate(mem)
    sim = Simulator(mem, {})
    R = sim.registers
    R[24] = 0x5B80
    n = 0
    while R[24] != 0x8000:
        if n >= steps:
            return None, [], []
        sim.opcodes[mem[R[24]]]()
        n += 1
    ss = Snapshot.get(s0)
    want = bytearray(bytes(16384) + bytes(ss.ram()))
    for a, old, new in LunarJetmanPatch().sites:
        want[a:a + len(new)] = new
    diff = [a for a in range(0x4000, 0x10000) if mem[a] != want[a]]
    ok = ISR_VARS | set(range(ss.sp - ISR_STACK, ss.sp))
    return n, [a for a in diff if a not in ok], [a for a in diff if a in ok]


def decrypt_negatives(z80, s0):
    """Negative controls the decrypter check must catch: one encrypted byte of the game changed (a wrong decrypted
    byte), and the decrypter's final JP 0x8000 made a jump to itself (it never ends: the step bound stops it).
    -> {name: detected}"""
    def wrong_byte(mem):
        mem[0x9000] ^= 0x10

    def endless(mem):
        mem[0x5B8F:0x5B92] = bytes([0xC3, 0x8F, 0x5B])
    out = {}
    for name, f in (('a wrong decrypted byte', wrong_byte), ('a decrypter that never reaches 0x8000', endless)):
        n, d, _ = decrypt_check(z80, s0, mutate=f)
        out[name] = n is None or bool(d)
    return out


def decrypt_line(z80, s0):
    """-> (ok, the report's Decrypter line)."""
    n, d, acc = decrypt_check(z80, s0)
    negs = decrypt_negatives(z80, s0)
    ok = n is not None and not d and all(negs.values())
    if n is None:
        head = 'MISMATCH: the decrypter did not reach 0x8000 in %d instructions' % DECRYPT_STEPS
    elif d:
        head = '%d instructions to 0x8000; MISMATCH: differs from %s + the sites at %d bytes (%s)' % (
            n, S0_NAME, len(d), ', '.join('0x%04X' % a for a in d[:16]))
    else:
        head = '%d instructions to 0x8000; equals %s + the sites' % (n, S0_NAME)
    head += ' (accepted: %d bytes of the IM 1 handler\'s footprint in %s, KSTATE / FRAMES / dead stack)' % (len(acc), S0_NAME)
    head += '; negatives %d/%d DETECTED%s' % (sum(negs.values()), len(negs), '' if all(negs.values()) else ' - MISMATCH: '
                                              + ', '.join(k for k, v in negs.items() if not v) + ' NOT DETECTED')
    return ok, head


def enhanced_inputs(j256):
    return os.path.exists(j256) and os.path.exists(pal_path(j256))


def build(z80, out, name, say=print):
    import hashlib
    from .z80tonex import convert
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    here = os.path.dirname(os.path.abspath(z80))
    s0, scr, j256 = (os.path.join(here, x) for x in (S0_NAME, LOADING, J256_NAME))
    ok = True
    if os.path.exists(s0):
        plain = os.path.join(out, name + '.nex')
        c = convert(s0, plain, None, True, quiet=True)
        bad = check(plain, s0, None, (c[1], c[1] + len(c[2])))
        ok = ok and not bad
        say('Plain     : %s  %s  boot %s  (from %s)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300], S0_NAME))
        dok, line = decrypt_line(z80, s0)
        ok = ok and dok
        say('Decrypter : ' + line)
    else:
        say('Plain     : no %s beside the snapshot: no plain build, no decrypter check' % S0_NAME)
    sets = [('sprites', False)] + ([('enhanced', True)] if enhanced_inputs(j256) else [])
    if len(sets) == 1:
        say('Enhanced  : no %s beside the snapshot: no Enhanced build' % ' + '.join(
            n for n, p in ((J256_NAME, j256), (PAL_NAME, pal_path(j256))) if not os.path.exists(p)))
    for tag, enh in sets:
        p = LunarJetmanPatch(enhanced=enh, encrypted=True, j256=j256)
        f = os.path.join(out, '%s_%s.nex' % (name, tag))
        convert(z80, f, patch=p, quiet=True)
        bad = check(f, z80, patch=p, tail=(0x5B00, 0x5B80))
        ok = ok and not bad
        say('%-10s: %s  %s  boot %s' % (tag.capitalize(), os.path.basename(f), md5(f), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
        if os.path.exists(scr):
            ld = f[:-4] + '_loading.nex'
            open(ld, 'wb').write(loading_nex(open(f, 'rb').read(), open(scr, 'rb').read()))
            say('Loading   : %s  %s  (the tape\'s screen held by bank 34 until a key or 5 s)' % (os.path.basename(ld), md5(ld)))
    return ok, s0, j256


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]     # registers verify() compares (not R, T, MEMPTR)


def unit_tests(patch=None, states=(), neg=None):
    """Cases no recording reaches: the setup routine's palette for both sets run against the shipped one, the whole
    alt ROM image (no byte outside the hooks that is not Sinclair's), the encrypt / decrypt round trip of the sites;
    negative control: the previous fill (rom3_left) must show NextZXOS ROM3 bytes outside the hooks. -> (Counter, [])."""
    import collections
    from skoolkit.simulator import Simulator
    from . import z80n
    from .nextboot import system_rom3
    c = collections.Counter()
    for enh in (False, True):
        p = LunarJetmanPatch(enhanced=enh)
        mem = bytearray(65536)
        mem[0xD000:0xD000 + len(p.stub_extra)] = p.stub_extra
        mem[0xCFFE:0xD000] = b'\xff\xff'
        sim = Simulator(mem, {})
        R = sim.registers
        R[24], R[12] = 0xD000, 0xCFFE
        pal, nr = [], {}

        def nx(r, v):
            nr[r] = v
            if r == 0x41:
                pal.append(v)
        z80n.install(sim, nx)
        n = 0
        while R[24] != 0xFFFF and n < 200000:
            sim.opcodes[mem[R[24]]]()
            n += 1
        c['setup cases'] += 1
        if bytes(pal) != palette(enh) or nr.get(0x43) != 0x20 or nr.get(0x4B) != 0 or nr.get(0x15) != 1:
            c['setup palette%s!' % (' (Enhanced)' if enh else '')] += 1
        if alt_outside_hooks(p):
            c["alt ROM image bytes outside the hooks not Sinclair's!"] += 1
    rom3 = system_rom3()
    if 'NOT modelled' not in rom3[1]:
        c['negative control cases'] += 1
        if alt_outside_hooks(rom3_left(LunarJetmanPatch())):
            c['negative control detected'] += 1
        else:
            c['negative control (rom3_left) NOT DETECTED!'] += 1
    return c, []


def auto(a, z80, name, out, say):
    import time
    say('Game      : %s' % name)
    say('Engine    : lunar_jetman (XOR stores and colour painters NOP; every object a sprite from build-time images)')
    ok, s0, j256 = build(z80, out, name, say)
    from .nextboot import rom_model
    rzxs = list(a.rzx or [])
    stop = getattr(a, 'quick', None)
    if rzxs:
        say('ROM model : %s' % rom_model())
    enh_ok = enhanced_inputs(j256)

    def one(r, n, neg, enh):
        t = time.time()
        c, ex, fr, err = verify(r, s0, stop=n, neg=neg, enh=enh, j256=j256)
        f = {k: v for k, v in c.items() if k.endswith('!')}
        return c, ex, fr, err, f, time.time() - t
    for r in rzxs:
        for enh in (False, True) if enh_ok else (False,):
            c, ex, fr, err, f, dt = one(r, stop, None, enh)
            ok = ok and not f and not err
            say('Verify    : %s%s  %d frames%s, %d hook calls, %d objects equal, %d IM 1 handlers, %.0fs -> %s' % (
                'Enhanced ' if enh else '', os.path.basename(r), fr, ' (%s)' % err if err else '',
                sum(v for k, v in c.items() if k.startswith('hook ')), c['objects equal'], c['IM 1 handlers compared'],
                dt, 'IDENTICAL' if not f else 'FAILED %s %s' % (f, {k: ex[k][:2] for k in f})))
    u, _ = unit_tests()
    uf = {k: v for k, v in u.items() if k.endswith('!')}
    ok = ok and not uf
    say('Unit      : %d setup cases (palette, alt ROM image), negative control %d/%d -> %s' % (
        u['setup cases'], u['negative control detected'], u['negative control cases'], 'PASS' if not uf else 'FAIL %s' % uf))
    if rzxs and not stop:
        r = rzxs[0]
        det = tot = 0
        for enh, negs in ((False, NEGATIVES), (True, NEGATIVES_ENH if enh_ok else ())):
            for neg in negs:
                tot += 1
                c, ex, fr, err, f, dt = one(r, 700, neg, enh)
                det += bool(f)
                say('Negative  : %-10s%s %s' % (neg, ' Enhanced' if enh else '', 'DETECTED on %s (700 frames) %s' % (
                    os.path.basename(r), str(f)[:120]) if f else 'NOT DETECTED'))
        ok = ok and det == tot
        say('Negatives : %d of %d DETECTED' % (det, tot))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Enhanced set (second version, 2026-11-04): every figure painted by its parts from one shared
# 15-colour sprite palette (the same 16 entries in every block, so the colour comes from the image,
# not the object's attribute). Jetman's suit from the Spec256 Jetpac (two frames byte-identical with
# Jetpac's); visor, pack and flame by part. Each alien family its own body colours with its features
# (the paper it encloses, its small separate pieces) in a contrasting colour. Same silhouettes,
# outlines and fills as the default build (build_data_enh checks every tile's opaque mask).
# No white outline and no white edge (owner, 2026-11-04): the play area is black, so the one-pixel
# outline is painted black (it still masks the scenery behind, as in the default build), and white is
# kept only inside a figure (eyes, the pod's window, a canister's body, a blast's core), never on a
# pixel that touches the outside (_no_white_edge). No family paints ink black any more: without the white
# rim a black shade vanished into the black play area, so the dark shade is now the family's darker colour.
# ---------------------------------------------------------------------------------------------
J256 = os.environ.get('NEXCLASH_JETPAC256')     # the Spec256 Jetpac.256 (game data, never in the repo); build(): beside the snapshot
J256_NAME = 'Jetpac.256'
PAL_NAME = 'spec256-palette.pal'                 # Spec256-Games' palette (licence not established: never in the repo)
PAL_MD5 = 'b095dc99a047bab844b87b06657b0a7a'
JET_TEMPLATES = {0xBCC2: 0x79AD, 0xBDA3: 0x7AA9}     # Lunar Jetman graphic -> Jetpac address
JETMAN = range(0xBCC0, 0xBE94)                       # Jetman's frames (types 1-17)
# shared Enhanced palette, index: colour. OUTLINE is black like BLACK but its own index, so a tile holding only
# a figure's outline never equals a tile holding only the rover's black outline (the verifier maps each
# Enhanced tile back to one default tile); it took the place of brown (the ringed planets' shade, now DRED).
EP = [None, (0, 0, 0), (255, 255, 255), (190, 190, 200), (90, 90, 100), (255, 230, 40), (255, 140, 20), (220, 30, 30),
      (120, 10, 20), (130, 255, 90), (20, 150, 40), (0, 220, 240), (30, 70, 220), (210, 60, 230), (0, 0, 0),
      (255, 200, 140)]
BLACK, WHITE, LGREY, DGREY, YELLOW, ORANGE, RED, DRED, LGREEN, DGREEN, CYAN, BLUE, MAGENTA, OUTLINE, SKIN = range(1, 16)
# family: (light, body, dark, feature, small pieces)   by type ranges of the two graphic tables
FAMILY = [
    ('a', 1, 17, 'jetman'), ('a', 220, 223, 'jetman'),
    ('a', 42, 45, (LGREY, WHITE, DGREY, RED, RED)),            # canisters: silver, red bands
    ('a', 46, 63, (LGREY, LGREY, DGREY, RED, YELLOW)),         # guns / dishes of the base
    ('a', 64, 71, (CYAN, BLUE, DGREY, YELLOW, YELLOW)),        # flying saucers with lights
    ('a', 72, 87, (ORANGE, RED, DRED, YELLOW, YELLOW)),        # tumbling blobs and eggs
    ('a', 88, 91, (LGREY, LGREY, DGREY, ORANGE, ORANGE)),      # debris
    ('a', 92, 99, 'blast'), ('a', 100, 101, (LGREY, LGREY, DGREY, ORANGE, ORANGE)),
    ('a', 128, 135, 'missile'), ('a', 136, 143, (LGREEN, DGREEN, DGREEN, YELLOW, YELLOW)),  # spinning green cubes
    ('a', 144, 151, (MAGENTA, BLUE, BLUE, YELLOW, RED)),       # bug robots
    ('a', 152, 159, (LGREY, LGREY, DGREY, RED, YELLOW)),       # towers of the base
    ('a', 160, 167, 'missile'),
    ('a', 168, 175, (ORANGE, RED, DRED, YELLOW, YELLOW)),      # red spinning balls
    ('a', 176, 183, (CYAN, BLUE, BLUE, WHITE, YELLOW)),        # pods
    ('a', 184, 191, (LGREEN, DGREEN, DGREEN, RED, YELLOW)),    # saucers with legs
    ('a', 192, 203, 'spark'), ('a', 204, 219, (SKIN, ORANGE, DRED, BLUE, CYAN)),      # ringed planets
    ('a', 224, 235, 'blast'), ('a', 236, 239, (RED, DRED, DRED, YELLOW, YELLOW)),     # bombs
    ('b', 1, 8, (MAGENTA, BLUE, BLUE, YELLOW, YELLOW)),        # invaders
    ('b', 9, 16, (CYAN, BLUE, BLUE, WHITE, RED)),              # birds / faces
    ('b', 17, 24, (YELLOW, ORANGE, RED, WHITE, RED)),          # spiked mines
    ('b', 25, 30, 'spark'),
]
TRUCK_FILL = (BLACK, DGREY, BLUE)     # never ink in the rover's Enhanced images (fill, outline)


def families(m):
    t1 = [w16(m, GTAB1 + 2 * i) for i in range(255)]
    t2 = [w16(m, GTAB2 + 2 * i) for i in range(30)]
    fam = {}
    for tab, lo, hi, f in FAMILY:
        t = t1 if tab == 'a' else t2
        for ty in range(lo, hi + 1):
            if ty - 1 < len(t):
                fam.setdefault(t[ty - 1], f)
    return fam


def _fig_ink(m, p):
    H = m[p]
    ink = set()
    for k in range(H):
        r = 1 + (H - 1 - k)
        for j in range(2):
            b = m[p + 1 + 2 * k + j]
            for i in range(8):
                if b & (0x80 >> i):
                    ink.add((1 + 8 * j + i, r))
    return ink


def pal_path(j256):
    """The Spec256 palette is read beside the Jetpac.256 (the record stages both beside the snapshot)."""
    return os.path.join(os.path.dirname(os.path.abspath(j256)), PAL_NAME)


def _spec256_palette(j256):
    """The Spec256 palette (PAL_NAME beside the .256; a declared, MD5-pinned input, never in the repo) -> 256 RGB."""
    import hashlib
    p = pal_path(j256)
    if not os.path.isfile(p):
        raise ValueError('no %s beside %s: the Enhanced colours need it' % (PAL_NAME, os.path.basename(j256)))
    raw = open(p, 'rb').read()
    if hashlib.md5(raw).hexdigest() != PAL_MD5:
        raise ValueError('%s MD5 %s, the approved build used %s' % (PAL_NAME, hashlib.md5(raw).hexdigest(), PAL_MD5))
    v = [int(x) for x in raw.decode('ascii').split()]
    ch = [255 * (x >> 2) // 63 for x in v]
    return [tuple(ch[i:i + 3]) for i in range(0, 768, 3)]


def jet_templates(m, path=None):
    path = path or J256
    """[{(x, y): RGB}] from the .256: the pixel colours of Jetman's two matched frames."""
    from pathlib import Path
    d = Path(path).read_bytes()
    banks = (5, 2, 0)

    def at(a):
        return banks[(a >> 14) - 1] * 16384 * 9 + (a & 0x3FFF) * 9
    pal = _spec256_palette(path)
    out = []
    for p, a in JET_TEMPLATES.items():
        H = m[p]
        same = sum(1 for i in range(2 * H) if d[at(a + i) + 8] == m[p + 1 + i])
        if same < 2 * H - 2:        # 0xBCC2 differs from Jetpac's frame in one byte (one pixel)
            raise ValueError('Jetpac .256 graphics differ at %x' % a)
        t = {}
        for k in range(H):
            for j in range(2):
                pl = d[at(a + 2 * k + j):at(a + 2 * k + j) + 8]
                for i in range(8):
                    if m[p + 1 + 2 * k + j] & d[at(a + 2 * k + j) + 8] & (0x80 >> i):
                        ix = sum(((b >> (7 - i)) & 1) << q for q, b in enumerate(pl))
                        t[(1 + 8 * j + i, 1 + (H - 1 - k))] = pal[ix]
        out.append(t)
    return out


def _transfer(ink, temps):
    best = None
    for t in temps:
        for mir in (False, True):
            tt = {((17 - x) if mir else x, y): c for (x, y), c in t.items()}
            for dx in range(-3, 4):
                for dy in range(-5, 6):
                    sc = sum(1 for (x, y) in ink if (x - dx, y - dy) in tt)
                    if best is None or sc > best[0]:
                        best = (sc, tt, dx, dy)
    _, tt, dx, dy = best
    pts = list(tt.items())
    out = {}
    for (x, y) in ink:
        q = (x - dx, y - dy)
        out[(x, y)] = tt[q] if q in tt else min(pts, key=lambda e: (e[0][0] - q[0]) ** 2 + (e[0][1] - q[1]) ** 2)[1]
    return out


def _components(px, diag=True):
    px = set(px); out = []
    while px:
        st = [px.pop()]; c = set(st)
        while st:
            x, y = st.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in px and (diag or dx == 0 or dy == 0):
                        px.discard(q); c.add(q); st.append(q)
        out.append(c)
    return out


def _paint_jetman(ink, sh, temps):
    col = _transfer(ink, temps)
    ys = [y for _, y in ink]; top = min(ys)
    out = {}
    for q in ink:
        r, g, b = col[q]
        grey = abs(r - g) < 40 and abs(g - b) < 40
        if grey:
            out[q] = CYAN if q[1] - top < 7 else (LGREY if r > 160 else DGREY)     # visor / pack
        else:
            out[q] = SKIN if r > 250 and g > 170 else (ORANGE if g > 90 else RED)    # suit, lit to shaded
    # flame: sparse pixels below the body (the jet's dots)
    for c in _components(ink):
        if len(c) <= 3 and min(y for _, y in c) > top + 14:
            for q in c:
                out[q] = YELLOW if (q[0] + q[1]) % 2 else ORANGE
    for q, c in sh.items():
        if c == 2:
            out[q] = DRED          # enclosed paper inside Jetman (mouth of the helmet, gaps): dark red
    return out


def _paint_solid(ink, sh, fam):
    light_, body, dark_, feat, small = fam
    out = {}
    comps = _components(ink)
    big = max(comps, key=len)
    for c in comps:
        if len(c) <= 4 and len(comps) > 1:
            for q in c:
                out[q] = small
            continue
        y0 = min(y for _, y in c); h = max(y for _, y in c) - y0 + 1
        for (x, y) in c:
            up, dn = (x, y - 1) in ink, (x, y + 1) in ink
            lf, rt = (x - 1, y) in ink, (x + 1, y) in ink
            t = (y - y0) / h
            if not up or not lf or (h >= 8 and t < 0.25):
                out[(x, y)] = light_
            elif not dn or not rt or (h >= 8 and t >= 0.75):
                out[(x, y)] = dark_
            else:
                out[(x, y)] = body
    for q, c in sh.items():
        if c == 2:
            out[q] = feat          # the paper it encloses: eyes, windows, the cross of a ball
    return out


def _paint_radial(ink, sh, ramp):
    xs = [x for x, _ in ink] or [0]; ys = [y for _, y in ink] or [0]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    rmax = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in ink) + 0.01 if ink else 1
    out = {}
    for (x, y) in ink:
        f = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / rmax
        out[(x, y)] = ramp[min(len(ramp) - 1, int(f * len(ramp)))]
    for q, c in sh.items():
        if c == 2:
            out[q] = ramp[0]
    return out


def _paint_missile(ink, sh):
    comps = _components(ink)
    big = max(comps, key=len) if comps else set()
    out = {}
    if len(big) < 12:               # an exhaust trail of dots
        return _paint_radial(ink, sh, (YELLOW, ORANGE, RED))
    xs = [x for x, _ in big]; ys = [y for _, y in big]
    # the nose: the end of the long axis furthest from the figure's own centre of the dots elsewhere
    pts = sorted(big, key=lambda q: q[0] + q[1] if (max(xs) - min(xs)) <= (max(ys) - min(ys)) * 2 else q[0])
    n = len(pts)
    for i, q in enumerate(pts):
        out[q] = RED if i >= n * 0.8 else (WHITE if (q[1] - min(ys)) < 2 else LGREY)
    for c in comps:
        if c is not big:
            for q in c:
                out[q] = ORANGE
    for q, c in sh.items():
        if c == 2:
            out[q] = DGREY
    return out


def _no_white_edge(out, sh, repl):
    """White stays only inside: a white pixel with any of its 8 neighbours outside the figure's ink and
    enclosed paper takes `repl`."""
    for (x, y), c in list(out.items()):
        if c == WHITE and any(sh.get((x + dx, y + dy), 0) not in (1, 2) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            out[(x, y)] = repl
    return out


def fig_image_enh(m, p, temps, fam):
    ink = _fig_ink(m, p)
    sh = _shape(ink, 32, 32)
    f = fam.get(p, (LGREY, LGREY, DGREY, CYAN, YELLOW))
    if p in JETMAN or f == 'jetman':
        col, repl = _paint_jetman(ink, sh, temps), LGREY
    elif f == 'blast':
        col, repl = _paint_radial(ink, sh, (WHITE, YELLOW, ORANGE, RED)), YELLOW
    elif f == 'spark':
        col, repl = _paint_radial(ink, sh, (WHITE, CYAN, BLUE)), CYAN
    elif f == 'missile':
        col, repl = _paint_missile(ink, sh), LGREY
    else:
        col, repl = _paint_solid(ink, sh, f), (f[1] if f[1] != WHITE else f[0])
    col = _no_white_edge(col, sh, repl)
    out = {}
    for q, c in sh.items():
        out[q] = OUTLINE if c == 3 else col[q]    # the outline: black, never white
    return out


def _wheels(ink, H):
    """The rover's wheels: (centre x, centre y, x radius, y radius) from the ink of the bottom five rows."""
    xs = sorted({x for (x, y) in ink if H - y <= 4})
    if not xs:
        return []
    cl = [[xs[0]]]
    for x in xs[1:]:
        if x - cl[-1][-1] <= 4:
            cl[-1].append(x)
        else:
            cl.append([x])
    return [((c[0] + c[-1]) / 2, H - 4.5, (c[-1] - c[0]) / 2 + 2.5, 6.0) for c in cl if c[-1] - c[0] >= 8]


def truck_image_enh(m, p):
    W, H = m[p], m[p + 1]
    ink = set()
    for k in range(H):
        r = 1 + (H - 1 - k)
        for j in range(W):
            b = m[p + 2 + k * W + j]
            for i in range(8):
                if b & (0x80 >> i):
                    ink.add((1 + 8 * j + i, r))
    sh = _shape(ink, 80, 32)
    wh = _wheels(ink, H) if H == 27 else []          # the 22 rover frames (not its debris)
    out = {}
    for (x, y), c in sh.items():
        k = H - y          # 0 = bottom row
        d = min([(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) ** 0.5 for cx, cy, rx, ry in wh] or [9])
        if k < 10 and d <= 1.0:                          # a wheel: solid dark-grey tyre, light-grey spokes
            if c == 1:
                out[(x, y)] = LGREY if d <= 0.6 else DGREY
            elif d > 0.6 and (c == 2 or d <= 0.9):
                out[(x, y)] = DGREY
            else:
                out[(x, y)] = BLACK
            continue
        if c == 1:
            up, dn = (x, y - 1) in ink, (x, y + 1) in ink
            if k < 10:                                   # lower body (and debris)
                out[(x, y)] = LGREY
            elif k < 16:                                 # chassis band and its trim
                out[(x, y)] = YELLOW if not up else LGREY
            else:                                        # body: cyan top edge, no white
                out[(x, y)] = CYAN if (not up or dn) else BLUE
        elif c == 2:
            out[(x, y)] = DGREY if k < 16 else BLUE      # tyres' inside, the cockpit glass
        else:
            out[(x, y)] = BLACK
    return out


def palette_enh():
    pal = [0xE3] * 256
    for b in range(16):
        for i in range(1, 16):
            pal[16 * b + i] = rgb8(EP[i])
    return bytes(pal)


def build_data_enh(m, path=None):
    st, pages, info = build_data(m)
    temps = jet_templates(m, path)
    fam = families(m)
    figs, trucks = info['figs'], info['trucks']
    dpages = pages
    pages = {k: bytearray(v) for k, v in pages.items()}
    for k, p in enumerate(figs):
        pat = patterns(fig_image_enh(m, p, temps, fam), 2, 2)
        pg = FP0 + k // 16
        pages[pg][(k % 16) * 512:(k % 16) * 512 + 512] = pat
    for k, p in enumerate(trucks):
        pat = patterns(truck_image_enh(m, p), 5, 2)
        pg = TP0 + k // 6
        pages[pg][(k % 6) * 1280:(k % 6) * 1280 + 1280] = pat
    for pg in pages:            # the same opaque pixels as the default images, nibble for nibble
        a, b = dpages[pg], pages[pg]
        for i in range(8192):
            for sh_ in (4, 0):
                if bool((a[i] >> sh_) & 15) != bool((b[i] >> sh_) & 15):
                    raise ValueError('Enhanced image changes the silhouette (page %d +%d)' % (pg, i))
    return st, {k: bytes(v) for k, v in pages.items()}, info


# ---------------------------------------------------------------------------------------------
# Differential verification (imported 2026-11-04 from the pilot's work/verify.py, a script: the same
# checks, its screenshots dropped). Original replay (rzx.trace). At every hook site: original and
# patched code run from the same state to the same continuation point; registers (all but R, T,
# MEMPTR) and memory (0x4000-0xFFFF but the dead stack) must match; slot 4 must be back on page 4. The
# patched runs feed a model of the sprite hardware (NEXTREG 0x34-0x39, patterns via 0x303B / 0x5B)
# and of the hook pages. At every interrupt outside the plot code, each object's sprite INK pixels
# must equal the pixels its own XOR stores put on the original screen (per object, so overlaps are
# exact), the palette must be the object's colour, and no other object may own figure pixels; at
# every IM 1 the alt ROM image's handler runs against the original's. s0 = the stepped start state
# (the decrypted game at 0x8000) the patch is applied to; the shipped build starts at the decrypter.
# ---------------------------------------------------------------------------------------------

NEGATIVES = ('xoff', 'img', 'idx', 'keepstore', 'keeppaint', 'nobright', 'noslot', 'nocls', 'pal', 'rom3left', 'speed35')
NEGATIVES_ENH = ('pal', 'img', 'idx', 'nobright', 'xoff', 'rom3left')


def verify(rzx, s0, stop=None, neg=None, enh=False, j256=None):
    """-> (Counter, examples, frames, trace error). Failure keys end in '!'."""
    import sys
    import collections
    from .rzx import trace
    from . import z80n
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import A, F, B, C, D, E, H, L, SP, REGISTERS
    LJ = sys.modules[__name__]
    IXh, IXl = REGISTERS['IXh'], REGISTERS['IXl']
    CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]
    prof = LJ.load_profile()
    if neg == 'xoff':      # sprite x one pixel right
        h = bytearray.fromhex(prof['hooks']['rom'])
        # 'add a,31' in h_new (C6 1F) -> add a,32
        i = h.find(bytes([0xC6, 0x1F])); h[i + 1] = 32; prof['hooks']['rom'] = h.hex()
    if neg == 'nocls':
        pass
    if neg == 'speed35':   # the old fixed 3.5 MHz exit: the speed read's 'and 3' (E6 03 F5) -> 'and 0'
        h = bytearray.fromhex(prof['hooks']['rom'])
        i = h.find(bytes([0xE6, 0x03, 0xF5]))
        while i >= 0:
            h[i + 1] = 0
            i = h.find(bytes([0xE6, 0x03, 0xF5]), i + 1)
        prof['hooks']['rom'] = h.hex()
    PREPAINT = {}
    ENH, RZX, STOP = enh, rzx, stop
    if neg == 'nobright':  # palette offset without the bright bit: 'or 8' (F6 08) -> 'or 0'
        h = bytearray.fromhex(prof['hooks']['rom']); i = h.find(bytes([0xF6, 0x08])); h[i + 1] = 0; prof['hooks']['rom'] = h.hex()
    if neg == 'noslot':    # h_new leaves slot 4 on the state page: first 'nextreg 0x54,4' -> 0x54,26
        h = bytearray.fromhex(prof['hooks']['rom']); i = h.find(bytes([0xED, 0x91, 0x54, 4])); h[i + 3] = 26; prof['hooks']['rom'] = h.hex()
    if neg == 'nocls':     # h_cls hides nothing: 'nextreg 0x38,0' in its loop -> 0x37,0
        h = bytearray.fromhex(prof['hooks']['rom'])
        i = h.find(bytes([0xED, 0x92, 0x34, 0xED, 0x91, 0x38])); h[i + 5] = 0x37; prof['hooks']['rom'] = h.hex()
    patch = LJ.LunarJetmanPatch(prof, enhanced=ENH, j256=j256)
    if neg == 'rom3left':  # the previous build: only the hook bytes 0x386E.. written over NextZXOS's ROM3 (IM 1 reaches 0x0038 here)
        LJ.rom3_left(patch)
    ALT = LJ.alt_image(patch)            # the alt ROM image as the Next's stub fills it, from NextZXOS's ROM3
    HR = getattr(patch, 'hook_range', patch.altrom)
    if neg == 'pal':       # one palette entry wrong (Jetman white block, ink)
        se = bytearray(patch.stub_extra); i = se.find(LJ.palette(ENH)); se[i + 16 * 15 + 1] ^= 0x24; patch.stub_extra = bytes(se)
    from skoolkit.snapshot import Snapshot
    _s = Snapshot.get(s0)
    _ram = bytes(_s.ram())
    class _Snap:
        is128 = False
        banks = {5: _ram[0:16384], 2: _ram[16384:32768], 0: _ram[32768:]}
    snap = _Snap()
    patch.apply(snap)
    if neg == 'img':       # one figure image wrong: Jetman's first graphic shifted a pixel
        pg = patch.pages[LJ.FP0]
        k = patch.info['figs'].index(0xbdd0)
        off = (k % 16) * 512
        b = bytearray(pg); b[off:off + 512] = bytes(b[off + 1:off + 512]) + b'\x00'
        patch.pages[LJ.FP0] = bytes(b)
    if neg == 'whiteedge':  # needs the pilot's lj_before.py (the images before the no-white change): not imported
        raise ValueError('negative whiteedge is not in the repo (pilot work/lj_before.py)')
    if neg == 'idx':       # index page points one graphic (Jetman 0xBDD0) at its neighbour's image
        b = bytearray(patch.pages[LJ.IDX_PAGE]); b[0xBDD0 & 0x1FFF] += 1; patch.pages[LJ.IDX_PAGE] = bytes(b)
    SITE = {a: (old, new) for a, old, new in patch.sites}
    HOOKS = {a: sym for a, _, _, sym in LJ.SITES}
    if neg == 'keepstore':
        del SITE[34282]
    if neg == 'keeppaint':
        del SITE[34663]

    TILEMAP = {}
    if ENH:     # each Enhanced tile -> its default tile (same silhouette), whose classes say ink / fill / outline
        _ram = bytes(16384) + bytes(snap.banks[5] + snap.banks[2] + snap.banks[0])
        _dec = LJ.decrypt(_ram)[0] if False else _ram
        _sd, _pd, _ = LJ.build_data(bytes(16384) + _Snap.banks[5] + _Snap.banks[2] + _Snap.banks[0])
        _se, _pe, _ = LJ.build_data_enh(bytes(16384) + _Snap.banks[5] + _Snap.banks[2] + _Snap.banks[0], j256)
        for pg, data in _pe.items():      # built here, independently of the patch under test
            if pg in (LJ.IDX_PAGE,):
                continue
            for t in range(0, 8192, 128):
                e, d = bytes(data[t:t + 128]), bytes(_pd[pg][t:t + 128])
                if TILEMAP.get(e, d) != d:
                    raise ValueError('two default tiles share one Enhanced tile')
                TILEMAP[e] = d
    SITEB = {a + i for a, (old, new) in SITE.items() for i in range(len(new))}
    store = {}            # page -> bytes (hook pages, persistent model)
    for pg, data in patch.pages.items():
        store[pg] = bytearray(data)
    store[LJ.STATE_PAGE] = bytearray(patch.state)


    class NS:
        def __init__(s):
            s.nr = {}
            s.attr = [[0] * 5 for _ in range(128)]
            s.pat = bytearray(16384)
            s.pp = 0
            s.sel = None                # NextREG selected at 0x243B (h_new / h_tnew read NR 7: the caller's speed)

    ns = NS()
    cnt = collections.Counter()
    ex = collections.defaultdict(list)


    def fail(k, msg):
        cnt[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(msg)


    def patched_mem(m):
        pm = bytearray(m)
        pm[0:0x4000] = ALT
        for a, (old, new) in SITE.items():
            pm[a:a + len(new)] = new
        return pm


    def run(sim, stop, limit=300000):
        R, ops, mem = sim.registers, sim.opcodes, sim.memory
        n = 0
        while not stop(R):
            ops[mem[R[24]]]()
            n += 1
            if n > limit:
                return False
        return True


    def mk(mem, regs, patched):
        sim = Simulator(mem, {})
        sim.registers[:] = regs
        cur = [4]
        page4 = bytes(mem[0x8000:0xA000])

        def nextreg(r, v):
            ns.nr[r] = v
            if not patched:
                raise RuntimeError('NEXTREG in original code')
            if 0x35 <= r <= 0x39:
                ns.attr[ns.nr.get(0x34, 0) & 0x7F][r - 0x35] = v
            if r == 0x54:
                if cur[0] != 4:
                    store[cur[0]][:] = mem[0x8000:0xA000]
                mem[0x8000:0xA000] = page4 if v == 4 else store[v]
                cur[0] = v
        z80n.install(sim, nextreg)

        class Tr:
            def read_port(s, regs_, port):
                if patched and port == 0x253B and ns.sel is not None:     # a NextREG read: NR 7 as the core
                    if ns.sel == 0x07:                                      # composes it (actual << 4 | programmed)
                        sp = ns.nr.get(0x07, 0) & 3
                        return sp << 4 | sp
                    return ns.nr.get(ns.sel, 0)
                return 0xFF

            def write_port(s, regs_, port, value, *x):
                if not patched:
                    return
                if port == 0x243B:
                    ns.sel = value
                elif port == 0x303B:
                    ns.pp = (value & 0x3F) * 256 + (128 if value & 0x80 else 0)
                elif port & 0xFF == 0x5B:
                    ns.pat[ns.pp & 0x3FFF] = value
                    ns.pp += 1
                else:
                    fail('port!', hex(port))
        sim.set_tracer(Tr())
        return sim, cur


    FIG = collections.defaultdict(dict)    # ix -> {addr: bits}
    PLOT = (34054, 35150)


    def ula_xy(a):
        return (a & 31) * 8, ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)


    def fig_pixels(ix):
        out = set()
        for a, b in FIG[ix].items():
            if b:
                x, y = ula_xy(a)
                for i in range(8):
                    if b & (0x80 >> i):
                        out.add((x + i, y))
        return out


    def sprite_pixels(s0, n):
        ink, other, pals = set(), set(), set()
        for s in range(s0, s0 + n):
            a = ns.attr[s]
            if not a[3] & 0x80:
                continue
            x = a[0] | (a[2] & 1) << 8
            y = a[1]
            pal = a[2] & 0xF0
            pals.add(pal >> 4)
            pn = (a[3] & 0x3F) << 1 | (1 if a[4] & 0x40 else 0)
            base = pn * 128
            tile = bytes(ns.pat[base:base + 128])
            if ENH:
                if tile not in TILEMAP:
                    fail('unknown Enhanced tile!', pn); continue
                d_ = TILEMAP[tile]
                if any(bool((tile[i] >> q) & 15) != bool((d_[i] >> q) & 15) for i in range(128) for q in (4, 0)):
                    fail('Enhanced tile silhouette!', pn)
                tile = d_
            for r in range(16):
                for c in range(16):
                    byte = tile[r * 8 + c // 2]
                    v = byte >> 4 if c % 2 == 0 else byte & 15
                    if not v:
                        continue
                    px, py = (x + c) % 512 - 32, y + r - 32
                    if not (0 <= px < 256 and 0 <= py < 192):
                        continue
                    if (pal == 0 and v in (13, 15)) or (pal and v == 1):
                        ink.add((px, py))
                    else:
                        other.add((px, py))
        return ink, other, pals


    def owner(ix):
        d = ix - LJ.OBJ0
        if ix in LJ.TRUCKS:     # a truck record drawn by the figure plotter uses its figure sprites too
            return [((0 if ix == 0x6090 else 10), 10), (20 + 4 * (d // 24), 4)]
        if 0 <= d < LJ.NOBJ * 24 and d % 24 == 0:
            return [(20 + 4 * (d // 24), 4)]
        return None


    def owner1(ix):
        d = ix - LJ.OBJ0
        if 0 <= d < LJ.NOBJ * 24 and d % 24 == 0:
            return 20 + 4 * (d // 24), 4
        return None


    frames = [0]
    stores = [0]


    def check_frame(sim):
        m = sim.memory
        r = sim.registers
        sp = r[SP]
        ret = m[sp] | m[(sp + 1) & 0xFFFF] << 8
        frames[0] += 1
        if PLOT[0] <= ret <= PLOT[1]:
            cnt['frames skipped (in plot code)'] += 1
            return
        cnt['frames checked'] += 1
        # clash in the original: figure pixels shown in a cell whose ink is not the figure's own colour
        worst = 0
        for ix in FIG:
            if ix in LJ.TRUCKS:
                continue
            fp = fig_pixels(ix)
            if not fp:
                continue
            own = m[ix + 7] & 0x47
            bad = sum(1 for (x, y) in fp if m[0x5800 + (y >> 3) * 32 + (x >> 3)] & 0x47 != own)
            cnt['clash: figure pixels'] += len(fp)
            cnt['clash: shown in another ink'] += bad
            cnt['clash: figure plots'] += 1
            if bad:
                cnt['clash: plots with pixels in another ink'] += 1
            worst = max(worst, bad)
        painted = sum(1 for a, v in PREPAINT.items() if m[a] != v)
        cnt['clash: scenery cells repainted by figures (sum over frames)'] += painted
        owned = set()
        for ix in sorted(FIG):
            o = owner(ix)
            fp = fig_pixels(ix)
            if o is None:
                if fp:
                    fail('figure with no sprites!', hex(ix))
                continue
            owned.add(o[0])
            nz = [a for a, b in FIG[ix].items() if b]
            if nz and all(m[a] == 0 for a in nz):
                fail('figure wiped from the screen, sprite shown!', 'f%d ix %x' % (frames[0], ix))
            ink, other, pals = set(), set(), set()
            for rg in o:
                a_, b_, c_ = sprite_pixels(*rg); ink |= a_; other |= b_; pals |= c_
            if ink != fp:
                fail('sprite ink != figure pixels!', 'f%d ix %x miss %d extra %d e.g. %s' % (
                    frames[0], ix, len(fp - ink), len(ink - fp), sorted(fp ^ ink)[:3]))
            else:
                cnt['objects equal'] += 1
                cnt['figure pixels equal'] += len(fp)
            if other & fp:
                fail('outline or fill over ink!', hex(ix))
            if fp and ix not in LJ.TRUCKS:
                want = LJ.colour_offset(m[ix + 7])
                if pals - {0} != {want}:
                    cnt['palette differs from (IX+7) now'] += 1
        # sprites shown for objects with no figure pixels
        for ix in [LJ.OBJ0 + 24 * n for n in range(LJ.NOBJ)] + list(LJ.TRUCKS):
            if ix in FIG and fig_pixels(ix):
                continue
            ink = set()
            for rg in owner(ix):
                ink |= sprite_pixels(*rg)[0]
            if ink:
                fail('sprite shown, no figure!', 'f%d ix %x %d px' % (frames[0], ix, len(ink)))


    def isr(sim):
        """An IM 1 interrupt the original takes at 0x0038: the original ROM's handler and the alt ROM image's handler run
        from the same state to the return; registers and 0x4000-0xFFFF compared, and no PC in the hook bytes. On the Next
        NextZXOS's DivMMC trap takes 0x0038; here it really reaches the alt ROM, as without that trap."""
        m, r = sim.memory, sim.registers
        mem0 = bytes(m)
        regs0 = list(r)
        sp0 = regs0[SP]
        ret = mem0[sp0] | mem0[(sp0 + 1) & 0xFFFF] << 8
        stop = lambda R: R[24] == ret and R[SP] == (sp0 + 2) & 0xFFFF
        o_mem = bytearray(mem0)
        so, _ = mk(o_mem, regs0, False)
        p_mem = patched_mem(mem0)
        sp_, cur = mk(p_mem, regs0, True)
        oko = run(so, stop, 20000)
        Rp, ops = sp_.registers, sp_.opcodes
        n = ran = 0
        try:
            while not stop(Rp) and n < 20000:
                if HR[0] <= Rp[24] < HR[1]:
                    ran += 1
                ops[p_mem[Rp[24]]]()
                n += 1
        except Exception as e:
            fail('IM 1 handler: patched run raised!', repr(e)[:80]); return
        cnt['IM 1 handlers compared'] += 1
        if ran:
            fail('IM 1 handler ran hook code!', 'f%d %d instructions' % (frames[0], ran))
        if not (oko and stop(Rp)):
            fail('IM 1 handler did not return!', 'f%d' % frames[0]); return
        d = [i for i in CMP if so.registers[i] != Rp[i]]
        if d:
            fail('IM 1 handler: registers!', 'f%d %s' % (frames[0], d))
        md = [a for a in range(0x4000, 0x10000) if o_mem[a] != p_mem[a] and a not in SITEB]   # the patch's own code bytes aside
        if md:
            fail('IM 1 handler: memory!', 'f%d %d bytes %s' % (frames[0], len(md), [hex(a) for a in md[:4]]))


    def on(pc, sim):
        m, r = sim.memory, sim.registers
        if pc == 0x38:
            isr(sim)
            check_frame(sim)
            return
        ix = r[IXl] | r[IXh] << 8
        if pc in LJ.STORE_NOPS:
            hl = r[L] | r[H] << 8
            d = r[A] ^ m[hl]
            if d:
                FIG[ix][hl] = FIG[ix].get(hl, 0) ^ d
            stores[0] += 1
            cnt['figure stores (original)'] += 1
            if pc not in SITE:
                fail('store site not patched!', pc)
            return
        if pc in (34663, 35127, 35104):
            v = r[D] if pc != 35104 else r[A]
            hl = r[L] | r[H] << 8
            PREPAINT.setdefault(hl, m[hl])
            cnt['paint %d' % pc] += 1
            if v == 0:
                fail('paint zero (changes a later branch)!', pc)
            if pc not in SITE:
                fail('paint site not patched!', pc)
            return
        sym = HOOKS[pc]
        if pc in (34011, 35749):
            FIG.clear(); PREPAINT.clear()
        mem0 = bytes(m)
        regs0 = list(r)
        sp0 = regs0[SP]
        if sym in ('h_new', 'h_clr', 'h_tnew'):
            ret = mem0[sp0] | mem0[sp0 + 1] << 8
            stop = lambda R: R[24] == ret and R[SP] == (sp0 + 2) & 0xFFFF
        elif sym == 'h_eo':
            stop = lambda R: R[24] == 34372
        elif sym == 'h_teo':
            stop = lambda R: R[24] == 34387
        elif sym == 'h_msg':
            stop = lambda R: R[24] == 35752
        else:
            stop = lambda R: R[24] == 34014 and R[SP] == sp0
        o_mem = bytearray(mem0)
        so, _ = mk(o_mem, regs0, False)
        p_mem = patched_mem(mem0)
        sp_, cur = mk(p_mem, regs0, True)
        t0 = regs0[25]
        k_in = cnt['speed cases'] & 3           # the hook entered at each clock in turn (patch.restore-speed)
        cnt['speed cases'] += 1
        ns.nr[0x07] = k_in
        okp = run(sp_, stop)
        if ns.nr.get(0x07, 0) & 3 != k_in:
            fail('exit speed is not the incoming clock!', '%s in %d out %d' % (sym, k_in, ns.nr.get(0x07, 0) & 3))
        ns.nr[0x07] = 0
        oko = run(so, stop)
        cnt['T added by hooks (sim T, all at 3.5 MHz)'] += (sp_.registers[25] - so.registers[25])
        cnt['T ' + sym] += (sp_.registers[25] - so.registers[25])
        cnt['hook %s' % sym] += 1
        if not (okp and oko):
            fail('run limit!', sym); return
        if cur[0] != 4:
            fail('slot 4 not restored!', sym)
        if sym == 'h_new' and o_mem[regs0[IXl] | regs0[IXh] << 8 + 0] is not None:
            ix = regs0[IXl] | regs0[IXh] << 8
            o = owner(ix)
            if o and o_mem[ix + 10]:
                want = LJ.colour_offset(o_mem[ix + 7])
                f0 = o[-1][0]
                got = {ns.attr[q][2] >> 4 for q in range(f0, f0 + 4)}
                if got != {want}:
                    fail('palette offset at the draw!', '%x %s %s' % (ix, got, want))
                else:
                    cnt['palette offsets checked'] += 1
        for i in CMP:
            if so.registers[i] != sp_.registers[i]:
                fail('register!', '%s reg %d %x/%x' % (sym, i, so.registers[i], sp_.registers[i]))
                break
        lo = sp0 - 48
        diff = [a for a in range(0x4000, 0x10000) if o_mem[a] != p_mem[a] and not (lo <= a < sp0)
                and a not in SITEB]
        if diff:
            fail('memory!', '%s %d bytes %s' % (sym, len(diff), [hex(a) for a in diff[:4]]))


    def setup_check():
        mem = bytearray(65536)
        mem[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
        mem[0xCFFE:0xD000] = b'\xff\xff'
        regs = [0] * 30
        sim = Simulator(mem, {}); R = sim.registers
        R[24] = 0xD000; R[12] = 0xCFFE
        pal = []; nr = {}
        def nx(r, v):
            nr[r] = v
            if r == 0x41:
                pal.append(v)
        z80n.install(sim, nx)
        run(sim, lambda R: R[24] == 0xFFFF)
        want = LJ.palette(ENH)
        cnt['setup palette entries'] = len(pal)
        if bytes(pal) != want or nr.get(0x43) != 0x20 or nr.get(0x4B) != 0 or nr.get(0x15) != 1:
            fail('setup palette!', '%d entries, %d differ' % (len(pal), sum(1 for a, b in zip(pal, want) if a != b)))
    setup_check()
    _off = LJ.alt_outside_hooks(patch)
    if _off:
        cnt["alt ROM image bytes outside the hooks not Sinclair's!"] = len(_off)
        ex["alt ROM image bytes outside the hooks not Sinclair's!"].append([hex(a) for a in _off[:6]])

    pcs = set(HOOKS) | set(LJ.STORE_NOPS) | {34663, 35127, 35104, 0x38}
    n, err = trace(RZX, pcs, on, stop=STOP)
    return cnt, ex, n, err
