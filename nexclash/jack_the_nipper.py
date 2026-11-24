"""Jack the Nipper (Gremlin Graphics, 1986, 48K) engine 'jack_the_nipper'. Additive module: reachable only through
is_jack_the_nipper().

Game facts (games/jack_the_nipper.md): the sprite routine 0x8009 draws each object masked (AND mask, OR graphics)
into a shadow screen at 0x6000-0x6FFF and marks its cells (0x7D00-0x7EFF); the copier 0x86F9 copies marked cells to
the display, and 0x8735 restores them from the tile map. Interrupts are off for the whole game; nothing syncs it to
the frame, so the work it does is its pace.

Hooks (asm/jack_the_nipper_hooks.asm, Next page JTN_PAGE at MMU slot 1 for the whole game; the game never reads the
ROM there): at the two returns from the address helper 0x87BB (0x80C9: 16-wide figures, 0x8273: 24-wide) the shadow
address moves to a scratch shadow at 0x2000-0x2FFF (RES 6,H), so the game's own draw runs unchanged (the same work,
so the same pace) and the real shadow keeps the background. The cell marks take only H bits 3 and 0-2 and L (0x8123),
so they mark the same cells.

The commit at the copier's entry 0x86F9 turns the recorded figures into 4-bit sprites: black lines, the body in the
paper of the cell under the figure's feet (one palette bank per Spectrum colour), mirrored by the sprite's X mirror.
Stage B (2026-11-23): sprites; the verifier checks the redirect so far (games/jack_the_nipper.md "Patch plan").
"""
import json
import os

JTN_PAGE = 24               # Next page at MMU slot 1 for the whole game (bank 12's first half)
CODE_ORG = 0x3600           # hook code in the page (asm ORG); state 0x3000-0x35FF below it
RESTORE = 0x3E00            # restore_tail: the tail's backup, then its code
REGBLOCK = 0x3F00           # the stub's register block (20 bytes)
SCRATCH = (0x2000, 0x3000)  # the scratch shadow the figure draws land in
SHADOW = (0x6000, 0x7000)   # the game's shadow screen
TAIL_ADDR = 0x6F00          # the start-up tail; restore_tail puts its bytes back before the game starts
SITES_ORIG = {0x80C9: 'e5f5a7', 0x8273: 'e5f5a7', 0x86F9: '21ff7c'}
SITE_OP = {0x80C9: (0xC3, 'e_d16'), 0x8273: (0xC3, 'e_d24'), 0x86F9: (0xC3, 'e_cmt')}
INTERIORS = (0x80CA, 0x80CB, 0x8274, 0x8275, 0x86FA, 0x86FB)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'jack_the_nipper.json'),
              os.path.join(_HERE, 'jack_the_nipper.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jack_the_nipper.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_jack_the_nipper(snap):
    """True only for Jack the Nipper: 48K and the address helper 0x87BB's bytes."""
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    a, sig = int(sg['addr']), bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[a:a + len(sig)]) == sig


def restore_tail(p, s):
    """The start-up tail puts the snapshot's bytes back before the game starts (as Green Beret's): the tail jumps to
    code in the slot-1 page, which copies a backup over the tail and runs the tail's register restore again, so no
    game memory is assumed dead. Call before the page goes into extra_banks; idempotent (check() applies a copy
    again)."""
    from . import z80tonex as zt
    tail, _, restore, _ = zt.build_tail(s, p.tail_addr, p.slot1, False)
    entry = RESTORE + len(tail)
    code = (b'\xF3\x21' + zt.w16(RESTORE) + b'\x11' + zt.w16(p.tail_addr) + b'\x01' + zt.w16(len(tail)) + b'\xED\xB0'
            + tail[restore:])
    end = entry + len(code)
    if end > REGBLOCK:
        raise ValueError('tail restore 0x%04X-0x%04X runs into the register block' % (RESTORE, end))
    page = bytearray(p.page)
    page[RESTORE - 0x2000:entry - 0x2000] = bytes(s.read(p.tail_addr + i) for i in range(len(tail)))
    page[entry - 0x2000:end - 0x2000] = code
    p.page = bytes(page)
    p.original_pc, p.tail_restore_bytes, s.pc = s.pc, len(tail), entry


class _PagePatch:
    """What both builds share: the slot-1 page (scratch shadow, code, register block) and restore_tail."""
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = True
    keep_printer_buffer = True              # the game reads and runs code at 0x5B00-0x5BBC
    tail_addr = TAIL_ADDR

    def __init__(self, code=b''):
        page = bytearray(8192)
        page[CODE_ORG - 0x2000:CODE_ORG - 0x2000 + len(code)] = code
        if CODE_ORG + len(code) > RESTORE:
            raise ValueError('hook code runs into the tail restore')
        self.page = bytes(page)
        self.slot1 = (JTN_PAGE, REGBLOCK)
        self.sites = []
        self.extra_banks = {JTN_PAGE // 2: self.page + bytes(8192)}

    def _check(self, ram):
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Jack the Nipper patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        self._check(ram)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])
        restore_tail(self, snap)
        self.extra_banks = {JTN_PAGE // 2: self.page + bytes(8192)}


class PlainPatch(_PagePatch):
    """The plain .nex: no hooks; the slot-1 page holds only the tail restore."""
    name = 'Jack the Nipper plain conversion'


class JtnPatch(_PagePatch):
    name = 'Jack the Nipper figures -> hardware sprites (slot-1 page, scratch-shadow redirect)'

    def __init__(self, prof=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if self.syms['code_start'] != CODE_ORG:
            raise ValueError('hook code assembled at 0x%04X, not CODE_ORG' % self.syms['code_start'])
        super().__init__(bytes.fromhex(h['page']))
        self.stub_extra = bytes.fromhex(h['setup'])      # the sprite palette and NR 0x15, once (asm `setup`)
        self.setup_call = self.syms['setup']
        self.sites = [(a, bytes.fromhex(old), bytes([SITE_OP[a][0]]) + self.syms[SITE_OP[a][1]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]


def build(z80, out, name, say=print):
    """Both builds with their boot checks. -> (plain path, sprites path, problems)"""
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    bad = []
    paths = []
    for label, patch, suffix in (('Plain', PlainPatch(), ''), ('Sprites', JtnPatch(), '_sprites')):
        path = os.path.join(out, name + suffix + '.nex')
        conv = zt.convert(z80, path, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
        b = check(path, z80, patch, (conv[1], conv[1] + len(conv[2])))
        say('%-10s: %s  %s  boot %s  (tail 0x%04X, %d bytes, put back)' % (
            label, os.path.basename(path), md5(path), 'OK' if not b else 'MISMATCH %s' % str(b[:3])[:200],
            conv[1], len(conv[2])))
        bad += b
        paths.append(path)
    return paths[0], paths[1], bad


# ---------------------------------------------------------------------------------------------
# Verify (PLAYBOOK 6): at each site in the replay, the original code and the patched one from the same state
# ---------------------------------------------------------------------------------------------

DRAW = (0x8000, 0x8820)     # the sprite routine and its helpers: a draw ends back in the caller, below its stack frame
COPY = (0x86F9, 0x8735)     # the copier: it ends back in its caller
SITE_KIND = {0x80C9: 'draw16', 0x8273: 'draw24', 0x86F9: 'copy'}
STATE = (0x3000, 0x3600)    # the page's hook state and stack
PLAY = (256, 128)           # the play area: shadow / screen rows 0-127


def shadow_addr(x, y):
    return 0x6000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3


class NextSide:
    """The Next as the hooks drive it, across the whole replay: NextRegs (NR 7 read back as the hardware composes
    it), the sprite pattern port (0x303B selects, 0x5B writes on) and the attribute port (0x57: attribute 4 only when
    attribute 3 bit 6 is set)."""

    def __init__(s):
        s.nr = {}
        s.sel = 0
        s.pat = bytearray(16384)
        s.patp = 0
        s.attr = bytearray(640)
        s.an = s.ab = 0
        s.events = []

    def nextreg(s, r, v):
        s.nr[r] = v

    def read_port(s, regs, port):
        if port == 0x243B:
            return s.sel
        if port == 0x253B:
            v = s.nr.get(s.sel, 0)
            return (v & 3) << 4 | (v & 3) if s.sel == 0x07 else v
        s.events.append(('in', port))
        return 0xFF

    def write_port(s, regs, port, v, *x):
        lo = port & 0xFF
        if port == 0x243B:
            s.sel = v
        elif port == 0x253B:
            s.nextreg(s.sel, v)
        elif port == 0x303B:
            s.patp = (v & 0x3F) << 8 | (0x80 if v & 0x80 else 0)
            s.an, s.ab = v & 0x7F, 0
        elif lo == 0x5B:
            s.pat[s.patp & 0x3FFF] = v
            s.patp += 1
        elif lo == 0x57:
            s.attr[5 * s.an + s.ab] = v
            if s.ab == 3 and not v & 0x40:
                s.attr[5 * s.an + 4] = 0
                s.an, s.ab = (s.an + 1) & 127, 0
            elif s.ab == 4:
                s.an, s.ab = (s.an + 1) & 127, 0
            else:
                s.ab += 1
        else:
            s.events.append(('out', port, v))


def render(ns):
    """The visible sprites as {(X, Y): (pixel, bank)} in sprite coordinates (the screen's top-left = (32, 32)),
    sprite 127 on top (NR 0x15 bit 6, set by setup) -> (pixels, problems)."""
    px, bad = {}, []
    a, pat = ns.attr, ns.pat
    for n in range(128):
        b0, b1, b2, b3, b4 = a[5 * n:5 * n + 5]
        if not b3 & 0x80:
            continue
        if not (b3 & 0x40 and b4 & 0x80):
            bad.append(('sprite %d is not a 4-bit anchor' % n, b3, b4))
            continue
        X, Y = b0 | (b2 & 1) << 8, b1 | (b4 & 1) << 8
        base, bank, xm = (b3 & 0x3F) << 8 | (b4 >> 6 & 1) << 7, b2 >> 4, b2 >> 3 & 1
        for r in range(16):
            for c in range(16):
                v = pat[base + r * 8 + c // 2]
                v = v >> 4 if c % 2 == 0 else v & 15
                if v:
                    px[(X + (15 - c if xm else c)) & 0x1FF, (Y + r) & 0x1FF] = (v, bank)
    return px, bad


def figure_of(pc, regs, get):
    """The figure a draw at site pc is about to make, from the original's state there."""
    ix = regs[8] << 8 | regs[9]
    t = get(ix + 2)
    width = 2 if pc == 0x80C9 else 3
    rows = (16 if t & 1 else 24) if pc == 0x80C9 else (24 if t & 4 else 32 if t & 8 else 40)
    h, l = regs[6], regs[7]
    x = (l & 31) * 8 + regs[0]
    y = (h & 0x18) << 3 | (l & 0xE0) >> 2 | (h & 7)
    attr = get(0x5800 + (y >> 3) * 32 + ((x + width * 4) >> 3 & 31))
    return dict(gfx=regs[20] << 8 | regs[21], mask=regs[4] << 8 | regs[5], rows=rows, width=width, x=x, y=y,
                mirror=not get(ix + 4) & 1, bank=(attr >> 3 & 7) | (8 if attr & 0x40 else 0))


def figure_pixels(f, get):
    """{(x, y): 1 graphics / 2 mask clear} of a figure on the screen (rows stored bottom first; the mirrored draw
    flips the image across its width, at the same place)."""
    out = {}
    w8 = f['width'] * 8
    for r in range(f['rows']):
        for b in range(f['width']):
            g = get((f['gfx'] + r * f['width'] + b) & 0xFFFF)
            m = get((f['mask'] + r * f['width'] + b) & 0xFFFF)
            for bit in range(8):
                gb, mb = g >> (7 - bit) & 1, m >> (7 - bit) & 1
                v = 1 if gb else 2 if not mb else 0
                if v:
                    c = b * 8 + bit
                    out[f['x'] + (w8 - 1 - c if f['mirror'] else c), f['y'] - r] = v
    return out


def _overlays(base, vpage, psite):
    class O:
        """The original: ROM below 0x4000 (writes go nowhere), RAM from the replay."""
        def __init__(s):
            s.w = {}

        def __getitem__(s, a):
            v = s.w.get(a)
            return base[a] if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.w[a] = v

        def __len__(s):
            return 65536

    class P(O):
        """The patched build: its page at 0x2000-0x3FFF (RAM, kept across the replay), the sites' new bytes."""
        def __init__(s):
            O.__init__(s)
            s.page = vpage
            s.pw = {}
            s.err = []
            s.R = None

        def __getitem__(s, a):
            if 0x2000 <= a < 0x4000:
                return s.page[a - 0x2000]
            v = psite.get(a)
            if v is not None and a not in s.w:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if 0x2000 <= a < 0x4000:
                hook = s.R is not None and 0x2000 <= s.R[24] < 0x4000
                if STATE[0] <= a < STATE[1] and not hook:
                    s.err.append(('game code wrote the hook state', a, s.R[24] if s.R else None))
                if not STATE[0] <= a < STATE[1] and not SCRATCH[0] <= a < SCRATCH[1]:
                    s.err.append(('write to the page outside state and scratch', a))
                s.page[a - 0x2000] = v
                s.pw[a] = v
            elif a < 0x2000:
                s.err.append(('write to the ROM area', a))
            else:
                if a in psite:
                    s.err.append(('wrote a patch site', a))
                s.w[a] = v
    return O, P


def _writable_slot1(sim, store):
    """SkoolKit drops every write below 0x4000 (its opcodes test addr > 0x3FFF); on the Next slot 1 is this build's
    RAM page. Wrap the store opcodes the draw uses so a write into 0x2000-0x3FFF reaches the page: LD (HL),r,
    LD (HL),n, LD (DE),A, LD (BC),A. The hooks' own stores (LD (nn),A / rr, PUSH on the hook stack, LD (IX+d)) go
    through other opcodes: wrapped too where a hook uses them (_hook_stores)."""
    R, mem, ops = sim.registers, sim.memory, sim.opcodes

    def wrap(table, op, target, value):
        fn = table[op]

        def g():
            a = target()
            if 0x2000 <= a < 0x4000:
                v = value()
                fn()
                store(a, v)
            else:
                fn()
        table[op] = g
    hl = lambda: R[6] << 8 | R[7]
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        wrap(ops, op, hl, lambda ri=ri: R[ri])
    wrap(ops, 0x36, hl, lambda: mem[(R[24] + 1) & 0xFFFF])
    wrap(ops, 0x12, lambda: R[4] << 8 | R[5], lambda: R[0])
    wrap(ops, 0x02, lambda: R[2] << 8 | R[3], lambda: R[0])
    _hook_stores(sim, store)


def _hook_stores(sim, store):
    """The stores the hook code makes in its page (state and stack): run each instruction, then write what the Next
    would have written, for the forms the hooks use: LD (nn),A; LD (nn),HL; LD (nn),rr (ED); LD (nn),SP (ED 73);
    PUSH rr / CALL (to the hook stack); LD (IX+d),r / n. A form missed here leaves the page short of a byte and the
    sprite check fails."""
    R, mem, ops, ed = sim.registers, sim.memory, sim.opcodes, sim.after_ED

    def pre(table, op, writes):
        fn = table[op]

        def g():
            ws = [(a, v) for a, v in writes() if 0x2000 <= a < 0x4000]
            fn()
            for a, v in ws:
                store(a, v)
        table[op] = g
    nn = lambda: mem[(R[24] + 1) & 0xFFFF] | mem[(R[24] + 2) & 0xFFFF] << 8
    nn_ed = lambda: mem[(R[24] + 2) & 0xFFFF] | mem[(R[24] + 3) & 0xFFFF] << 8
    pre(ops, 0x32, lambda: [(nn(), R[0])])
    pre(ops, 0x22, lambda: [(nn(), R[7]), ((nn() + 1) & 0xFFFF, R[6])])
    for op, (hi, lo) in {0x43: (2, 3), 0x53: (4, 5), 0x63: (6, 7)}.items():
        pre(ed, op, lambda hi=hi, lo=lo: [(nn_ed(), R[lo]), ((nn_ed() + 1) & 0xFFFF, R[hi])])
    pre(ed, 0x73, lambda: [(nn_ed(), R[12] & 255), ((nn_ed() + 1) & 0xFFFF, R[12] >> 8)])
    sp2 = lambda hi, lo: [((R[12] - 1) & 0xFFFF, R[hi]), ((R[12] - 2) & 0xFFFF, R[lo])]
    for op, (hi, lo) in {0xC5: (2, 3), 0xD5: (4, 5), 0xE5: (6, 7), 0xF5: (0, 1)}.items():
        pre(ops, op, lambda hi=hi, lo=lo: sp2(hi, lo))
    ret_to = lambda n: (R[24] + n) & 0xFFFF
    pre(ops, 0xCD, lambda: [((R[12] - 1) & 0xFFFF, ret_to(3) >> 8), ((R[12] - 2) & 0xFFFF, ret_to(3) & 255)])
    for op in (0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC):
        pass                                # conditional calls: not in the hooks
    dd = sim.after_DD
    pre(dd, 0xE5, lambda: [((R[12] - 1) & 0xFFFF, R[8]), ((R[12] - 2) & 0xFFFF, R[9])])     # PUSH IX
    ixd = lambda: ((R[8] << 8 | R[9]) + ((mem[(R[24] + 2) & 0xFFFF] ^ 0x80) - 0x80)) & 0xFFFF
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        pre(dd, op, lambda ri=ri: [(ixd(), R[ri])])
    pre(dd, 0x36, lambda: [(ixd(), mem[(R[24] + 3) & 0xFFFF])])


def _run(sim, sp0, span, limit=5000000):
    """Step until the code has returned to its caller: PC outside span with SP above the site's SP."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    for _ in range(limit):
        if not span[0] <= R[24] < span[1] and not 0x2000 <= R[24] < 0x4000 and R[12] > sp0:
            return True
        ops[mem[R[24]]]()
    return False


RUN_ON = 400000             # dead_after: at most this many (Jack's own draw, the last of a frame: up to ~185,000)


def dead_after(base, writes, regs, idx, alt, n=RUN_ON):
    """Whether register idx (H') is dead after the draw: the original machine run on from its return state, once as
    it is and once with idx = alt, in lockstep. The difference may travel (EXX at 0x8014 swaps it into H, EX DE,HL
    at 0x8240 into D); it is dead when every register agrees again (overwritten, for H by the next CALL 0x87BB) and
    memory agrees then too, apart from popped bytes below SP (0x85D0 pushes HL), with both machines on the same PC at
    every step on the way. A different path, or no agreement within n instructions: live."""
    from skoolkit.simulator import Simulator
    from .hooklib import CMP
    mem = bytearray(base)
    for a, v in writes.items():
        mem[a] = v
    sims = []
    for v in (regs[idx], alt):
        r = list(regs)
        r[idx] = v
        sim = Simulator(bytearray(mem), {})
        sim.registers[:] = r
        sims.append(sim)
    A, B = sims
    ra, rb = A.registers, B.registers
    for _ in range(n):
        A.opcodes[A.memory[ra[24]]]()
        B.opcodes[B.memory[rb[24]]]()
        if ra[24] != rb[24]:
            return False
        if all(ra[i] == rb[i] for i in CMP):
            if A.memory == B.memory:
                return True
            sp = ra[12]
            return all(sp - 0x100 <= a < sp for a in range(65536) if A.memory[a] != B.memory[a])
    return False


def pair(patch, regs, base, vpage, vns, span):
    """One site from one state, original and patched (the patched page and Next side carried across the replay).
    -> (failures, allowed, details, original writes, patched page writes)"""
    import collections
    from skoolkit.simulator import Simulator
    from .hooklib import CMP
    from .simpool import machine
    from . import z80n
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P = _overlays(base, vpage, psite)
    o, p = O(), P()
    so = machine(Simulator, o, list(regs), 'jo')
    sp = Simulator(p, {})                   # not pooled: its opcodes are wrapped for the slot-1 page
    sp.registers[:] = list(regs)
    p.R = sp.registers
    _writable_slot1(sp, p.__setitem__)
    z80n.install(sp, vns.nextreg)
    sp.set_tracer(vns)
    vns.events = []
    speed0 = vns.nr.get(0x07, 0)
    bad, ok, det = collections.Counter(), collections.Counter(), []
    sp0 = regs[12]
    if not (_run(so, sp0, span) and _run(sp, sp0, span)):
        bad['did not return!'] += 1
        return bad, ok, det, o.w, p.pw
    for e in p.err:
        bad[e[0] + '!'] += 1
        det.append(e)
    if vns.events:
        bad['port access outside the Next side!'] += 1
        det.append(('ports', vns.events[:4]))
    if vns.nr.get(0x07, 0) != speed0:
        bad['CPU speed not given back!'] += 1
    ro, rp = so.registers, sp.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff == [22] and rp[22] == ro[22] - 0x40:
        # H' holds the draw's last address, moved like H: dead if the game overwrites it before reading it
        if dead_after(base, o.w, ro, 22, rp[22]):
            ok["H' moved address (dead)"] += 1
        else:
            bad["H' moved address read later!"] += 1
    elif diff:
        bad['registers differ!'] += 1
        det.append(('registers', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    shadow_o = {a: v for a, v in o.w.items() if SHADOW[0] <= a < SHADOW[1]} if span is DRAW else {}
    rest_o = {a: v for a, v in o.w.items() if a not in shadow_o}
    shadow_p = {a for a in p.w if SHADOW[0] <= a < SHADOW[1]} if span is DRAW else set()
    rest_p = {a: v for a, v in p.w.items() if a not in shadow_p}
    if shadow_p:
        bad['patched draw wrote the real shadow!'] += 1
        det.append(('shadow writes', sorted(shadow_p)[:6]))
    stack = {a for a in set(rest_o) | set(rest_p) if ro[12] - 0x100 <= a < ro[12] and rest_o.get(a) != rest_p.get(a)}
    if stack and all(rest_p.get(a) == rest_o.get(a, -1) - 0x40 for a in stack):
        ok['stack below SP: pushed address moved (dead)'] += 1      # popped bytes below the caller's SP
        for a in stack:
            rest_o.pop(a, None)
            rest_p.pop(a, None)
    if rest_o != rest_p:
        bad['memory differs!'] += 1
        ks = sorted(set(rest_o) ^ set(rest_p) | {a for a in rest_o if rest_p.get(a) != rest_o[a]})
        det.append(('memory', ['%04X' % a for a in ks[:8]]))
    if span is DRAW:
        moved = {a - 0x4000 for a in shadow_o}
        scratch = {a for a in p.pw if SCRATCH[0] <= a < SCRATCH[1]}
        if moved != scratch:
            bad['scratch writes are not the shadow writes moved by 0x4000!'] += 1
            det.append(('scratch', len(moved), len(scratch), sorted(moved ^ scratch)[:6]))
    return bad, ok, det, o.w, p.pw


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Differential test (PLAYBOOK 6). Figure sites: the redirect (pair). Copier entry: the commit, then the picture:
    the figures drawn since the last copy, modelled from their graphics and masks, must (1) give the original's shadow
    bytes over the background they were drawn on, and (2) be the visible sprites, pixel for pixel, with the colour
    bank and mirror the design gives and the later figure on top. -> (Counter, examples, states)"""
    import collections
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    vpage = bytearray(patch.page)
    vns = NextSide()
    upd = {'figs': [], 'pre': {}}

    def fail(k, info):
        c[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)

    def on(pc, sim):
        regs, base = list(sim.registers), bytes(sim.memory[:65536])
        get = base.__getitem__
        c[SITE_KIND[pc]] += 1
        if pc in (0x80C9, 0x8273):
            upd['figs'].append(figure_of(pc, regs, get))
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, DRAW)
            for a in ow:
                if SHADOW[0] <= a < SHADOW[1]:
                    upd['pre'].setdefault(a, base[a])
                    c['figure bytes redirected'] += 1
        else:
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY)
            picture(get)
        for k, n in ok.items():
            c[k] += n
        for k, n in bad.items():
            for _ in range(n):
                fail(k, (hex(pc), det))
        if collect and len(states) < collect:
            states.append((pc, regs, base))

    def picture(get):
        figs, pre = upd['figs'], upd['pre']
        exp = {}
        for f in figs:                      # later over earlier
            for (x, y), v in figure_pixels(f, get).items():
                exp[x, y] = (v, f['bank'])
        # (1) the model against the original's own drawing: every byte the draws touched
        for a, b0 in pre.items():
            y = (a >> 5 & 0xC0) | (a >> 8 & 7) | (a >> 2 & 0x38)
            x0 = (a & 31) * 8
            want = 0
            for bit in range(8):
                v = exp.get((x0 + bit, y))
                pb = b0 >> (7 - bit) & 1 if v is None else (1 if v[0] == 1 else 0)
                want |= pb << (7 - bit)
            if want != get(a):
                fail('figure model differs from the original drawing!', ('%04X' % a, want, get(a)))
        c['picture bytes checked'] += len(pre)
        # (2) the visible sprites against the model, in the play area
        got, bad = render(vns)
        for b in bad:
            fail('sprite attributes!', b)
        want = {(x + 32, y + 32): v for (x, y), v in exp.items() if 0 <= x < PLAY[0] and 0 <= y < PLAY[1]}
        have = {k: v for k, v in got.items() if 32 <= k[0] < 32 + PLAY[0] and 32 <= k[1] < 32 + PLAY[1]}
        if want != have:
            d = sorted(set(want) ^ set(have) | {k for k in want if have.get(k) != want[k]})
            fail('SPRITE PIXEL difference!', (len(d), d[:4], [(want.get(k), have.get(k)) for k in d[:4]]))
        c['sprite pixels compared'] += len(want)
        upd['figs'], upd['pre'] = [], {}

    frames, err = RZ.trace(rzx_path, set(SITE_KIND), on, stop=stop)
    c['frames'] = frames
    if err:
        fail('replay desync!', err)
    return c, dict(ex), states
