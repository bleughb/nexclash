"""Elite standard versions verifier (engine elite_std; games/elite_std.md "## Verify"): lockstep differential test from
scripted states. No RZX of the standard game exists, so the states come from free runs of the version's start state with
key schedules (title, docked pages, launch, flight with turning and speed, charts, hyperspace, the sun) and, for combat,
encounters injected with the game's own dispatcher (VERSIONS[v]['dispatch'], A = event, called from the main-loop top:
the ships are spawned by the game's code, as a random encounter would; scenarios()).

Per case two 48K machines run the same frames with the same keys: the ORIGINAL (Sinclair's ROM, the state as it is, IM 2
vector read with bus byte 0xFF as on a Spectrum) and the BUILD (the alt ROM image of the built patch below 0x4000, the
sites applied, I = 0x39 where the fix applies, and the IM 2 vector read with a different bus byte at every interrupt,
BUSES: 0xFF, 0x00 and others - CSpect's is not 0xFF). Frames are timed by the original's T. Every instruction of the
original is executed by the build too and the PCs must match after each one; the build's only extra instruction is the
alt ROM's JP 0xFEFE at 0x3A3A after an interrupt (R is put back after it: the build's R runs one ahead per interrupt
on the Next; the standard code has no LD A,R outside the Lenslok code - games/elite_std.md). At every pass (the
original at VERSIONS[v]['clear']) and at the end: registers (CMP: all but I, T, MEMPTR), RAM 0x4000-0xFFFF (the sites'
bytes excepted) and the port writes since the last pass must be equal. Failure keys end in '!'.
Negative controls: the same case with the build's negative_variants (a table byte, a site left at 0xFD) must fail.

Title hooks (M5, games/elite_std.md "## Smooth title ship"): the build's four title CALLs run, in the lockstep, as the
instructions they replaced ('title hook'): the game's own title passes must equal the original's at every pass (as
every other case). What the hooks add between passes (renders at 28 MHz) is checked by title_render_check on the
title case: each render done on a copy of the original, then put back by the asm's ranges, must leave RAM as the
pass left it ('render ok'; 'render differs!' fails).
"""
import collections
import os
import tempfile

from . import elite_std as E

BUSES = (0xFF, 0x00, 0x07, 0x38, 0xFE, 0x06, 0x7F, 0x01, 0xC7)    # 0x06 / 0x07 meet the negative table byte
FT = 69888                      # 48K frame, T
JP_PC = 0x3A3A                  # asm h_isr: JP 0xFEFE
FIGHT = '0-300:A;30-80:S;100-130:M;150-200:X;220-240:N'
_REG = ['A', 'F', 'B', 'C', 'D', 'E', 'H', 'L', 'IXh', 'IXl', 'IYh', 'IYl', 'SP', 'SP2', 'I', 'R',
        "A'", "F'", "B'", "C'", "D'", "E'", "H'", "L'", 'PC', 'T', 'IFF', 'IM', 'HALT']


def _launch_frame(version):
    return max(int(p.split(':')[0].split('-')[0]) for p in E.VERSIONS[version]['keys'].split(';'))


def scenarios(version, quick=False):
    """[(name, base, frames, keys, inject, run, run_keys)]: the case's state = the start state free-run `frames`
    frames with `keys` (base 'start'), or a named earlier case's state run on; inject = an event (A) for the dispatcher
    at the main-loop top, or None; then `run` frames are verified with `run_keys`."""
    v = E.VERSIONS[version]
    tl = _launch_frame(version)
    first = min(int(p.split(':')[0].split('-')[0]) for p in v['keys'].split(';'))
    base = v['keys']
    out = [
        ('title', 'start', first - 60, base, None, 120, ''),
        ('docked_pages', 'start', tl - 150, base, None, 300, '10-15:K;70-75:I;130-135:O;190-195:P;250-255:ENTER'),
        ('launch', 'start', tl + 20, base, None, 200, ''),
        ('flight', 'start', tl + 450, base, None, 200, '0-40:M;50-90:S;100-130:SPACE;140-160:SYM;170-190:X'),
        ('charts', 'flight', 0, '', None, 160, '0-5:I;50-55:O;100-105:1'),
        ('hyperspace', 'flight', 0, '', None, 500, '0-5:O;15-30:S;50-55:1;80-85:H'),
        ('sun', 'flight', 800, '0-5:O;15-30:S;50-55:1;80-85:H', None, 160, '0-3:2;80-83:1'),
    ]
    k = [p for p in v['keys'].split(';')]
    if len(k) > 2 and k[0].endswith(':N'):          # "Load New Commander (Y/N)?" then N: "Press Space, Commander"
        n_end = int(k[0].split(':')[0].split('-')[1])
        out.insert(1, ('title_space', 'start', n_end + 60, base, None, 120, ''))
    events = (1, 5) if quick else (1, 2, 5, 6, 7, 8, 9)
    for e in events:
        out.append(('combat_e%d' % e, 'flight', 0, '', e, 300, FIGHT))
    if not quick:
        out.append(('combat_missile', 'flight', 0, '', 1, 800, '0-5:T;20-700:A;30-80:S;100-130:M;150-155:F;250-255:F;'
                                                               '300-330:X;400-405:T;420-425:F'))
        out.append(('combat_long', 'flight', 0, '', 1, 1200, '0-1200:A;30-80:S;100-130:M;150-200:X;400-430:S;600-640:M;'
                                                             '800-830:X;900-1000:SPACE'))
    if quick:
        out = [c for c in out if c[0] in ('title', 'title_space', 'launch', 'flight', 'hyperspace', 'combat_e1', 'combat_e5')]
    return out


# ------------------------------------------------------------------------------------------------ states

def _save(sim, path):
    from skoolkit.simutils import get_state
    from skoolkit.snapshot import write_snapshot
    ram, regs, state, machine = get_state(sim)
    write_snapshot(path, ram, regs, state, machine)
    return path


def make_states(z80, version, folder, quick=False, progress=None):
    """Free-run the scripted states (scenarios) into folder; -> {name: (z80 path, run, run_keys)}."""
    from . import simrun
    os.makedirs(folder, exist_ok=True)
    paths = {'start': str(z80)}
    out = {}
    for name, base, frames, keys, inject, run, run_keys in scenarios(version, quick):
        src = paths[base]
        f, sim = simrun.free_run(src, frames, None, keys=keys) if frames else (0, None)
        path = os.path.join(folder, '%s_%s.z80' % (version, name))
        if sim is not None:
            _save(sim, path)
        else:
            import shutil
            shutil.copy(src, path)
        if inject is not None:
            path = _inject(path, version, inject, path)
        paths[name] = path
        out[name] = (path, run, run_keys)
        if progress:
            progress('state %s' % name)
    return out


def _inject(src, version, event, out):
    """Run src to the main-loop top, push it as the return address and enter the dispatcher with A = event."""
    from . import simrun
    v = E.VERSIONS[version]
    f, sim = simrun.free_run(src, 100, None, stop_pc=v['loop'])
    R, m = sim.registers, sim.memory
    if R[24] != v['loop']:
        raise ValueError('main-loop top 0x%04X not reached for the injection' % v['loop'])
    sp = (R[12] - 2) & 0xFFFF
    m[sp], m[(sp + 1) & 0xFFFF] = v['loop'] & 255, v['loop'] >> 8
    R[12], R[24], R[0] = sp, v['dispatch'], event
    return _save(sim, out)


# ------------------------------------------------------------------------------------------------ lockstep

class _Tr:
    def __init__(self):
        self.held, self.out = set(), []
        self.border = self.outfe = 0

    def read_port(self, regs, port):
        from .simrun import ROWS, KEMPSTON
        if port & 0xFF == 0x1F:
            return sum(v for k, v in KEMPSTON.items() if k in self.held)
        v = 0xFF
        if port & 1 == 0:
            for row, ks in ROWS.items():
                if (port >> 8) & (row ^ 0xFF) == 0:
                    for i, k in enumerate(ks):
                        if k in self.held:
                            v &= ~(1 << i)
        return v

    def write_port(self, regs, port, value, offset=0):
        self.out.append((port, value))


def _accept(sim, bus, prev):
    R, m = sim.registers, sim.memory
    if not R[26] or m[prev] == 0xFB:
        return False
    if m[R[24]] == 0x76:
        R[24] = (R[24] + 1) & 0xFFFF
    if R[27] == 2:
        va = bus + 256 * R[14]
        target = m[va] | m[(va + 1) & 0xFFFF] << 8
        R[25] += 19
    else:
        target = 0x38
        R[25] += 13
    sp = (R[12] - 2) & 0xFFFF
    m[sp], m[(sp + 1) & 0xFFFF] = R[24] & 255, R[24] >> 8
    R[12] = sp
    R[15] = (R[15] & 0x80) | ((R[15] + 1) & 0x7F)
    R[24], R[26] = target, 0
    return True


def machines(z80, patch, variant=None):
    """(original, build) simulators for a state: the build has the alt ROM image, the sites and its I. variant: a
    negative build as (name, banks, extra) from E.negative_variants applied over the build's RAM / alt ROM."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    s = Snapshot.get(str(z80))
    o = from_snapshot(Simulator, s)
    p = from_snapshot(Simulator, s)
    b12 = patch.extra_banks[12]
    img = bytearray(b12[8192:16384] + b12[0:8192])
    ram = bytearray(p.memory[0x4000:0x10000])
    regs = {'I': p.registers[14], 'IM': p.registers[27]}
    applied = patch.patch_ram(ram, regs, check=False)
    excl = set()
    if variant is not None:
        name, banks, extra = variant
        img = bytearray(extra[12][8192:16384] + extra[12][0:8192])
        if name == 'site':
            a = patch.sites[-1][0]
            ram[a - 0x4000 + 1] = E.GAME_I
            if regs['I'] == E.IM2_I:
                regs['I'] = E.GAME_I
        elif name == 'table' and not patch.sites:
            ram[E.GAME_I * 256 - 0x4000 + 7] ^= 1
            excl.add(E.GAME_I * 256 + 7)        # caught by the vector, not by the RAM compare
    p.memory[0:0x4000] = img
    p.memory[0x4000:0x10000] = ram
    p.registers[14] = regs['I']
    o.set_tracer(_Tr())
    p.set_tracer(_Tr())
    p.applied, p.excl = applied, excl
    return o, p


def run_case(z80, patch, frames, keys, version, variant=None, keep=5):
    """Lockstep `frames` frames of state z80 (module docstring). -> (Counter, examples, coverage)."""
    from .simrun import parse_keys, held_at
    v = E.VERSIONS[version]
    o, p = machines(z80, patch, variant)
    sched = parse_keys(keys)
    ro, rp, mo, mp = o.registers, p.registers, o.memory, p.memory
    opo, opp = o.opcodes, p.opcodes
    to, tp = o.tracer, p.tracer
    c, ex = collections.Counter(), []
    sites = {a + i for a, old, new in p.applied for i in range(len(new))} | p.excl
    tsites = {a: (a, old, new) for a, old, new in p.applied if (a, old, new) in patch.tsites}
    cmp_regs = [i for i in E.CMP if i < len(_REG) and _REG[i] not in ('T', 'SP2')]
    nint = [0]
    seen = set()

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex) < keep:
            ex.append((key, detail))

    def compare(where):
        bad_r = [(_REG[i], ro[i], rp[i]) for i in cmp_regs if ro[i] != rp[i]]
        bad_m = [a for a in range(0x4000, 0x10000) if mo[a] != mp[a] and a not in sites]
        bad_o = to.out != tp.out
        if bad_r or bad_m or bad_o:
            fail('state', (where, bad_r[:4], ['0x%04X' % a for a in bad_m[:6]], len(bad_m), bad_o))
            return False
        c['pass ok'] += 1
        to.out, tp.out = [], []
        return True
    clear = v['clear']
    prev = ro[24]
    for f in range(frames):
        to.held = tp.held = held_at(sched, f)
        while ro[25] < FT:
            prev = ro[24]
            if prev == clear and not compare('pass at frame %d' % f):
                return c, ex, seen
            opo[mo[prev]]()
            ts = tsites.get(rp[24])
            if ts:                      # a title hook: run as the instruction it replaced (module docstring)
                a, old, new = ts
                mp[a:a + len(old)] = old
                opp[mp[a]]()
                mp[a:a + len(new)] = new
                c['title hook'] += 1
            else:
                opp[mp[rp[24]]]()
            if rp[24] != ro[24]:
                fail('pc', (f, '0x%04X' % prev, '0x%04X' % ro[24], '0x%04X' % rp[24]))
                return c, ex, seen
            if len(seen) < 200000:
                seen.add(prev)
        ro[25] -= FT
        rp[25] = ro[25]
        bus = BUSES[nint[0] % len(BUSES)]
        a1 = _accept(o, 0xFF, prev)
        a2 = _accept(p, bus, prev)
        if a1 != a2:
            fail('interrupt', (f, a1, a2))
            return c, ex, seen
        if a1:
            nint[0] += 1
            if rp[24] == JP_PC:
                opp[mp[JP_PC]]()
                rp[15] = (rp[15] & 0x80) | ((rp[15] - 1) & 0x7F)
            rp[25] = ro[25]             # the JP's 10 T are not modelled: frame time is the original's (HALT reads T)
            if rp[24] != ro[24]:
                fail('im2 vector', (f, 'bus 0x%02X' % bus, '0x%04X' % ro[24], '0x%04X' % rp[24]))
                return c, ex, seen
    compare('end')
    c['frames'] += frames
    c['interrupts'] += nint[0]
    return c, ex, seen


def verify(patch, z80, progress=None, quick=False, folder=None, cases=None):
    """Every scripted case (scenarios), lockstep; then the negative controls on the first case with interrupts on.
    -> (Counter, examples, [state paths])."""
    version = patch.version
    folder = folder or tempfile.mkdtemp(prefix='elite_std_')
    states = make_states(z80, version, folder, quick, progress)
    total, examples = collections.Counter(), []
    cov = set()
    for name, (path, run, keys) in states.items():
        if cases and name not in cases:
            continue
        c, ex, seen = run_case(path, patch, run, keys, version)
        cov |= seen
        bad = sum(v for k, v in c.items() if k.endswith('!'))
        total['case ok' if not bad else 'case failed!'] += 1
        for k, v in c.items():
            total[k] += v
        examples += [(name,) + e for e in ex]
        if progress:
            progress('%s: %s' % (name, dict(c)))
    for tname in ('title', 'title_space'):
        if not patch.v.get('ttl') or tname not in states or (cases and tname not in cases):
            continue
        rc = title_render_check(patch, states[tname][0], states[tname][1])
        if not rc['passes']:
            rc['render: no title pass!'] += 1
        for k, v in rc.items():
            if k.startswith(('render', 'w0', 'passes', 'jump')):
                total['title ' + k if not k.startswith('render') else k] += v
        if progress:
            progress('%s renders: %s' % (tname, dict(rc)))
    neg_case = states['flight'][0]
    for name, nb, ne in E.negative_variants(_banks_of(patch, neg_case), version):
        c, ex, _ = run_case(neg_case, patch, 60, '', version, variant=(name, nb, ne))
        caught = any(k.endswith('!') for k in c)
        total['neg %s caught' % name if caught else 'neg %s missed!' % name] += 1
        if progress:
            progress('negative %s: %s' % (name, dict(c)))
    total['pcs executed'] = len(cov)
    return total, examples, [s[0] for s in states.values()]


def _banks_of(patch, z80):
    """{5, 2, 0: the state's RAM with the sites, 12: the alt ROM bank} for negative_variants."""
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(str(z80))
    ram = bytearray(s.ram(-1))
    patch.patch_ram(ram, None, check=False)
    return {5: bytes(ram[0:16384]), 2: bytes(ram[16384:32768]), 0: bytes(ram[32768:49152]),
            12: patch.extra_banks[12]}


# ------------------------------------------------------------------------------------------------ title renders

SENTINEL = 0x3FFE               # a return address in the ROM: never reached by the game's code


def _dec(b, kind):
    """A slot value (asm dec_v): kind 1 = lo, hi, sign | bits 16-22; kind 0 = fraction, sign | magnitude."""
    if kind:
        v = b[0] | b[1] << 8 | (b[2] & 0x7F) << 16
        return -v if b[2] & 0x80 else v
    v = b[0] | (b[1] & 0x7F) << 8
    return -v if b[1] & 0x80 else v


def _enc(v, kind):
    s, m = (0x80, -v) if v < 0 else (0, v)
    if kind:
        return [m & 255, (m >> 8) & 255, s | ((m >> 16) & 0x7F)]
    return [m & 255, s | ((m >> 8) & 0x7F)]


def extrapolate(prev, cur, w):
    """The asm's extrap on 27 slot bytes: cur + (cur - prev) * w / 256 per value (|delta| * w truncated, as the
    asm's MULs), or None on a jump (|delta| >= 0x2000)."""
    out, i = [], 0
    for k in range(12):
        kind = 1 if k < 3 else 0
        n = 3 if kind else 2
        p, c = _dec(prev[i:i + n], kind), _dec(cur[i:i + n], kind)
        d = c - p
        if abs(d) >= 0x2000:
            return None
        m = ((abs(d) & 255) * w >> 8) + (abs(d) >> 8) * w
        out += _enc(c + (m if d >= 0 else -m), kind)
        i += n
    return out


def _call(mem, regs, addr, limit=4000000):
    """Run the game's routine addr on a copy of the machine (no interrupts) until it returns. -> (memory, lowest SP
    within 256 below the start: the routine's own stack, which the asm's renders keep in STATE_PG instead)."""
    from skoolkit.simulator import Simulator
    m = list(mem)
    sp = (regs['SP'] - 2) & 0xFFFF
    m[sp], m[sp + 1] = SENTINEL & 255, SENTINEL >> 8
    r = dict(regs, SP=sp, PC=addr)
    sim = Simulator(m, r)
    ops, R = sim.opcodes, sim.registers
    n, low = 0, sp
    while R[24] != SENTINEL:
        ops[m[R[24]]]()
        if sp - 256 <= R[12] < low:
            low = R[12]
        n += 1
        if n > limit:
            raise RuntimeError('routine 0x%04X did not return' % addr)
    return m, low


def title_render_check(patch, z80, frames, keys='', weights=(0, 64, 128, 192, 255)):
    """The renders' effect on the game, checked on the ORIGINAL title (games/elite_std.md "## Smooth title ship"):
    at each pass's h_pre point (after the copy) the asm's render is done on a copy - buffer = the background kept at
    h_bg, slot = extrapolate(last pass, this pass, w), the game's draw (IX = slot, IY = blueprint) and copy - and then
    its put-back (prm ranges from the pass's memory, the buffer); RAM 0x4000-0xFFFF must then equal the pass's
    except the screen 0x4000-0x4FFF (the render's picture: the point) and the routines' own stack below SP.
    -> Counter: 'render ok' per (pass, weight), 'render differs!' (a byte the ranges miss), 'w0 same' / 'w0 px' (the
    w = 0 render vs the game's own picture: equal but for the draw's slot tidy, counted in changed screen bytes),
    'moved px' (screen bytes changed by the w = 255 render vs w = 0)."""
    from .simrun import parse_keys, held_at
    t = patch.v.get('ttl')
    c = collections.Counter()
    if not t:
        return c
    a_bg = {a for a, _, sym in t['sites'] if sym == 'h_bg'}
    a_pre = {a for a, _, sym in t['sites'] if sym.startswith('h_pre')}
    rng = [(a, n) for a, n in t['rng']]
    o, _ = machines(z80, patch)
    R, m = o.registers, o.memory
    sched = parse_keys(keys)
    prev, bg = None, None
    pc = R[24]
    for f in range(frames):
        o.tracer.held = held_at(sched, f)
        while R[25] < FT:
            pc = R[24]
            if pc in a_bg:
                bg = list(m[0xC000:0xD000])
            elif pc in a_pre and bg is not None:
                cur = list(m[0x6159:0x6159 + 27]) + list(m[0x617C:0x617E])
                regs = {'SP': R[12], 'IX': 0x6159, 'IY': m[0x617C] | m[0x617D] << 8}
                base = list(m)
                shots = {}
                for w in weights:
                    sl = cur[:27] if w == 0 or prev is None or prev[27:] != cur[27:] else extrapolate(prev, cur, w)
                    if sl is None:
                        c['jump'] += 1
                        continue
                    mm = list(base)
                    mm[0xC000:0xD000] = bg
                    mm[0x6159:0x6159 + 27] = sl
                    mm, l1 = _call(mm, regs, t['draw'])
                    mm, l2 = _call(mm, regs, t['copy'])
                    shots[w] = mm[0x4000:0x5000]
                    for a, n in rng:
                        mm[a:a + n] = base[a:a + n]
                    mm[0xC000:0xD000] = base[0xC000:0xD000]
                    sp = R[12]
                    bad = [a for a in range(0x5000, 0x10000) if mm[a] != base[a] and not min(l1, l2) <= a < sp]
                    if bad:
                        c['render differs!'] += 1
                        c['first 0x%04X' % bad[0]] += 1
                    else:
                        c['render ok'] += 1
                if 0 in shots:
                    d = sum(1 for x, y in zip(shots[0], base[0x4000:0x5000]) if x != y)
                    c['w0 same' if not d else 'w0 px'] += 1 if not d else d
                if 0 in shots and max(weights) in shots:
                    c['moved px'] += sum(1 for x, y in zip(shots[0], shots[max(weights)]) if x != y)
                prev = cur
                c['passes'] += 1
            o.opcodes[m[pc]]()
        R[25] -= FT
        _accept(o, 0xFF, pc)
    return c
