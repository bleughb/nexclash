"""Mad Mix 2 - en el Castillo de los Fantasmas (Topo Soft, 1990, 128K): the original look, made to display on a Next.

The play area is one attribute per stage, so there is no clash to remove. The copy to the screen writes 2, then 3, to port
0xFF: nothing on a 128K, Timex hi-colour in a Next .nex (the picture is garbage; NextZXOS's snapshot loader shows it fine). Both writes become IN A,(0xFF): same bytes,
same T states, same R; A is reloaded before anything reads it. No hooks, no Layer 2, no sprites.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/mad_mix_2.json'
SOURCE_MD5 = 'f5f5262f7a41d3c55408b45878c31d00'
CMP = tuple(hooklib.CMP_R)
SITES = ((0xABEF, b'\xd3\xff', b'\xdb\xff'), (0xAC43, b'\xd3\xff', b'\xdb\xff'))
A_RELOAD = {0xABEF: 0xABF4, 0xAC43: 0xAA62}     # where each site's A dies: LD A,$90 and the handler's next LD A,(6001)
REGBLOCK = 0x3900                               # Sinclair's unused 0xFF fill; the game reads ROM only at 0000-015F
SIGNATURE = {0xABEF: 'D3FF', 0xAC43: 'D3FF', 0x6001: '01', 0x8818: 'CD76A7'}
DECISIONS = {'figures': 'the original look: no clash to remove, one attribute per stage', 'outline': 'none: figures have their own black edge and white fill',
             'pace': 'unchanged code at the game clock', 'enhanced': 'the Spec256 colours for stage group 1, a menu option, off by default'}
PUBLISHER = 'Topo Soft, 1990'


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_mad_mix_2(snap):
    banks = getattr(snap, 'banks', None)
    if banks is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    bank = {0x4000: 5, 0x8000: 2}
    try:
        return all(bytes(banks[bank[a & 0xC000]][a & 0x3FFF:(a & 0x3FFF) + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Mad Mix 2 128K: the copy no longer switches a Next into Timex hi-colour'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = None
    stub_extra = b''

    def __init__(self, source=None, sites=SITES, enhanced=None):
        from .build import rom48
        self.source = str(source) if source else None
        self.sites = [tuple(s) for s in sites]
        self.enhanced = enhanced
        self.colours = None
        if enhanced:
            return self._enhanced(enhanced)
        self.slot1 = (25, REGBLOCK)
        self.altrom = self.altrom0 = (REGBLOCK, REGBLOCK + 20)    # the alt ROM holds only the start-up's register block, over Sinclair's ROM
        self.page = bytearray(rom48()[0x2000:0x4000])
        self.extra_banks = {12: bytes(0x2000) + bytes(self.page)}

    def _enhanced(self, path):
        from .build import rom48
        from . import mad_mix_2_art as art
        h = json.loads((ROOT / 'docs/profiles/mad_mix_2e.json').read_text())['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.colours = art.load(path)
        setup = bytearray.fromhex(h['setup'])
        at = self.syms['l2_pal256'] - 0xD000
        setup[at:at + 512] = self.colours['palette']
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1A00:0x1C00] = bytes(512)
        self.ram[0x1E00:0x2000] = bytes(512)
        tp = art.FIRST_PAGE + self.colours['tile_pages']
        idx = bytearray(self.colours['index'])
        for i in range(art.NFIGS):
            if idx[i * 4 + 3]:
                idx[i * 4] += tp
        self.ram[self.syms['TBL'] - 0x2000:self.syms['TBL'] - 0x2000 + len(idx)] = idx
        self.ram[self.syms['V_GP'] - 0x2000] = tp + len(self.colours['store'])
        self.ram[self.syms['V_FRONT'] - 0x2000] = 16
        self.ram[self.syms['V_BACK'] - 0x2000] = 19
        self.ram[self.syms['V_S0'] - 0x2000] = 255
        s = self.syms
        self.sites = [SITES[0], SITES[1],
                      (0xABC8, b'\xf3\x3a\x7b', b'\xc3' + zt.w16(s['h_flip'])),
                      (0xAC46, b'\xcd\x3f\x92', b'\xc3' + zt.w16(s['h_tile'])),
                      (0xB02A, b'\x3e\x3c\xdd', b'\xc3' + zt.w16(s['h_star'])),
                      (0xA58B, b'\xfe\xff\xc8', b'\xc3' + zt.w16(s['h_fig'])),
                      (0xA89A, b'\xfb\x76\x21', b'\xc3' + zt.w16(s['h_hide'])),
                      (0xA8F9, b'\xcd\x42\xa8', b'\xc3' + zt.w16(s['h_text'])),
                      (0x9157, b'\x21\xb6\x87', b'\xc3' + zt.w16(s['h_lives'])),
                      (0xA548, b'\xf3\xf5\xc5', b'\xc3' + zt.w16(s['h_isr'])),
                      (0xA584, b'\xfb\xc9\x00', b'\xc3' + zt.w16(s['h_isrx']))]
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in [k for k in self.syms if k.startswith('h_')]:
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 8] = self.ram[at:at + 8]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        c = self.colours
        for buf in (16, 19):
            for i in range(3):
                self.extra_banks[buf + i] = c['panel'][i * 16384:(i + 1) * 16384]
        pages = [c['tiles'][i:i + 8192].ljust(8192, b'\xff') for i in range(0, len(c['tiles']), 8192)] + list(c['store']) + [c['glyph']]
        if len(pages) & 1:
            pages.append(b'\xff' * 8192)
        for i in range(0, len(pages), 2):
            self.extra_banks[22 + i // 2] = pages[i] + pages[i + 1]

    def apply(self, snap):
        if not is_mad_mix_2(snap):
            raise ValueError('Not the supported Mad Mix 2 128K release (MD5 %s)' % SOURCE_MD5)
        b = bytearray(snap.banks[2])
        for a, old, new in self.sites:
            at = a - 0x8000
            if bytes(b[at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            b[at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(b) if i == 2 else bytes(snap.banks[i])) for i in range(8))


def build(source, destination, enhanced=None):
    p = Patch(source, enhanced=enhanced)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class _Machine:
    """A 128K machine fed an RZX frame's port readings. Port 0xFF reads are the patch's, so they take no reading."""
    FRAME_T = 70908

    def __init__(self, z80, sites=()):
        from skoolkit import CSimulator
        from skoolkit.simutils import from_snapshot
        from skoolkit.snapshot import Snapshot
        s = Snapshot.get(z80)
        self.sim = from_snapshot(CSimulator, s, config={'int_active': 0})
        self.mem = self.sim.memory
        for a, old, new in sites:
            for i, v in enumerate(new):
                self.mem[a + i] = v
        self.out7ffd = s.out7ffd
        self.ins = iter(())
        self.ports = Counter()
        self.sim.set_tracer(self)

    def read_port(self, registers, port):
        if port & 0xFF == 0xFF:
            self.ports['in ff'] += 1
            return 0xFF
        return next(self.ins, 0xFF)

    def write_port(self, registers, port, value, offset=0):
        if port & 0xFF == 0xFF:
            self.ports['out ff'] += 1
        if port & 0x8002 == 0 and self.out7ffd & 32 == 0:
            self.mem.out7ffd(value)
            self.out7ffd = value

    def frame(self, ins, watch=None):
        from skoolkit.simutils import T, IFF, PC
        self.ins = iter(ins)
        regs = self.sim.registers
        left = [0, regs[PC]]

        class End(Exception):
            pass

        def tr(fc, at):
            if regs[T] >= self.FRAME_T:
                left[:] = [fc, at]
                raise End()
            if watch is not None and at in watch:
                watch[at](self)
        try:
            self.sim.exec_frame(65535, None, tr)
        except End:
            pass
        else:
            raise RuntimeError('frame over the fetch budget')
        regs[T] = 0
        if regs[IFF]:
            if self.mem[left[1]] == 0x76:
                regs[PC] = (regs[PC] + 1) % 65536
            self.sim.accept_interrupt(regs, self.mem, 0)
        return 65535 - left[0]

    def state(self):
        return [bytes(b) for b in self.mem.banks], list(self.sim.registers)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Original and patched machines fed the same recording: at the end of every frame every register with R, all eight RAM
    banks and the frame's fetch count must match, A aside between a site and the point its value dies. Port 0xFF: the patched
    machine must never write it. -> (Counter, examples, states)."""
    from .rzx import read_segments
    from skoolkit.simutils import PC, A
    c, examples = Counter(), defaultdict(list)

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    states = []
    for snap, rec, _ in read_segments(rzx_path):
        break
    from tempfile import NamedTemporaryFile
    from .rzx import extract
    with NamedTemporaryFile(suffix='.z80') as t:
        extract(rzx_path, t.name)
        orig, new = _Machine(t.name), _Machine(t.name, patch.sites)
    live_a = [False]
    passes = Counter()

    def enter(a):
        def f(m):
            passes[a] += 1
            live_a[0] = True
        return f

    def die(m):
        live_a[0] = False
    watch = {s[0]: enter(s[0]) for s in patch.sites}
    watch.update({A_RELOAD[s[0]]: die for s in patch.sites if s[0] in A_RELOAD})
    for n, frame in enumerate(rec.frames):
        if stop is not None and n >= stop:
            break
        ins = rec.data[frame.start:frame.end]
        fo = orig.frame(ins)
        fn = new.frame(ins, watch)
        c['frames'] += 1
        if fo != fn:
            fail('fetch count differs', {'frame': n, 'orig': fo, 'new': fn})
        bo, ro = orig.state()
        bn, rn = new.state()
        c['R comparisons'] += 1
        for i in CMP:
            if i == A and live_a[0]:
                continue
            if ro[i] != rn[i]:
                fail('registers differ', {'frame': n, 'reg': i, 'orig': ro[i], 'new': rn[i], 'pc': hex(ro[PC])})
        for b in range(8):
            if bo[b] != bn[b]:
                diff = [i for i in range(16384) if bo[b][i] != bn[b][i]]
                diff = [i for i in diff if not (b == 2 and any(0 <= (0x8000 + i) - s[0] < len(s[1]) for s in SITES))]
                if diff:
                    fail('RAM differs', {'frame': n, 'bank': b, 'at': hex(diff[0]), 'count': len(diff)})
        if collect and len(states) < collect and passes:
            states.append((bn, rn))
        if progress and n % 2000 == 0:
            progress(n)
    c['original port FF writes'] = orig.ports['out ff']
    c['build port FF writes'] = new.ports['out ff']
    c['site passes'] = sum(passes.values())
    if new.ports['out ff']:
        fail('the build still writes port FF', {'count': new.ports['out ff']})
    if not orig.ports['out ff'] and c['frames'] > 1000:
        fail('the recording never reached the copy', {})
    return c, examples, states


def unit_tests(patch, states, neg=True):
    """The sites alone from every A: only A may change, with the same T, R and flags as the OUT they replace."""
    from skoolkit import CSimulator
    from skoolkit.simutils import A, R, T, PC, F
    from skoolkit.snapshot import Snapshot
    c = Counter()

    class Ports:
        def __init__(self):
            self.out = 0

        def read_port(self, regs, port):
            return 0xFF

        def write_port(self, regs, port, value, offset=0):
            self.out += 1
    for a, old, new in patch.sites:
        for av in range(256):
            res = []
            for code in (old, new):
                memory = [0] * 65536
                memory[a:a + 2] = code
                sim = CSimulator(memory, config={'int_active': 0})
                p = Ports()
                sim.set_tracer(p)
                sim.registers[A] = av
                sim.registers[F] = 0x55
                sim.registers[PC] = a
                sim.run(stop=a + 2)
                res.append((sim.registers[T], sim.registers[R], sim.registers[F], sim.registers[PC], p.out))
            c['site cases'] += 1
            if res[0][:4] != res[1][:4]:
                c['T, R, flags or PC differ!'] += 1
            if new == b'\xdb\xff' and res[1][4] != 0:
                c['the replacement writes a port!'] += 1
    return c


def negative_patches(patch):
    one = lambda i, new: [(s[0], s[1], new if j == i else s[2]) for j, s in enumerate(SITES)]
    return {'first write left in': Patch(patch.source, one(0, b'\xd3\xff')),
            'second write left in': Patch(patch.source, one(1, b'\xd3\xff')),
            'first site as two NOPs (R, T)': Patch(patch.source, one(0, b'\x00\x00')),
            'second site as two NOPs (R, T)': Patch(patch.source, one(1, b'\x00\x00')),
            'a stray byte in game RAM': Patch(patch.source, [(0xABEF, b'\xd3\xff', b'\xdb\xff'), (0x8E73, b'\x00', b'\x01')])}


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched snapshot, bar the tail."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = zt.choose_tail_addr(s, size, None, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size or (nexload and 0x5B00 <= a < 0x5C00):
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


LOAD_SCREEN = 'mad_mix_2_loading.scr'
LOAD_MD5 = 'c551765e986c0fa8c51b967bee022e58'     # the tape's loading screen, 6,912 bytes
COLOURS_FILE = 'mad_mix_2_enhanced.bin'
COLOURS_MD5 = 'd37c129e6ec91774f93ce6a7cfc4f804'   # mad_mix_2_art.py's table from the Spec256 set (Jao Paulo); never in this repo
NEG_STOP = 1500
INT_STOP = 150


def _beside(z80, fname, md5):
    """A local input beside the snapshot, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / fname
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not the expected file (MD5 %s)' % (fname, md5))
    return path


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def _verify_default(z80, rzx, stop):
    c, ex, states = verify(Patch(z80), rzx, stop=stop, collect=1)
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}, states


def _verify_enh(z80, colours, rzx, stop):
    c, ex, _ = verify_enhanced(Patch(z80, enhanced=colours), rzx, stop=stop)
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}


def _interrupts(z80, colours, rzx):
    """The handler at many points of each hook kind, on states from the first INT_STOP frames -> (cases, problems)."""
    p = Patch(z80, enhanced=colours)
    c, ex, states = verify_enhanced(p, rzx, stop=INT_STOP, collect=3)
    cases, bad = 0, [k for k in c if k.endswith('!')]
    for st in states:
        n, _, b = interrupted(p, st, every=1500 if st[0] == 'tile' else 97, limit=60)
        cases += n
        bad += b[:3]
    return cases, sorted(set(st[0] for st in states)), bad


def _negative_enh(z80, colours, name, rzx, stop):
    p = negative_enhanced(Patch(z80, enhanced=colours))[name]
    try:
        c, ex, _ = verify_enhanced(p, rzx, stop=stop)
    except (AssertionError, KeyError, IndexError) as x:
        return name, ['the hook ran away: %s' % x]
    return name, sorted(k for k in c if k.endswith('!'))


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build and, with the colour table beside the snapshot, Enhanced; each with the tape's
    loading screen when it is beside the snapshot, each boot-checked. With --rzx: the default's differential replay and
    unit cases; Enhanced replayed on every recording, the handler inside each hook kind, and its broken builds (the first
    recording's first 1,500 frames; one that survives that is run over the other recordings' first 3,000). Pace, soak, flicker, beam and the real loader are the review runs' (games/mad_mix_2.md)."""
    import concurrent.futures, hashlib, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'fix_label', None):
        a.fix_label = 'NexClash build'
    say('Game      : Mad Mix 2 (Topo Soft, 1990, 128K)')
    say('Engine    : mad_mix_2; default: the original look, both port FF writes of the copy become reads, no hooks; '
        'Enhanced: stages 1 to 3 in the Spec256 set\'s colours on a double-buffered Layer 2')
    ok = True
    screen_path = _beside(z80, LOAD_SCREEN, LOAD_MD5)
    screen = screen_path.read_bytes() if screen_path else None
    colours = _beside(z80, COLOURS_FILE, COLOURS_MD5)
    colours = str(colours) if colours else None
    builds = [('Default', '_sprites', None)]
    if colours is None:
        say('Enhanced  : no %s beside the snapshot: default only' % COLOURS_FILE)
    else:
        builds.append(('Enhanced', '_enhanced', colours))
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    for label, suffix, enh in builds:
        nex = out / (name + suffix + '.nex')
        build(z80, nex, enhanced=enh)
        nexes = [nex]
        if screen is not None:
            loading = out / (name + suffix + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen))
            nexes.append(loading)
        for n in nexes:
            bad = boot_check(n, z80, Patch(z80, enhanced=enh))
            ok = ok and not bad
            say('%-10s: %s  %s' % (label, n.name, hashlib.md5(n.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)' if not bad
                                    else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    stop = getattr(a, 'quick', None)
    if not rzxs:
        say('Verify    : not requested; boot evidence only')
        say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
        return bool(ok)
    n = len(rzxs)
    with concurrent.futures.ProcessPoolExecutor(min(2 * n + 2, os.cpu_count() or 1)) as pool:
        dflt = pool.map(_verify_default, [z80] * n, rzxs, [stop] * n)
        if colours:
            enh = pool.map(_verify_enh, [z80] * n, [colours] * n, rzxs, [stop] * n)
            ints = pool.submit(_interrupts, z80, colours, rzxs[0])
        states = []
        for rname, c, fail, got in dflt:
            states += got
            ok = ok and not fail
            say('Verify    : %s %d frames, %d R comparisons, %d site passes: %s' % (
                rname, c.get('frames', 0), c.get('R comparisons', 0), c.get('site passes', 0), 'IDENTICAL' if not fail else str(fail)[:400]))
        u = unit_tests(Patch(z80), states)
        ok = ok and not [k for k in u if k.endswith('!')]
        say('Unit      : %s' % dict(u))
        if colours:
            for rname, c, fail in enh:
                ok = ok and not fail
                say('Verify    : Enhanced %s %d frames, %d hooks: %s' % (
                    rname, c.get('frames', 0), sum(v for k, v in c.items() if k.startswith('hook')),
                    'IDENTICAL' if not fail else str(fail)[:400]))
            cases, kinds, bad = ints.result()
            ok = ok and not bad and cases > 0
            say('Interrupt : %d cases of the handler inside a hook (%s): %s' % (cases, ', '.join(kinds), 'OK' if not bad else str(bad[:3])[:300]))
            if stop is None:
                names = list(negative_enhanced(Patch(z80, enhanced=colours)))
                res = dict(pool.map(_negative_enh, [z80] * len(names), [colours] * len(names), names,
                                    [rzxs[0]] * len(names), [NEG_STOP] * len(names)))
                left = [k for k, v in res.items() if not v]
                jobs = [(k, r) for k in left for r in rzxs[1:]]
                for k, v in pool.map(_negative_enh, [z80] * len(jobs), [colours] * len(jobs), [j[0] for j in jobs],
                                     [j[1] for j in jobs], [2 * NEG_STOP] * len(jobs)):
                    res[k] = res[k] or v
                missed = [k for k, v in res.items() if not v]
                ok = ok and not missed
                say('Negatives : Enhanced %d of %d broken builds caught%s' % (len(res) - len(missed), len(res),
                                                                              '; MISSED %s' % missed if missed else ''))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)


# ---------------------------------------------------------------- Enhanced: the hooks against the original, and the picture against a model
class _EView:
    """64K view of the game RAM and the Next pages a hook can map, per the model's MMU and write map."""
    def __init__(self, mem, patch, st):
        self.mem, self.patch, self.st = bytearray(mem), patch, st
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a >= 0x4000:
            return self.mem[a]
        m = self.model.nr.get(0x50 + (a >> 13), 255)
        if m == 255:
            return self.patch.page[a - 0x2000] if a >= 0x2000 else self.mem[a]
        if m == 24:
            return self.st.page[a - 0x2000]
        return self.st.pages[m][a & 8191]

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.mem[a] = v
            return
        wm = self.model.wm
        if wm & 1:
            bank = self.model.nr[0x13 if wm & 8 else 0x12] + (wm >> 6)
            self.st.pages[bank * 2 + (a >> 13)][a & 8191] = v
            self.model.c['writes through the map'] += 1
            return
        m = self.model.nr.get(0x50 + (a >> 13), 255)
        if m == 24:
            self.st.page[a - 0x2000] = v
        elif m != 255:
            self.st.pages[m][a & 8191] = v


class _EModel(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        self.wm = 0
        self.palw = []
        super().__init__(sim, speed, line=line, lines=311, t_line=228)
        self.nr.update({0x50: 255, 0x51: 255})
        self.nr[1] = 0x32

    def nextreg(self, reg, v):
        if reg == 0x44 or reg == 0x40:
            self.palw.append((reg, v))
        return super().nextreg(reg, v)

    def write_port(self, regs, port, v, *args):
        if port == 0x123B:
            self.wm = v
            return None
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        return None


class _EState:
    def __init__(self, patch):
        c = patch.colours
        self.page = bytearray(patch.ram)
        self.pages = {}
        for p in range(32, 44):
            sec = (p - 32) % 6
            self.pages[p] = bytearray(c['panel'][sec * 8192:(sec + 1) * 8192])
        for i in range(c['tile_pages']):
            self.pages[44 + i] = bytearray(c['tiles'][i * 8192:(i + 1) * 8192])
        for i, d in enumerate(c['store']):
            self.pages[44 + c['tile_pages'] + i] = bytearray(d)
        self.pages[44 + c['tile_pages'] + len(c['store'])] = bytearray(c['glyph'])
        self.nr = {0x12: 16, 0x13: 19, 0x69: 0}
        self.line = 0
        self.port = 0


def _run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0, inject=None):
    from .dizzy6 import _rw_simulator
    v = _EView(mem, patch, st)
    s = simpool.machine(_rw_simulator(), v, list(regs), 'mm2-hook')
    s.low_writes = True
    m = _EModel(s, speed, st.line)
    m.nr.update(st.nr)
    v.model = m
    R = s.registers
    n = 0
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        if inject and n in inject:
            inject[n](s, v, m)
        at = R[24]
        if v[at] == 0x76:
            R[24] = (at + 1) & 65535
            R[15] = (R[15] & 0x80) | ((R[15] + 1) & 0x7F)
        else:
            s.opcodes[v[at]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not end at %04X' % stop_pc)
    st.line = m.line()
    for k in (0x12, 0x13, 0x69):
        if k in m.nr:
            st.nr[k] = m.nr[k]
    return list(R), v, m, n


def _run_ref(mem, regs, stop_pc, stop_sp=None):
    from skoolkit.simulator import Simulator
    s = simpool.machine(Simulator, list(mem), regs, 'mm2-ref')
    R = s.registers
    n = 0
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        at = R[24]
        if s.memory[at] == 0x76:
            R[24] = (at + 1) & 65535
            R[15] = (R[15] & 0x80) | ((R[15] + 1) & 0x7F)
        else:
            s.opcodes[s.memory[at]]()
        n += 1
    return s


class EPicture:
    """What Layer 2's window should show, read afresh from the game's own state and the colour table."""
    INK, PAPER, SKIP = 253, 254, 255

    def __init__(self, colours):
        self.c = colours
        self.tp = colours['tile_pages']
        self.px = bytearray(192 * 144)
        self.front = None
        self.panels = {16: bytearray(colours['panel']), 19: bytearray(colours['panel'])}

    def char(self, ch, x, y, front):
        g = self.c['glyph']
        o = (ch - 0x20) * 64
        win = 16 <= y < 160
        if win and not 32 <= x < 224:
            return 0
        for r in range(8):
            row = g[o + r * 8:o + r * 8 + 8]
            if win:
                at = (y - 16 + r) * 192 + x - 32
                front[at:at + 8] = row
            else:
                for base in self.panels:
                    self.panels[base][(y + r) * 256 + x:(y + r) * 256 + x + 8] = row
        return 1

    def lives(self, n):
        g = self.c['glyph']
        for i in range(4):
            x = 0x68 + 32 * i
            src = 0x1000 if i < min(n, 4) else 0x1240
            for r in range(24):
                for base in self.panels:
                    self.panels[base][(0xA8 + r) * 256 + x:(0xA8 + r) * 256 + x + 24] = g[src + r * 24:src + r * 24 + 24]

    def tiles(self, mem):
        camx, camy = mem[0x8F80] | mem[0x8F81] << 8, mem[0x8F82] | mem[0x8F83] << 8
        xs = camx & 0x1C
        cell = (0xCD00 + (((camy & 0xFFF0) * 4) & 0xFFFF) + ((camx & 0x7FF) >> 5)) & 0xFFFF
        off = camy & 15
        y = 0
        while y < 144:
            n = min(16 - off, 144 - y)
            c = cell
            for t in range(7):
                idx = mem[0x5C00 + mem[c]]
                for r in range(n):
                    src = idx * 512 + (off + r) * 32
                    for i in range(32):
                        x = 32 * t - xs + i
                        if 0 <= x < 192:
                            self.px[(y + r) * 192 + x] = self.c['tiles'][src + i]
                c = (c & 0xFFC0) | ((c + 1) & 0x3F)
            y += n
            off = 0
            cell = (cell + 0x40) & 0xFFFF

    def stars(self, mem):
        m = bytearray(mem)
        for i in range(60):
            x, y = m[0x92BF + i * 2], m[0x92C0 + i * 2]
            a = (0xDB00 + y * 32 + (x >> 3)) & 0xFFFF
            d, e = m[0xB068 + (x & 7) * 2], m[0xB069 + (x & 7) * 2]
            z = m[a] & m[a + 32] & m[a + 64]
            if (z ^ 255) & d:
                continue
            m[a + 32] ^= e
            wy = y + 1
            col = (x & 0xF8)
            if wy >= 144 or not 32 <= col < 224:
                continue
            for b in range(8):
                if e & (0x80 >> b):
                    o = wy * 192 + col - 32 + b
                    v = self.px[o]
                    v = 0 if v == self.INK else v ^ 255
                    self.px[o] = self.PAPER if v >= self.INK else v
        return m

    def figure(self, mem, a, d, e):
        n = a & 0x7F
        mir = bool(a & 0x80)
        page, off, rows0 = self.c['index'][n * 4], self.c['index'][n * 4 + 1] | self.c['index'][n * 4 + 2] << 8, self.c['index'][n * 4 + 3]
        if mir:
            e = (e - 4) & 255
        rows, skip, y = rows0, 0, d
        if d == (256 - rows0) & 255:
            return
        if d > (256 - rows0) & 255:
            skip = 256 - d
            rows = rows0 - skip
            y = 0
            if rows <= 0:
                return
        if y >= 144:
            return
        rows = min(rows, 144 - y)
        left = e & 0xFC
        first, last = 0, 24
        if e & 4:
            if mir:
                first = 4
            else:
                last = 20
        data = self.c['store'][page]
        for r in range(rows):
            base = off + (skip + r) * 24
            for i in range(first, last):
                sx = left + i
                if not 32 <= sx < 224:
                    continue
                v = data[base + (23 - i if mir else i)]
                if v != self.SKIP:
                    self.px[(y + r) * 192 + sx - 32] = v


def _l2_window(st, base):
    out = bytearray(192 * 144)
    for y in range(144):
        ys = y + 16
        page = st.pages[base * 2 + (ys >> 5)]
        o = (ys & 31) * 256 + 32
        out[y * 192:y * 192 + 192] = page[o:o + 192]
    return out


def _outside(st, base):
    """Layer 2 outside the window, for the panel check."""
    out = []
    for y in range(192):
        page = st.pages[base * 2 + (y >> 5)]
        o = (y & 31) * 256
        out.append(bytes(page[o:o + 32]) + bytes(page[o + 224:o + 256]) if 16 <= y < 160 else bytes(page[o:o + 256]))
    return b''.join(out)


def _outside_model(p):
    out = []
    for y in range(192):
        o = y * 256
        out.append(bytes(p[o:o + 32]) + bytes(p[o + 224:o + 256]) if 16 <= y < 160 else bytes(p[o:o + 256]))
    return b''.join(out)


def verify_enhanced(patch, rzx_path, stop=None, collect=0):
    """Replay the original; at every changed site run the hook on a copy of the state and the original beside it: every register with R,
    all RAM but the changed bytes and the stack below SP, the clock, the MMU, the write map. At every flip the picture against the model."""
    from .rzx import read_segments, extract
    from tempfile import NamedTemporaryFile
    c, examples = Counter(), defaultdict(list)
    states = []

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    for snap, rec, _ in read_segments(rzx_path):
        break
    with NamedTemporaryFile(suffix='.z80') as t:
        extract(rzx_path, t.name)
        orig = _Machine(t.name)
    st = _EState(patch)
    pic = EPicture(patch.colours)
    panel = _l2_window.__name__ and None
    ss = patch.syms
    site_at = {a: new for a, old, new in patch.sites}
    site_old = {a: old for a, old, new in patch.sites}
    live = [dict(rb=0, ob=0)]
    from skoolkit.simutils import A, F, B, C

    def flat(m):
        o7 = m.out7ffd
        b = m.mem.banks
        return bytes(16384) + bytes(b[5]) + bytes(b[2]) + bytes(b[o7 & 7])

    def diff(mem_ref, mem_hook, sp, kind, regs_r, regs_h, skip=()):
        lo = max(0x4000, sp - 128)
        changed = [a for a in range(0x4000, 65536) if mem_ref[a] != mem_hook[a]] if bytes(mem_ref[0x4000:]) != bytes(mem_hook[0x4000:]) else []
        cov = {0xA718, 0xA719}              # where the game keeps SP during a pop-driven loop: written before it is read, and the hook's stack is deeper
        for a, new in site_at.items():
            cov |= set(range(a, a + len(new)))
        changed = [a for a in changed if not (lo <= a < sp) and a not in cov]
        if changed:
            fail('RAM differs', {'kind': kind, 'at': hex(changed[0]), 'n': len(changed)})
        for i in CMP:
            if i in skip:
                continue
            if regs_r[i] != regs_h[i]:
                fail('registers differ', {'kind': kind, 'reg': i, 'orig': regs_r[i], 'hook': regs_h[i]})
        c['R comparisons'] += 1

    def guards(kind, m):
        if m.nr.get(7, 0) != 0:
            fail('clock differs', {'kind': kind})
        if m.nr.get(0x50, 255) != 255 or m.nr.get(0x51, 255) != 255:
            fail('MMU not restored', {'kind': kind, 's0': m.nr.get(0x50), 's1': m.nr.get(0x51)})
        if m.wm & 1:
            fail('write map left on', {'kind': kind})

    def patched(mem):
        p = bytearray(mem)
        for a, new in site_at.items():
            if bytes(p[a:a + len(site_old[a])]) == site_old[a]:
                p[a:a + len(new)] = new
        return p

    def main_hook(kind):
        def f(m):
            mem = flat(m)
            regs = list(m.sim.registers)
            if collect and sum(1 for x in states if x[0] == kind) < collect:
                states.append((kind, regs, mem))
            sp = regs[12]
            ret = mem[sp] | mem[sp + 1] << 8
            on = st.page[ss['V_ON'] - 0x2000]
            at = regs[24]
            c['hooks ' + kind] += 1
            if kind == 'star':
                m2 = bytes(pic.stars(mem)) if on else None
            ref = _run_ref(mem, regs, ret, (sp + 2) & 65535)
            if kind == 'fig' and on and regs[0] != 0xFF:
                pic.figure(mem, regs[0], regs[2 + 2], regs[2 + 3])
            if kind == 'tile':
                on2 = ref.memory[G_STAGE] < 3
                if on2:
                    pic.tiles(ref.memory)
            r, v, md, n = _run_hook(patch, st, patched(mem), regs, ret, (sp + 2) & 65535)
            diff(ref.memory, v.mem, sp, kind, ref.registers, r)
            guards(kind, md)
            if (kind == 'tile' and ref.memory[G_STAGE] < 3) or (kind != 'tile' and on):
                got = _l2_window(st, st.nr[0x13])
                if got != pic.px:
                    d = [i for i in range(len(got)) if got[i] != pic.px[i]]
                    fail('picture differs from the model', {'after': kind, 'a': regs[0], 'd': regs[4], 'e': regs[5], 'n': len(d), 'first': (d[0] % 192, d[0] // 192), 'got': got[d[0]], 'want': pic.px[d[0]], 'frame': c['frames']})
                    pic.px[:] = got
        return f
    G_STAGE = 0x8E76

    def panel_check(kind):
        for bk in (16, 19):
            if _outside(st, bk) != _outside_model(pic.panels[bk]):
                fail('the panel differs from the model', {'kind': kind, 'buffer': bk})
                pic.panels[bk][:] = _full(st, bk)

    def _full(st_, base):
        return b''.join(bytes(st_.pages[base * 2 + i]) for i in range(6))

    def flip(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        sp = regs[12]
        ref = _run_ref(mem, regs, 0xABCC, sp)
        drawn = st.page[ss['V_DRAWN'] - 0x2000]
        back = st.nr[0x13]
        r, v, md, n = _run_hook(patch, st, patched(mem), regs, 0xABCC, sp)
        diff(ref.memory, v.mem, sp, 'flip', ref.registers, r)
        guards('flip', md)
        c['hooks flip'] += 1
        if drawn:
            c['pictures'] += 1
            if st.nr[0x12] != back:
                fail('picture not published', {})
            if st.nr[0x69] != 0x80:
                fail('Layer 2 not shown after a picture', {})
            got = _l2_window(st, back)
            c['pixels compared'] += len(got)
            if got != pic.px:
                d = [i for i in range(len(got)) if got[i] != pic.px[i]]
                fail('picture differs from the model', {'n': len(d), 'first': (d[0] % 192, d[0] // 192), 'got': got[d[0]], 'want': pic.px[d[0]], 'frame': c['frames']})
                pic.px[:] = got
            panel_check('flip')
            # the set's plain pixel must agree with the game's own bit
            bad = 0
            for y in range(0, 144, 3):
                for x in range(0, 192, 3):
                    v_ = got[y * 192 + x]
                    if v_ in (253, 254):
                        bit = (mem[0xDB04 + y * 32 + (x >> 3)] >> (7 - (x & 7))) & 1
                        if bit != (v_ == 253):
                            bad += 1
            c['plain pixels against the bitmap, wrong'] += bad
            if bad > 200:
                fail('plain pixels disagree with the bitmap', {'n': bad})
            pic.front = bytes(got)

    def hide(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        ref = _run_ref(mem, regs, 0xA89F)
        r, v, md, n = _run_hook(patch, st, patched(mem), regs, 0xA89F)
        diff(ref.memory, v.mem, regs[12], 'hide', ref.registers, r)
        guards('hide', md)
        c['hooks hide'] += 1
        if st.nr[0x69] != 0:
            fail('Layer 2 left showing over a cleared screen', {})

    def text(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        sp = regs[12]
        ret = mem[sp] | mem[sp + 1] << 8
        ref = _run_ref(mem, regs, ret, (sp + 2) & 65535)
        show = st.nr[0x69]
        de0 = regs[2 + 2] << 8 | regs[2 + 3]
        r, v, md, n = _run_hook(patch, st, patched(mem), regs, ret, (sp + 2) & 65535)
        diff(ref.memory, v.mem, sp, 'text', ref.registers, r)
        guards('text', md)
        c['hooks text'] += 1
        if show and pic.front is not None:
            de1 = ref.registers[2 + 2] << 8 | ref.registers[2 + 3]
            count = de1 - de0 - 1
            want = bytearray(pic.front)
            x0, y0 = regs[3], regs[2]
            for k in range(count):
                ch = mem[de0 + 1 + k] & 0x7F
                if 0x20 <= ch < 0x60:
                    c['text cells painted'] += pic.char(ch, x0 + k * 8, y0, want)
            got = _l2_window(st, st.nr[0x12])
            if got != want:
                fail('the text differs from the model', {'x': x0, 'y': y0, 'n': count})
            pic.front = bytes(want)
            panel_check('text')

    def lives(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        ref = _run_ref(mem, regs, 0x915A)
        show = st.nr[0x69]
        r, v, md, n = _run_hook(patch, st, patched(mem), regs, 0x915A)
        diff(ref.memory, v.mem, regs[12], 'lives', ref.registers, r)
        guards('lives', md)
        c['hooks lives'] += 1
        if show:
            pic.lives(mem[0x8E64])
            panel_check('lives')

    def isr_in(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        ref = _run_ref(mem, regs, 0xA54B)
        r, v, md, n = _run_hook(patch, st, patched(mem), regs, 0xA54B)
        diff(ref.memory, v.mem, regs[12] - 4, 'isr in', ref.registers, r, skip=(A, F, B, C, 15))
        if md.nr.get(7, 0) != 0:
            fail('clock differs', {'kind': 'isr in'})
        if md.wm & 1:
            fail('write map left on', {'kind': 'isr in'})
        live[0] = dict(rb=r[15], ob=ref.registers[15])
        c['hooks isr'] += 1

    def isr_out(m):
        mem = flat(m)
        regs = list(m.sim.registers)
        sp = regs[12]
        ret = mem[sp] | mem[sp + 1] << 8
        ref = _run_ref(mem, regs, ret, (sp + 2) & 65535)
        h = list(regs)
        h[15] = (live[0]['rb'] & 0x80) | ((live[0]['rb'] + (regs[15] - live[0]['ob'])) & 0x7F)
        r, v, md, n = _run_hook(patch, st, patched(mem), h, ret, (sp + 2) & 65535)
        diff(ref.memory, v.mem, sp, 'isr out', ref.registers, r)
        guards('isr out', md)
    watch = {0xAC46: main_hook('tile'), 0xB02A: main_hook('star'), 0xA58B: main_hook('fig'), 0xABC8: flip, 0xA89A: hide,
             0xA8F9: text, 0x9157: lives, 0xA548: isr_in, 0xA584: isr_out}
    for n, frame in enumerate(rec.frames):
        if stop is not None and n >= stop:
            break
        orig.frame(rec.data[frame.start:frame.end], watch)
        c['frames'] += 1
    return c, examples, states


def negative_enhanced(patch):
    """Broken builds, each of which the replay must catch."""
    import copy
    out = {}

    def mutate(name, old, new):
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        code = bytes(b.ram[0x800:0x800 + len(patch.code)])
        i = code.find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b.code = bytes(b.ram[0x800:0x800 + len(patch.code)])
        b._banks()
        out[name] = b
    s = patch.syms
    mutate('R off by one on the tiles', bytes((0x3E, 0x100 - 19, 0xCD)), bytes((0x3E, 0x100 - 18)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('tile page wrong', bytes.fromhex('E60FC62C'), bytes.fromhex('E60FC62D'))
    mutate('tile rows from the wrong place', bytes.fromhex('79E60F87'), bytes.fromhex('79E60E87'))
    mutate('map column never wraps', bytes.fromhex('2F E63F'.replace(' ', '')), bytes.fromhex('2F E600'.replace(' ', '')))
    mutate('figure not mirrored', bytes.fromhex('EDBC'), bytes.fromhex('EDB4'))
    mutate('figure transparency lost', bytes.fromhex('3EFFEDB4'), bytes.fromhex('3EFEEDB4'))
    mutate('stars not found', bytes.fromhex('3E3C32'), bytes.fromhex('3E0132'))
    mutate('no flip', bytes.fromhex('ED9212'), bytes.fromhex('ED9213'))
    mutate('Layer 2 left showing', bytes.fromhex('ED9169'), bytes.fromhex('ED9109'))
    mutate('write map left on', bytes.fromhex('013B123A343EED79'), bytes.fromhex('013B123A333EED79'))
    mutate('slot 0 left mapped', bytes.fromhex('3EFF32323EED9150FFC9'), bytes.fromhex('3EFF32323EED9151FFC9'))
    mutate('text not painted', bytes.fromhex('E6C0B0CD'), bytes.fromhex('E6C000CD'))
    b = copy.copy(patch)
    b.sites = [(a, old, new) for a, old, new in patch.sites if a != 0xA89A]
    out['the picture stays over a cleared screen'] = b
    return out


def interrupted(patch, kind_state, every=4001, limit=40):
    """The handler at many points of a hook: it runs at the game's clock, the write map off; after it slot 0, slot 1 and the map are back, so the
    picture and the game's RAM end as without it. The handler's body is reduced to its pushes and pops and a port 0x7FFD write's MMU reset."""
    kind, regs, mem = kind_state
    sp = regs[12]
    ret = mem[sp] | mem[sp + 1] << 8
    bad, cases = [], 0
    st0 = _EState(patch)
    st0.page[patch.syms['V_ON'] - 0x2000] = 0xFF
    st0.page[patch.syms['V_SHOW'] - 0x2000] = 1
    st0.nr[0x69] = 0x80
    base = bytearray(mem)
    for a, old, new in patch.sites:
        if bytes(base[a:a + len(old)]) == old:
            base[a:a + len(new)] = new
    # the handler: its pushes, then straight to its pops
    base[0xA557:0xA557 + 3] = bytes((0xC3, 0x76, 0xA5))
    import copy
    st = copy.deepcopy(st0)
    r0, v0, m0, n0 = _run_hook(patch, st, base, regs, ret, (sp + 2) & 65535)
    want = {k: bytes(p) for k, p in st.pages.items() if k < 44}
    for at in range(50, min(n0, every * limit), every):
        cases += 1
        st2 = copy.deepcopy(st0)
        seen = []

        def fire(s, v, m, at=at):
            R = s.registers
            pc = R[24]
            if not R[26]:               # interrupts off: no handler here
                return
            R[12] = (R[12] - 2) & 65535
            v[R[12]] = pc & 255
            v[(R[12] + 1) & 65535] = pc >> 8
            R[24] = 0xA548
            seen.append((pc, m.wm & 1, m.nr.get(0x50), m.nr.get(0x51)))
            # run to the handler's end, then the MMU reset of its 0x7FFD write has happened
            n = 0
            while R[24] != 0xA584:
                s.opcodes[v[R[24]]]()
                n += 1
                if n > 20000:
                    raise AssertionError('handler stuck')
            if m.wm & 1:
                bad.append(('map on in the handler', hex(pc)))
            if m.nr.get(7) != 0:
                bad.append(('handler not at the game clock', hex(pc)))
            m.nr[0x50] = 255
            m.nr[0x51] = 255
            sp_h = (R[12] + 2) & 65535
            n = 0
            while not (R[24] == pc and R[12] == sp_h):
                s.opcodes[v[R[24]]]()
                n += 1
                if n > 20000:
                    raise AssertionError('handler exit stuck')
            if m.nr.get(0x51) != 24 and 0x2000 <= pc < 0x4000:
                bad.append(('slot 1 not back', hex(pc)))
        r1, v1, m1, n1 = _run_hook(patch, st2, base, regs, ret, (sp + 2) & 65535, inject={at: fire})
        got = {k: bytes(p) for k, p in st2.pages.items() if k < 44}
        if got != want:
            bad.append(('picture differs', at, hex(seen[0][0]) if seen else None))
        d = [a for a in range(0x4000, 65536) if not (sp - 128 <= a < sp) and v1.mem[a] != v0.mem[a]]
        if d:
            bad.append(('RAM differs', at, hex(d[0])))
        if m1.wm & 1 or m1.nr.get(0x50, 255) != 255:
            bad.append(('left mapped', at))
        cases -= not seen
    return cases, n0, bad
