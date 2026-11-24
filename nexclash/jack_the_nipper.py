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

Stage A (2026-11-23): the redirect only; sprites, the verifier and the unit tests follow (games/jack_the_nipper.md
"Patch plan").
"""
import json
import os

JTN_PAGE = 24               # Next page at MMU slot 1 for the whole game (bank 12's first half)
CODE_ORG = 0x3800           # hook code in the page (asm ORG)
RESTORE = 0x3E00            # restore_tail: the tail's backup, then its code
REGBLOCK = 0x3F00           # the stub's register block (20 bytes)
SCRATCH = (0x2000, 0x3000)  # the scratch shadow the figure draws land in
SHADOW = (0x6000, 0x7000)   # the game's shadow screen
TAIL_ADDR = 0x6F00          # the start-up tail; restore_tail puts its bytes back before the game starts
SITES_ORIG = {0x80C9: 'e5f5a7', 0x8273: 'e5f5a7', 0xAA4A: 'cdf986'}
SITE_OP = {0x80C9: (0xC3, 'e_d16'), 0x8273: (0xC3, 'e_d24'), 0xAA4A: (0xCD, 'e_cmt')}
INTERIORS = (0x80CA, 0x80CB, 0x8274, 0x8275, 0xAA4B, 0xAA4C)

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
# Verify (PLAYBOOK 6): at each figure site in the replay, the original draw and the patched one from the same state
# ---------------------------------------------------------------------------------------------

DRAW = (0x8000, 0x8820)     # the sprite routine and its helpers: a run ends back in the caller, below its stack frame
SITE_KIND = {0x80C9: 'draw16', 0x8273: 'draw24'}


def _overlays(base, page, psite):
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
        """The patched build: the slot-1 page at 0x2000-0x3FFF (RAM), the sites' new bytes."""
        def __init__(s):
            O.__init__(s)
            s.page = bytearray(page)
            s.pw = {}
            s.rom_w = []

        def __getitem__(s, a):
            if 0x2000 <= a < 0x4000:
                return s.page[a - 0x2000]
            v = psite.get(a)
            if v is not None and a not in s.w:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if 0x2000 <= a < 0x4000:
                s.page[a - 0x2000] = v
                s.pw[a] = v
            elif a < 0x2000:
                s.rom_w.append(a)
            else:
                s.w[a] = v
    return O, P


def _writable_slot1(sim, store):
    """SkoolKit drops every write below 0x4000 (its opcodes test addr > 0x3FFF); on the Next slot 1 is this build's
    RAM page. Wrap the store opcodes the draw uses so a write into 0x2000-0x3FFF reaches the page: LD (HL),r,
    LD (HL),n, LD (DE),A, LD (BC),A. A write through any other opcode would still be dropped, and the scratch check
    (the scratch writes = the original's shadow writes moved by 0x4000) fails then."""
    R, mem, ops = sim.registers, sim.memory, sim.opcodes

    def wrap(op, target, value):
        fn = ops[op]

        def g():
            a = target()
            if 0x2000 <= a < 0x4000:
                v = value()
                fn()
                store(a, v)
            else:
                fn()
        ops[op] = g
    hl = lambda: R[6] << 8 | R[7]
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        wrap(op, hl, lambda ri=ri: R[ri])
    wrap(0x36, hl, lambda: mem[(R[24] + 1) & 0xFFFF])
    wrap(0x12, lambda: R[4] << 8 | R[5], lambda: R[0])
    wrap(0x02, lambda: R[2] << 8 | R[3], lambda: R[0])


def _run(sim, sp0, limit=3000000):
    """Step until the draw has returned to its caller: PC outside DRAW with SP above the site's SP."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    for _ in range(limit):
        if not DRAW[0] <= R[24] < DRAW[1] and R[12] > sp0:
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


def pair(patch, regs, base):
    """One figure draw from one state, original and patched. -> (Counter of failures, details)"""
    import collections
    from skoolkit.simulator import Simulator
    from .hooklib import CMP
    from .simpool import machine
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P = _overlays(base, patch.page, psite)
    o, p = O(), P()
    so = machine(Simulator, o, list(regs), 'jo')
    sp = Simulator(p, {})                   # not pooled: its store opcodes are wrapped for the slot-1 page
    sp.registers[:] = list(regs)
    _writable_slot1(sp, p.__setitem__)
    sp0 = regs[12]
    bad = collections.Counter()
    bad_ok = collections.Counter()
    det = []
    if not (_run(so, sp0) and _run(sp, sp0)):
        bad['did not return!'] += 1
        return bad, det
    ro, rp = so.registers, sp.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff == [22] and rp[22] == ro[22] - 0x40:
        # H' holds the draw's last address, moved like H: dead if the game overwrites it before reading it
        if dead_after(base, o.w, ro, 22, rp[22]):
            bad_ok['H\' moved address (dead)'] += 1
        else:
            bad['H\' moved address read later!'] += 1
    elif diff:
        bad['registers differ!'] += 1
        det.append(('registers', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    shadow_o = {a: v for a, v in o.w.items() if SHADOW[0] <= a < SHADOW[1]}
    rest_o = {a: v for a, v in o.w.items() if not SHADOW[0] <= a < SHADOW[1]}
    shadow_p = {a for a in p.w if SHADOW[0] <= a < SHADOW[1]}
    rest_p = {a: v for a, v in p.w.items() if not SHADOW[0] <= a < SHADOW[1]}
    if shadow_p:
        bad['patched draw wrote the real shadow!'] += 1
        det.append(('shadow writes', sorted(shadow_p)[:6]))
    stack = {a for a in set(rest_o) | set(rest_p) if ro[12] - 0x100 <= a < ro[12] and rest_o.get(a) != rest_p.get(a)}
    if stack and all(rest_p.get(a) == rest_o.get(a, -1) - 0x40 for a in stack):
        bad_ok['stack below SP: pushed address moved (dead)'] += 1      # popped bytes below the caller's SP
        for a in stack:
            rest_o.pop(a, None)
            rest_p.pop(a, None)
    if rest_o != rest_p:
        bad['memory outside the shadow differs!'] += 1
        ks = sorted(set(rest_o) ^ set(rest_p) | {a for a in rest_o if rest_p.get(a) != rest_o[a]})
        det.append(('memory', ['%04X' % a for a in ks[:8]]))
    moved = {a - 0x4000 for a in shadow_o}
    scratch = {a for a in p.pw if SCRATCH[0] <= a < SCRATCH[1]}
    if moved != scratch:
        bad['scratch writes are not the shadow writes moved by 0x4000!'] += 1
        det.append(('scratch', len(moved), len(scratch), sorted(moved ^ scratch)[:6]))
    other_page = {a for a in p.pw if not SCRATCH[0] <= a < SCRATCH[1]}
    if other_page:
        bad['draw wrote the page outside the scratch!'] += 1
        det.append(('page writes', ['%04X' % a for a in sorted(other_page)[:6]]))
    if p.rom_w:
        bad['draw wrote the ROM area!'] += 1
    return bad, det, len(shadow_o), bad_ok


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Differential test (PLAYBOOK 6) at the two figure sites. -> (Counter, examples, states)"""
    import collections
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []

    def on(pc, sim):
        regs, base = list(sim.registers), bytes(sim.memory[:65536])
        r = pair(patch, regs, base)
        bad, det = r[0], r[1]
        c[SITE_KIND[pc]] += 1
        if len(r) > 2:
            c['figure bytes redirected'] += r[2]
            for k, n in r[3].items():
                c[k] += n
        for k, n in bad.items():
            c[k] += n
            if len(ex[k]) < 5:
                ex[k].append((c['frames seen'], hex(pc), det))
        if collect and len(states) < collect:
            states.append((pc, regs, base))

    frames, err = RZ.trace(rzx_path, set(SITE_KIND), on, stop=stop)
    c['frames'] = frames
    if err:
        c['replay desync!'] += 1
        ex['replay desync!'].append(err)
    return c, dict(ex), states
