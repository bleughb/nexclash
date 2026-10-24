"""The Incredible Shrinking Fireman (Mastertronic, 1986, 48K) - engine 'fireman'. Additive module:
reachable only through is_fireman().

Facts (games/incredible_shrinking_fireman.md):
  47440  THE figure plotter (A = slot 0 fireman, 1 / 2 the room figures; slot state at 48375 + 8 A:
         x, y, frame (+2) ... E colour (+6); gfx at (48450) + 48 frame, 24 rows x 2 bytes, 1 = ink).
         One call is a differential XOR move: old image ^ new image on the screen, then the attribute
         routine colours the cells. Callers include the frame interrupt's tick (slot 0).
  60671  collectable draw (id, x, y entries of the room table, 5 per room): 7 plain stores, 8 x 7 px.
  The game's ground test reads the screen at (x, y + 25) (49868 51159 51183 51421 ... LD A,(DE)),
  which can be an enemy's XORed pixels: virtual read (screen XOR figure bytes) at those sites.
Hooks (asm/incredible_shrinking_fireman_hooks.asm): the plotters keep running, only their screen and
attribute writes are removed; flags in RAM (HS = 0xF400); ALL sprite writes happen in the frame
interrupt hook (interrupts are off there).
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5E40
HS = 0xF400
SLOTS = 48375
GFXPTR = 48450
PLOTTER = 47440
PLOT_END = 48220
ISR_SITE = 49804
DIA_SITE = 60656
ROOM = 49612
OBJTAB = 55021
DIA_GFX = 60692                 # 7 bytes: the collectable's rows
SPR_DIA = 0                     # sprites 0-4
SPR_SLOT = {0: (9, 10), 1: (7, 8), 2: (5, 6)}
PAT_DIA = 6
DIA_INDEX = 4                   # sprite palette index of the collectables (slots use 1-3, palette offset 0)
STACK_DEAD = 64

# (address, original bytes, symbol or None, opcode or None, replacement bytes when no symbol)
SITES = [
    (48220, 'dde1c9', 'e_ep', 0xC3, b''),
    (ISR_SITE, 'd9e1d1', 'e_isr', 0xC3, b''),
    (50343, '210040', 'e_c1', 0xC3, b''),
    (50609, '210048', 'e_c2', 0xC3, b''),
    (DIA_SITE, 'cdffec', 'e_dia', 0xCD, b''),
]
RD_SITES = {49868: ('a', '1aa7c0'), 49872: ('a', '1aa7c0'), 49892: ('a', '1aa7c0'),
            49896: ('a', '1aa7c0'), 51159: ('a', '1aa7c0'), 51163: ('a', '1aa7c0'),
            51183: ('a', '1aa7c0'), 51187: ('a', '1aa7c0'), 51421: ('j', '1aa7c2e7c8'),
            51427: ('z', '1aa728d6')}
RD_SYM = {'a': 'rd_a', 'j': 'rd_j', 'z': 'rd_z'}
SCREEN_PATCHES = [(47897, '77', '00'), (47901, '77', '00'), (47905, '77', '00'), (60683, '77', '00')] + \
    [(a, 'dd7700', '000000') for a in (48047, 48059, 48071, 48083, 48165, 48174, 48183, 48351)]
PLOT_WRITERS = {47897, 47901, 47905, 48047, 48059, 48071, 48083, 48165, 48174, 48183}
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'incredible_shrinking_fireman.json'),
              os.path.join(_HERE, 'incredible_shrinking_fireman.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('incredible_shrinking_fireman.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_fireman(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# Model of what the build must show (independent of the hook code)
# ---------------------------------------------------------------------------------------------

def frame_rows(peek, frame):
    a = (peek(GFXPTR) | peek(GFXPTR + 1) << 8) + 16 * ((3 * frame) & 255)     # 47742: 8-bit wrap
    return [peek(a + 2 * r) << 8 | peek(a + 2 * r + 1) for r in range(24)]


def image_pixels(rows, x, y):
    return {(x + c, y + r) for r, v in enumerate(rows) for c in range(16) if v >> (15 - c) & 1}


def diamond_rows(peek):
    return [peek(DIA_GFX + r) for r in range(7)]


def diamond_pattern(peek):
    """128 bytes: 16 x 16 4-bit pixels, the 8 x 7 diamond at the top left (colour index 4)."""
    out = bytearray(128)
    for r, v in enumerate(diamond_rows(peek)):
        for k in range(4):
            hi = (v >> (7 - 2 * k)) & 1
            lo = (v >> (6 - 2 * k)) & 1
            out[r * 8 + k] = (hi << 4 | lo) * DIA_INDEX
    return bytes(out)


def sprite_pixels(attr, pat):
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return set()
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 + (a4 & 1) * 256 - 32
    base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
    out = set()
    for j in range(16):
        for k in range(16):
            b = pat[base + j * 8 + k // 2]
            if (b >> 4) if k % 2 == 0 else (b & 15):
                out.add((x + k, y + j))
    return out


def model_colour(e):
    """RRRGGGBB of the figure's ink (E bits 0-2: blue, red, green; bit 6: bright)."""
    lv = (7, 3) if e & 0x40 else (5, 2)
    r = lv[0] if e & 2 else 0
    g = lv[0] if e & 4 else 0
    b = lv[1] if e & 1 else 0
    return r << 5 | g << 2 | b


def clip(px):
    return {(x, y) for x, y in px if 0 <= x < 256 and 0 <= y < 192}


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class FiremanPatch:
    name = 'Incredible Shrinking Fireman figures + collectables -> hardware sprites (altrom hooks)'

    def __init__(self, prof=None, rom_code=None):
        self.prof = prof or load_profile()
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
            raise ValueError('ROM hooks too long (0x3D00+ is the DivMMC entry area)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        if self.rom_code[0x39FF - ROM_ORG:0x3A01 - ROM_ORG] != b'\xff\xff':
            raise ValueError('the IM 2 vector bytes 0x39FF / 0x3A00 must stay FF FF')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, old, sym, op, extra in SITES:
            self.sites.append((a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little') + extra))
        for a, (kind, old) in RD_SITES.items():
            o = bytes.fromhex(old)
            self.sites.append((a, o, b'\xcd' + self.syms[RD_SYM[kind]].to_bytes(2, 'little') + bytes(len(o) - 3)))
        for a, old, new in SCREEN_PATCHES:
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.extra_banks = {}
        self.pats = None
        self.num_patterns = 7

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Fireman patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for lo, n, what in ((TAIL_ADDR, 256, 'tail'), (HS, 32, 'hook state')):
            if any(ram[lo - 0x4000:lo - 0x4000 + n]):
                raise ValueError('%s area at 0x%04X is not zero in this snapshot' % (what, lo))
        self.pats = diamond_pattern(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        bank11 = bytearray(16384)
        bank11[0:128] = self.pats
        self.extra_banks = {11: bytes(bank11), 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Next-side state (sprite attributes, pattern memory, sprite palette) and the machines
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, pats=b''):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat[PAT_DIA * 128:PAT_DIA * 128 + len(pats)] = pats
        self.pal = {}
        self.pal_idx = 0
        self.sel = 0
        self.ptr = 0
        self.events = []
        self.lastf_uploads = 0

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            self.pal_idx = val
        elif reg == 0x41:
            if self.nr.get(0x43, 0) & 0x70 == 0x20:
                self.pal[self.pal_idx] = val
            self.pal_idx = (self.pal_idx + 1) & 255
        self.events.append(('nr', reg, val))

    def out(self, port, val):
        if port == 0x303B:
            self.ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.ptr] = val
            self.ptr = (self.ptr + 1) & 0x3FFF
        self.events.append(('out', port, val))

    def pixels(self, i):
        return sprite_pixels(self.attr[i], self.pat)

    def copy(self):
        n = NextState()
        n.nr = dict(self.nr)
        n.attr = [list(a) for a in self.attr]
        n.pat = bytearray(self.pat)
        n.pal = dict(self.pal)
        n.pal_idx, n.sel, n.ptr = self.pal_idx, self.sel, self.ptr
        return n


def _machine(Sim, mem, regs, ns, slot='o', nextn=True):
    from . import z80n
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    if nextn:
        z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stop, limit=400000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        if check:
            check(R)
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    if check:
        check(R)
    return True


HOOK_HI = 0x3D00
STACK_BUDGET = 48               # bytes the hooks may use below the SP they were entered with


class IntSafe:
    """Interrupt safety of hooks that run with interrupts ON (BRIEFING A1: an interrupt may arrive after
    any instruction and its handler reads IX / IY / I and pushes on the stack): while the PC is in the
    hook, IY, I and the interrupt flags never change, IX only by the replayed POP IX, SP stays within
    STACK_BUDGET of its entry value, and every store goes to the stack or the flag span."""

    def __init__(self, mem):
        self.mem = mem
        self.ent = None
        self.bad = []
        self.prev = None
        self.hook_stores = 0

    def __call__(self, R):
        pc = R[24]
        inh = ROM_ORG <= pc < HOOK_HI
        if self.ent is not None:
            sp, ixh, ixl, iyh, iyl, i, f1, f2 = self.ent
            pp = self.prev
            popix = pp is not None and self.mem[pp] == 0xDD and self.mem[pp + 1] == 0xE1
            if (R[10], R[11], R[14], R[26], R[27]) != (iyh, iyl, i, f1, f2):
                self.bad.append(('IY / I / IFF changed inside a hook', pp))
            if (R[8], R[9]) != (ixh, ixl):
                if popix:               # the replayed POP IX (plotter end): IX is the game's own again
                    self.ent = (sp, R[8], R[9], iyh, iyl, i, f1, f2)
                else:
                    self.bad.append(('IX changed inside a hook', pp))
            if R[12] < sp - STACK_BUDGET:
                self.bad.append(('hook stack use', sp - R[12]))
        if inh and self.ent is None:
            self.ent = (R[12], R[8], R[9], R[10], R[11], R[14], R[26], R[27])
        elif not inh:
            self.ent = None
        self.prev = pc if inh else None


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


class World:
    """Persistent state of the patched world next to the live original: hook RAM (HS span), the
    Next hardware, the figures' pixel bytes the original has on the screen that the patched one
    does not (F, XOR plotter deltas), the model of what is drawn."""

    def __init__(self, pats):
        self.hs = bytearray(32)
        self.ns = NextState(pats)
        self.ns.nr[0x43] = 0x20                 # setup: sprite palette selected
        self.ns.pal[DIA_INDEX] = 0xB6           # diamond colour (setup)
        self.F = {}
        self.drawn = {}                 # slot -> (x, y, frame) the original has drawn
        self.dia = {}                   # index -> set of pixels the original drew (room table entry)
        self.touch = collections.Counter()
        self.pending = []               # plots entered but not yet at their end (an interrupt can nest them)


def _overlays(get, alt, psite, world):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            return get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            v = psite.get(a)
            if v is not None:
                return v
            v = s.ov.get(a)
            if v is not None:
                return v
            if HS <= a < HS + 32:
                return world.hs[a - HS]
            if a < 0x5800:
                return get(a) ^ world.F.get(a, 0)
            return get(a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            else:
                s.ov[a] = v
    return O, P


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


def _pix_of(ov, lo=0x4000, hi=0x5800):
    out = set()
    for a, v in ov.items():
        if lo <= a < hi:
            y = ((a >> 5) & 0xC0) | ((a >> 8) & 7) | ((a >> 2) & 0x38)
            for k in range(8):
                if (v >> (7 - k)) & 1:
                    out.add(((a & 31) * 8 + k, y))
    return out


def _model_screen(rows, x, y):
    """{address: byte} of an image's pixels as the plotter would XOR them (no wrap)."""
    out = {}
    for px, py in image_pixels(rows, x, y):
        if 0 <= px < 256 and 0 <= py < 192:
            a = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
            out[a] = out.get(a, 0) | 0x80 >> (px & 7)
    return out


def _slot_state(get, s):
    b = SLOTS + 8 * s
    return get(b), get(b + 1), get(b + 2)


def _diamond_entries(get):
    room = get(ROOM)
    p = get(OBJTAB + 2 * room) | get(OBJTAB + 2 * room + 1) << 8
    return [(get(p + 3 * i), get(p + 3 * i + 1), get(p + 3 * i + 2)) for i in range(5)]


def _dia_model(entry):
    """Pixels of one collectable (8 x 7 at x & 0xF8, y + 2) from the game's rows, set in `sprite`."""
    return entry


def expected_sprites(world, get):
    """-> {sprite index: set of pixels} the patched world must show (clipped to the screen)."""
    exp = {}
    for s, (i0, i1) in SPR_SLOT.items():
        if s in world.drawn:
            x, y, fr = world.drawn[s]
            exp[i0] = exp[i1] = clip(image_pixels(frame_rows(get, fr), x, y))
    return exp


def event(patch, kind, site, get, R, world, alt, Sim, extra=None):
    """One hook event from a live state. Returns a failure list. kinds: pl dia c rd isr."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P = _overlays(get, alt, psite, world)
    f = []
    ns = world.ns
    before = ns.copy()
    ns.events = []
    sp0 = R[12]
    w = lambda a: get(a) | get(a + 1) << 8
    if kind == 'ep':
        # the live plot reaches its end: the screen delta, the drawn tuple and the flags take effect
        if not world.pending:
            return ['plot end without a plot']
        slot, d, post, hsw = world.pending.pop()
        for a, v in d.items():
            world.F[a] = world.F.get(a, 0) ^ v
            if not world.F[a]:
                del world.F[a]
        world.drawn[slot] = post
        for a, v in hsw.items():
            world.hs[a - HS] = v
        return f
    if kind == 'isr':
        # the live original is at 49804 (the tick has run): EXX / POP HL / POP DE; the patched one
        # runs e_isr (sprite update) and replays them, then both are at 49807.
        o, p = O(), P()
        so = _machine(Sim, o, list(R), NextState(), 'o', nextn=False)
        sp_ = _machine(Sim, p, list(R), ns, 'p')
        stop = lambda r: r[24] == ISR_SITE + 3
        if not (_run(so, stop) and _run(sp_, stop)):
            return ['isr hook did not return']
        ro, rp = so.registers, sp_.registers
        world.touch['T original, kind isr'] += ro[25] - R[25]
        world.touch['T patched, kind isr'] += rp[25] - R[25]
        world.touch['T patched, isr, worst'] = max(world.touch['T patched, isr, worst'], rp[25] - R[25])
        diff = [i for i in CMP if ro[i] != rp[i]]
        if diff:
            f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        if getattr(p, 'romw', 0):
            f.append(('patched code wrote ROM',))
        spend = rp[12]
        bad = [a for a in p.ov if not (HS <= a < HS + 32) and not spend - STACK_DEAD <= a < spend]
        if bad:
            f.append(('hook wrote outside its state', sorted(bad)[:4]))
        extra_ev = [e for e in ns.events if e[0] == 'in' or (e[0] == 'out' and e[1] != 0x303B and e[1] & 0xFF != 0x5B)]
        if extra_ev:
            f.append(('unexpected port access', extra_ev[:3]))
        for e in ns.events:
            if e[0] == 'nr' and e[1] not in (0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x40, 0x41, 0x43):
                f.append(('NEXTREG other than sprite / palette', e[1]))
                break
        for a in p.ov:
            if HS <= a < HS + 32:
                world.hs[a - HS] = p.ov[a]
        # sprite pixels against the model
        exp = expected_sprites(world, get)
        for s, (i0, i1) in SPR_SLOT.items():
            got = clip(ns.pixels(i0) | ns.pixels(i1))
            want = exp.get(i0, set())
            if s in world.drawn and world.drawn[s][0] > 240:
                world.touch['slot x > 240 (ULA wraps, sprite clips)'] += 1
                continue
            if got != want:
                f.append(('slot %d sprite pixels differ from the original plot' % s, len(got ^ want), world.drawn.get(s), _slot_state(get, s), sorted(got - want)[:6], sorted(want - got)[:6], [ns.attr[i0], ns.attr[i1]], [get(a) for a in range(48374, 48400)], bytes(world.hs)[:12].hex()))
            world.touch['slot pixels compared'] += len(want)
        for s_ in world.drawn:
            e_ = get(SLOTS + 8 * s_ + 6)
            if ns.pal.get(s_ + 1) != model_colour(e_):
                f.append(('slot %d palette entry differs from the colour model' % s_, ns.pal.get(s_ + 1), model_colour(e_)))
        ent = _diamond_entries(get)
        for i in range(5):
            got = clip(ns.pixels(SPR_DIA + i))
            shown = world.hs[3 + i] and ent[i][0] != 0
            if shown:
                idv, x, y = ent[i]
                want = clip({(x & 0xF8) + c, y + 2 + r} for r, v in enumerate(diamond_rows(get))
                            for c in range(8) if v >> (7 - c) & 1) if False else set()
                want = {((x & 0xF8) + c, y + 2 + r) for r, v in enumerate(diamond_rows(get))
                        for c in range(8) if v >> (7 - c) & 1}
                want = clip(want)
                # the original must really have it on the screen: bytes of the 7 rows
                ok = True
                for r, v in enumerate(diamond_rows(get)):
                    py = y + 2 + r
                    if 0 <= py < 192 and x & 0xF8 < 256:
                        a = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | (x >> 3)
                        if get(a) ^ world.F.get(a, 0) != v:
                            ok = False
                if not ok:
                    world.touch['diamond shown but the original screen differs'] += 1
                    world.touch['  e.g. frame-less sample: entry %s' % (ent[i],)] += 0
                world.touch['diamond pixels compared'] += len(want)
                if got != want:
                    f.append(('diamond %d sprite pixels differ' % i, len(got ^ want)))
            elif got:
                f.append(('diamond %d sprite visible but not drawn / id 0' % i, len(got)))
        vis = [i for i in range(128) if ns.attr[i][3] & 0x80]
        okset = set(range(5)) | {j for pair in SPR_SLOT.values() for j in pair}
        if set(vis) - okset:
            f.append(('unexpected sprites visible', sorted(set(vis) - okset)[:4]))
        return f
    # --- events that run the original and the patched code from the same state
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState(), 'o', nextn=False)
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if kind == 'pl':
        slot = R[0]
        ret = w(sp0)

        def stop(r):
            return r[24] == ret and r[12] == sp0 + 2
        stop_o = stop_p = stop
        b = SLOTS + 8 * slot
        pre = [get(b + k) for k in range(8)]
        newf = get(48374)
    elif kind == 'dia':
        nxt = site + 3

        def stop(r):
            return r[24] == nxt and r[12] == sp0
        stop_o = stop_p = stop
        slot = None
    elif kind == 'c':
        nxt = site + 3
        stop_o = stop_p = lambda r: r[24] == nxt or (r[24] in (50346, 50612))
        slot = None
    else:               # 'rd'
        size = len(patch_rd_old(site))
        r0 = list(R)
        lo, hi = site, site + size
        n_ = 0
        while True:
            so.opcodes[o[so.registers[24]]]()
            n_ += 1
            if not lo <= so.registers[24] < hi:
                break
        tgt, tsp = so.registers[24], so.registers[12]
        ro = so.registers
        isf = IntSafe(p)
        if not _run(sp_, lambda r: r[24] == tgt and r[12] == tsp, check=isf):
            return ['rd hook did not return']
        for b_ in isf.bad[:2]:
            f.append(b_)
        world.touch['hook instructions checked for interrupt safety'] += 1
        rp = sp_.registers
        world.touch['T original, kind rd'] += ro[25] - R[25]
        world.touch['T patched, kind rd'] += rp[25] - R[25]
        diff = [i for i in CMP if ro[i] != rp[i]]
        if diff:
            f.append(('rd registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
        if getattr(p, 'romw', 0):
            f.append(('patched code wrote ROM',))
        bad = [a for a in p.ov if not sp0 - STACK_DEAD <= a < sp0]
        if bad:
            f.append(('rd hook wrote memory', sorted(bad)[:4]))
        return f
    isf = IntSafe(p)
    if not (_run(so, stop_o) and _run(sp_, stop_p, check=isf)):
        return ['did not return']
    for b_ in isf.bad[:2]:
        f.append(b_)
    world.touch['hook instructions checked for interrupt safety'] += 1
    ro, rp = so.registers, sp_.registers
    world.touch['T original, kind ' + kind] += ro[25] - R[25]
    world.touch['T patched, kind ' + kind] += rp[25] - R[25]
    diff = [i for i in CMP if ro[i] != rp[i]]
    if kind == 'pl' and diff and set(diff) <= {1, 16, 17}:
        # F and AF' at the end of the plotter are leftovers of its working registers (CP L at 48195,
        # the EX AF,AF' loop), computed from the screen bytes it read - the patched build reads them
        # without the figure. Dead: convergence() scrambles both in the live game.
        world.touch["plot ends with a different F / AF' (screen-derived leftover, see convergence)"] += 1
        diff = []
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    if any(e[0] in ('in', 'out') for e in ns.events):
        f.append(('port access in a plot / clear hook',))
    if any(e[0] == 'nr' for e in ns.events):
        f.append(('NEXTREG in a plot / clear hook',))
    spend = ro[12]
    dead = range(spend - STACK_DEAD, spend)
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if not 0x4000 <= a < 0x5B00 and not HS <= a < HS + 32 and a not in dead
          and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    # the patched code must not write the screen or the attributes
    if any(0x4000 <= a < 0x5B00 for a in p.ov):
        f.append(('patched code wrote the screen / attributes',))
    hsw = {a for a in p.ov if HS <= a < HS + 32}
    if kind == 'pl':
        # original screen delta vs the model: old image ^ new image
        d = {a: o.ov[a] ^ get(a) for a in o.ov if 0x4000 <= a < 0x5800}
        d = {a: v for a, v in d.items() if v}
        ox, oy, ofr = pre[0], pre[1], pre[2]
        nx, ny = (ox + pre[4]) & 255, (oy + pre[5]) & 255
        small = abs((nx & 248) - (ox & 248)) <= 8 and ox <= 240 and nx <= 240
        want = collections.Counter()
        for a, v in _model_screen(frame_rows(get, ofr), ox, oy).items():
            want[a] ^= v
        for a, v in _model_screen(frame_rows(get, newf), nx, ny).items():
            want[a] ^= v
        want = {a: v for a, v in want.items() if v}
        d = {a: o.ov[a] ^ get(a) for a in o.ov if 0x4000 <= a < 0x5800}
        d = {a: v for a, v in d.items() if v}
        if os.environ.get('FM_DIST'):
            world.touch['DIST slot %d dy %s dx %s oldblank %s ox>200 %s ok %s' % (
                slot, 'nz' if pre[5] else 0, 'nz' if pre[4] else 0, not any(frame_rows(get, ofr)), ox > 200, d == want)] += 1
        if small and d != want:
            f.append(('plot delta differs from the model (old ^ new image)', len(set(d) ^ set(want)) + 1))
        if not small:
            world.touch['plot with a move beyond one cell or x > 240 (model not compared)'] += 1
        post = _slot_state(lambda a: o[a], slot)
        if post != (nx, ny, newf):
            f.append(('slot state after the plot is not the drawn tuple', post, (nx, ny, newf)))
        if p.ov.get(HS + slot) != 1:
            f.append(('slot flag not set by the plot',))
        world.pending.append((slot, d, post, {a: p.ov[a] for a in hsw}))
        world.touch['plots'] += 1
    elif kind == 'dia':
        stack_b = get(sp0 + 3)           # B of the outer BC (entries left): SP -> HL, BC
        idx = 5 - stack_b
        pix = _pix_of(o.ov)
        if 0 <= idx < 5:
            world.dia[idx] = pix
            if p.ov.get(HS + 3 + idx) != 1:
                f.append(('diamond flag not set', idx))
        else:
            f.append(('diamond index out of range', idx))
    elif kind == 'c':
        for a in o.ov:
            if 0x4000 <= a < 0x5800 and o.ov[a] == 0:
                world.F.pop(a, None)
        world.drawn.clear()
        world.dia.clear()
        for i in range(8):
            if p.ov.get(HS + i, 1) != 0:
                f.append(('flags not cleared by a screen clear', i))
                break
    if kind != 'pl':
        for a in hsw:
            world.hs[a - HS] = p.ov[a]
    return f


def patch_rd_old(site):
    return bytes.fromhex(RD_SITES[site][1])


# ---------------------------------------------------------------------------------------------
# The live replay
# ---------------------------------------------------------------------------------------------

KEEP = bool(os.environ.get('FM_KEEP'))
_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the
    same state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    world = World(patch.pats)
    cnt = collections.Counter()
    EVENT = {PLOTTER: ('pl', None), PLOT_END: ('ep', None), 50343: ('c', 50343), 50609: ('c', 50609), DIA_SITE: ('dia', DIA_SITE),
             ISR_SITE: ('isr', ISR_SITE)}
    for a in RD_SITES:
        EVENT[a] = ('rd', a)
    WATCH = set(EVENT) | set(site_bytes) | {ISR_SITE}
    states = []

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        regs = None

        def __setitem__(s, a, v):
            if st['on'] and type(a) is int:
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                elif a in world.F and a < 0x5800 and s.regs[24] not in PLOT_WRITERS:
                    # any other writer (clear, redraw, scroller) replaces the byte in both worlds
                    del world.F[a]
                    world.touch['figure bytes overwritten by other writers'] += 1
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            self.memory.regs = self.registers
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc == 49740:
                        st['t0'] = R[25]
                    elif pc == ISR_SITE and 't0' in st:
                        d = R[25] - st['t0']
                        world.touch['ISR entry to hook site, T total'] += d
                        world.touch['ISR entry to hook site, T max'] = max(world.touch['ISR entry to hook site, T max'], d)
                    if pc in WATCH:
                        cnt[pc] += 1
                        ev = EVENT.get(pc)
                        if ev:
                            kind, site = ev
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((kind, site, list(R), bytes(G(mem, a) for a in range(65536)),
                                               world.ns.copy(), bytes(world.hs), dict(world.F), dict(world.drawn)))
                            keep = (list(R), bytes(G(mem, a) for a in range(65536)), world.ns.copy(),
                                    bytes(world.hs), dict(world.F), dict(world.drawn), list(world.pending),
                                    dict(world.dia)) if KEEP else None
                            fl = event(patch, kind, site if site is not None else pc, get, R, world, alt, _rw())
                            if fl and KEEP and not os.path.exists('/tmp/fm/fail_%s.pkl' % kind):
                                import pickle
                                pickle.dump((kind, site, st['frame'], keep, fl), open('/tmp/fm/fail_%s.pkl' % kind, 'wb'))
                            c[kind] += 1
                            for k in fl:
                                fail('%s: %s' % (kind, k[0] if isinstance(k, tuple) else k),
                                     k[1:] if isinstance(k, tuple) else ())
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
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
    # no jump into the middle of a patched instruction: interior bytes run only after their site
    for a, old_, new in patch.sites:
        for k in range(1, len(old_)):
            if cnt[a + k] > cnt[a]:
                c['jump into a patched instruction (%d)!' % (a + k)] += 1
    for k, v in world.touch.items():
        c[k] += v
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests (states from verify(collect=n)), negative controls
# ---------------------------------------------------------------------------------------------

def _isr_case(patch, base, alt, Sim, slots, dias=(), lastf=None, twice=True):
    """slots {s: (x, y, frame, E)}, dias [(i, id, x, y, shown)]. Runs the interrupt hook twice (the
    second time with the pattern cache hot). Returns (failures, pixels compared)."""
    kind, site, R, mem, ns, hs, Fd, dr = base
    m = bytearray(mem)
    world = World(patch.pats)
    world.ns = ns.copy()
    world.hs = bytearray(32)
    for s, (x, y, fr, e) in slots.items():
        b = SLOTS + 8 * s
        m[b], m[b + 1], m[b + 2], m[b + 6] = x, y, fr, e
        world.drawn[s] = (x, y, fr)
        world.hs[s] = 1
        world.hs[8 + s] = 0xFF if lastf is None else lastf
    m[ROOM] = 3                                     # a room whose table is a scratch span (the base state may be a menu)
    p = 0xF500
    m[OBJTAB + 6], m[OBJTAB + 7] = p & 255, p >> 8
    for k in range(15):
        m[p + k] = 0
    for i, idv, x, y, shown in dias:
        m[p + 3 * i], m[p + 3 * i + 1], m[p + 3 * i + 2] = idv, x, y
        world.hs[3 + i] = 1 if shown else 0
        # the original has it on the screen (7 overwritten rows)
        for r, v in enumerate(diamond_rows(m.__getitem__)):
            py = y + 2 + r
            if 0 <= py < 192 and (x >> 3) < 32:
                m[0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | x >> 3] = v
    fl = []
    n = 0
    for _ in range(2 if twice else 1):
        before = len(world.touch)
        fl += event(patch, 'isr', ISR_SITE, m.__getitem__, list(R), world, alt, Sim)
        n += world.touch['slot pixels compared'] + world.touch['diamond pixels compared']
    return fl, n


def _rd_case(patch, base, alt, Sim, site, de, slots, rnd):
    """Virtual read at one rd site: the original reads scenery ^ figures, the patched code scenery."""
    kind, site0, R, mem, ns, hs, Fd, dr = base
    m = bytearray(mem)
    for a in range(0x4000, 0x5800):
        m[a] = rnd.randrange(256)
    world = World(patch.pats)
    world.hs = bytearray(32)
    for s, (x, y, fr) in slots.items():
        b = SLOTS + 8 * s
        m[b], m[b + 1], m[b + 2] = x, y, fr
        world.drawn[s] = (x, y, fr)
        world.hs[s] = 1
        for a, v in _model_screen(frame_rows(m.__getitem__, fr), x, y).items():
            world.F[a] = world.F.get(a, 0) ^ v
            m[a] ^= v                               # the live (original) screen has the figure
    r = list(R)
    r[24] = site
    r[4], r[5] = de >> 8, de & 255
    sp = 0xB000
    r[12] = sp
    m[sp], m[sp + 1] = 0x00, 0x90
    return event(patch, 'rd', site, m.__getitem__, r, world, alt, Sim)


def unit_tests(patch, states, neg=None):
    import random
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    rnd = random.Random(1)
    isr = [s for s in states if s[0] == 'isr']
    if not isr:
        return c
    base = isr[len(isr) // 2]
    # 1. every frame x edge positions x slots, palette from E
    nfr = 96
    for s in range(3):
        for fr in range(nfr):
            for (x, y) in ((0, 0), (7, 100), (8, 167), (100, 168), (200, 191), (232, 20), (240, 80)):
                e = rnd.choice((0, 1, 2, 3, 4, 5, 6, 7, 0x40, 0x45, 0x47, 0x43))
                fl, n = _isr_case(patch, base, alt, Sim, {s: (x, y, fr, e)})
                c['slot cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                if fl and c['  fail example'] < 3:
                    c['  fail example'] += 1
                    c['  slot %d frame %d x %d y %d: %s' % (s, fr, x, y, str(fl[:1])[:200])] += 1
    # 2. all three slots at once, overlapping, flag combinations; hidden slots (flag 0) show nothing
    for k in range(60):
        slots = {s: (rnd.randrange(0, 241), rnd.randrange(0, 192), rnd.randrange(nfr), rnd.randrange(8))
                 for s in range(3) if rnd.random() < 0.7}
        fl, n = _isr_case(patch, base, alt, Sim, slots)
        c['multi-slot cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    fl, n = _isr_case(patch, base, alt, Sim, {})
    c['no slot shown cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    # 3. collectables: ids, positions, flags (shown, id 0, flag off)
    for k in range(80):
        dias = [(i, rnd.choice((0, 1, 5, 31)), rnd.randrange(0, 249), rnd.randrange(0, 185), rnd.random() < 0.7)
                for i in range(5)]
        fl, n = _isr_case(patch, base, alt, Sim, {}, dias)
        c['collectable cases %s' % ('ok' if not fl else 'FAIL!')] += 1
    # 4. virtual read at every site over the cells around the figures
    rdb = [s for s in states if s[0] == 'rd'] or isr
    base_rd = rdb[0]
    sites = sorted(RD_SITES)
    for k in range(400):
        slots = {s: (rnd.randrange(0, 241), rnd.randrange(0, 150), rnd.randrange(nfr)) for s in range(3)
                 if rnd.random() < 0.8}
        site = sites[k % len(sites)]
        if slots:
            s0 = rnd.choice(list(slots))
            x, y, _ = slots[s0]
        else:
            x, y = rnd.randrange(0, 240), rnd.randrange(0, 150)
        px, py = x + rnd.randrange(-8, 24), y + rnd.randrange(-2, 26)
        px, py = max(0, min(255, px)), max(0, min(191, py))
        de = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
        fl = _rd_case(patch, base_rd, alt, Sim, site, de, slots, rnd)
        c['virtual read cases %s' % ('ok' if not fl else 'FAIL!')] += 1
        if fl and c['  rd fail example'] < 3:
            c['  rd fail example'] += 1
            c['  site %d de %04X slots %s: %s' % (site, de, slots, str(fl[:1])[:200])] += 1
    fl = setup_test(patch, isr[0][3])
    c['setup routine %s' % ('ok' if not fl else 'FAIL!')] += 1
    if fl:
        c['  setup: %s' % (fl,)] += 1
    # 5. negative controls: each broken patch must FAIL the same checks
    if neg:
        for name, bp, run in neg:
            bad = 0
            tot = 0
            for k in range(30):
                tot += 1
                bad += 1 if run(bp, k) else 0
            c['negative control %s: %s' % (name, 'detected' if bad else 'NOT DETECTED!')] += 1
    return c


def setup_test(patch, mem64):
    """Run the start-up routine (0xD000) with bank 11 behind NextReg $57 = 22: the diamond pattern lands in
    pattern 6, patterns 0-5 are cleared, palette index 4 is white, every sprite is hidden, sprites are on,
    $57 is back to 21 and nothing else is touched."""
    f = []
    ns = NextState()
    ns.pat[:] = bytes([0x77]) * 16384                   # garbage the routine must overwrite
    bank = bytearray(16384)
    bank[0:128] = patch.extra_banks[11][0:128] if patch.extra_banks else patch.pats
    base = bytearray(mem64)
    base[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra

    class M(list):
        def __getitem__(s, a):
            if type(a) is int and a >= 0xE000 and ns.nr.get(0x57) == 22 and a < 0x10000:
                return bank[a - 0xE000]
            return list.__getitem__(s, a)

        def __setitem__(s, a, v):
            if type(a) is int and a >= 0x4000:
                list.__setitem__(s, a, v)
    mem = M(base)
    regs = [0] * 28
    regs[12] = 0xB800
    regs[24] = 0xD000
    mem[0xB800], mem[0xB801] = 0xFE, 0xFF
    sim = _machine(_rw(), mem, regs, ns, 'o')
    if not _run(sim, lambda r: r[24] == 0xFFFE and r[12] == 0xB802, 100000):
        return ['setup did not return']
    if bytes(ns.pat[PAT_DIA * 128:PAT_DIA * 128 + 128]) != patch.pats:
        f.append('diamond pattern not uploaded')
    if any(ns.pat[:PAT_DIA * 128]):
        f.append('patterns 0-5 not cleared')
    if bytes(ns.pat[(PAT_DIA + 1) * 128:]) != bytes([0x77]) * (16384 - (PAT_DIA + 1) * 128):
        f.append('setup wrote beyond pattern 6')
    if ns.pal.get(DIA_INDEX) != 0xB6:
        f.append('diamond colour')
    if ns.nr.get(0x4B) != 0 or ns.nr.get(0x15) != 1 or ns.nr.get(0x57) != 21:
        f.append(('transparency / sprites on / MMU7', ns.nr.get(0x4B), ns.nr.get(0x15), ns.nr.get(0x57)))
    if any(a[3] & 0x80 for a in ns.attr):
        f.append('a sprite is visible after setup')
    other = [e for e in ns.events if e[0] == 'nr' and e[1] not in (0x57, 0x43, 0x40, 0x41, 0x4B, 0x34, 0x38, 0x15)]
    if other:
        f.append(('other NextRegs', other[:2]))
    return f


def negative_patches(patch, states):
    """[(name, broken patch, run(patch, k) -> failure list)]. Each uses the broken patch's own bytes."""
    import copy
    out = []
    alt_good = _alt(patch)
    Sim = _rw()
    isr = [s for s in states if s[0] == 'isr']
    rdb = [s for s in states if s[0] == 'rd']
    if not isr:
        return out
    base = isr[len(isr) // 2]
    # (a) pixel conversion table with one wrong entry
    q = copy.copy(patch)
    rc = bytearray(patch.rom_code)
    nt = patch.syms['ntab'] - ROM_ORG
    rc[nt + 6] ^= 0x11
    q.rom_code = bytes(rc)
    page = bytearray(patch.page)
    page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rc)] = rc
    q.page = bytes(page)

    def run_a(bp, k):
        fr = 3 + k
        fl, _ = _isr_case(bp, base, _alt(bp), Sim, {0: (100, 80, fr, 7)})
        return fl
    out.append(('wrong pixel table', q, run_a))
    # (b) no virtual read: the rd sites are not patched
    q2 = copy.copy(patch)
    q2.sites = [t for t in patch.sites if t[0] not in RD_SITES]
    if rdb:
        import random
        rr = random.Random(7)

        def run_b(bp, k):
            slots = {0: (100, 60, 3 + k)}
            x, y, _ = slots[0]
            px, py = x + 2 + k % 6, y + 4 + k % 12
            de = 0x4000 | (py & 0xC0) << 5 | (py & 7) << 8 | (py & 0x38) << 2 | px >> 3
            return _rd_case(bp, rdb[0], _alt(bp), Sim, 51159, de, slots, rr)
        out.append(('no virtual read', q2, run_b))
    return out


def convergence(rzx_path, stop=None):
    """F and AF' are scratch in the plotter (CP L at 48195, the EX AF,AF' loop at 47950 / 48103): after a plot
    they depend on the screen bytes the plotter read, which the patched build reads without the figure.
    Prove they are dead: replay the original twice, the second time with F and AF' scrambled at every
    plot end (48220),
    and compare the whole memory at the end of every frame. -> (frames, scrambles, first diverging frame)."""
    import hashlib
    import random
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator

    def run(scramble):
        st = {'frame': 0, 'sim': None, 'n': 0}
        hashes = []
        rnd = random.Random(5)

        class Sm(Simulator):
            def __init__(self, memory, registers=None, state_=None, config=None):
                super().__init__(memory, registers, state_, config)
                st['sim'] = self
                R, ops = self.registers, self.opcodes
                f = ops[0xDD]

                def dd():
                    if R[24] == PLOT_END:
                        st['n'] += 1
                        R[1], R[16], R[17] = rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)
                    f()
                if scramble:
                    ops[0xDD] = dd
        _nf = rzxplay.RZXTracer.next_frame

        def next_frame(self):
            st['frame'] += 1
            if st['sim'] is not None:
                hashes.append(hashlib.md5(bytes(st['sim'].memory[0x4000:])).digest())
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
        return hashes, st['n']
    h0, _ = run(False)
    h1, n = run(True)
    first = next((i for i, (a, b) in enumerate(zip(h0, h1)) if a != b), None)
    if first is None and len(h0) != len(h1):
        first = min(len(h0), len(h1))
    return len(h0), n, first


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : fireman (figure plotter 47440 and the collectables -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain),
                                         'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = FiremanPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames: %s -> %s' % (os.path.basename(r), c['frames'],
                                                     {k: v for k, v in c.items() if not k.endswith('!') and k != 'frames'},
                                                     'IDENTICAL' if not fails else 'FAILED %s' % fails))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        fr, n, first = convergence(r, getattr(a, 'quick', None))
        ok = ok and first is None
        say("F/AF' check: %d frames, F and AF' scrambled at %d plot ends -> memory identical at every frame end: %s" % (
            fr, n, 'YES' if first is None else 'NO, first difference in frame %s' % first))
    if states:
        u = unit_tests(patch, states, negative_patches(patch, states))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.startswith(' ')},
                                       'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if k.startswith(' '):
                say('            %s' % k.strip())
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
