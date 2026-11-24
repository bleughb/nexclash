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

SD save / load (games/elite_std.md "## SD save"): the three sites (the ACCESS MENU's load and save CALLs, the key
wait before a save) run in the lockstep as the instructions they replaced ('sd hook'), like the title hooks; the
hooks themselves are checked by sd_check on the built .nex (a Next memory model with a fake esxDOS).
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


# Gap cases (games/elite_std.md "## Verify", coverage): from the flight state, RAM pokes (commander equipment at layout A
# 0xD082-0xD08D / B 0xA844-0xA84F, and the like), an optional dispatcher event, keys, frames. Each proven by a free run
# hitting the named routine (C:/1NEXT/elite_work/std/gaps/A|B/recipes.json, final.py); verify() fails a case whose
# lockstep never executes that routine (proof). -> (name, pokes, event, keys, run, proof)
GAPS = {
    'A': (
        ('gap_docking_computer', {0xD08C: 0xFF}, None, '10-30:C', 300, 0x71AE),          # engage 0x71AE, docked status page
        ('gap_escape_pod', {0xD089: 0xFF}, None, '10-30:Q', 400, 0x9C39),                # launch 0x9C39
        ('gap_energy_bomb', {0xD08A: 0xFF}, 1, '60-70:W', 200, 0x9D72),                  # 0x7095, ships killed 0x9D72
        ('gap_galactic_hyperdrive', {0xD08D: 0xFF}, None, '10-30:G+H', 500, 0xDC4E),     # 0xDBC5, galaxy change 0xDC4E
        ('gap_in_system_jump', {}, None, '0-5:O;15-30:S;50-55:1;80-85:H;300-310:J', 600, 0x7EFF),   # jump 0x7EFF
        ('gap_game_over', {0x7107: 0, 0x7108: 0, 0x7109: 0, 0x710A: 0, 0x710B: 0, 0x710C: 0, 0x710D: 0, 0x710E: 16,
                           0x710F: 0}, None, '', 330, 0x7552),                           # planet on us: 0x7519, Game Over 0x7552
        ('gap_explosion', {}, 9, FIGHT, 50, 0xA8AC),                                     # kill 0xB703, explosion 0xA8AC
        ('gap_missile_hit', {}, 9, '0-3:T;20-25:F', 150, 0xA527),                        # hit 0xA527
    ),
    'B': (
        ('gap_docking_computer', {0xA84E: 1}, None, '0-20:C', 300, 0xD16F),              # 0x70F6, status page 0xD16F
        ('gap_escape_pod', {0xA84B: 1}, None, '0-20:Q', 600, 0xA798),                    # 0xA798, docked 0x7AF8
        ('gap_energy_bomb', {0xA84C: 1}, 1, '60-70:W', 300, 0x926C),                     # 0x926C
        ('gap_galactic_hyperdrive', {0xA84F: 1}, None, '0-20:G+H', 600, 0xD62B),         # 0xD62B
        ('gap_in_system_jump', {}, None, '0-5:O;15-30:S;50-55:1;80-85:H;850-870:J', 1200, 0x9987),  # 0x9987
        ('gap_game_over', {0x7046: 0, 0x7048: 0, 0x7054: 1, 0x7056: 1, 0x7058: 1, 0x705A: 1}, 2, '', 700, 0x7335),  # 0x7335
        ('gap_explosion', {}, 9, FIGHT, 300, 0x8572),                                    # explosion disc 0x8572
        ('gap_missile_hit', {0xA871: 4, 0xA872: 0x80}, 9, '0-5:T;10-14:F', 300, 0xF99A),  # ECM test skipped (0xF81B); hit 0xF99A
    ),
}


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
    if not quick:
        for name, pokes, event, keys, run, proof in GAPS[v['layout']]:
            out.append((name, 'flight', 0, '', dict(pokes=pokes, event=event), run, keys))
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
        if isinstance(inject, dict):                # a gap case: RAM pokes (equipment, position), then an event or none
            if inject.get('pokes'):
                path = _poke(path, inject['pokes'], path)
            inject = inject.get('event')
        if inject is not None:
            path = _inject(path, version, inject, path)
        paths[name] = path
        out[name] = (path, run, run_keys)
        if progress:
            progress('state %s' % name)
    return out


def _poke(src, pokes, out):
    """The state with RAM bytes set ({address: byte}): commander equipment and the like, before a gap case runs."""
    from . import simrun
    f, sim = simrun.free_run(src, 0, None)
    for a, b in pokes.items():
        sim.memory[int(a, 0) if isinstance(a, str) else a] = b
    return _save(sim, out)


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
    tsites = {a: (a, old, new) for a, old, new in p.applied if (a, old, new) in patch.tsites + patch.sdsites}
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
            if ts:                      # a title / SD hook: run as the instruction it replaced (module docstring)
                a, old, new = ts
                mp[a:a + len(old)] = old
                opp[mp[a]]()
                mp[a:a + len(new)] = new
                c['title hook' if ts in patch.tsites else 'sd hook'] += 1
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
        proof = {g[0]: g[5] for g in GAPS[E.VERSIONS[version]['layout']]}.get(name)
        if proof is not None:                       # a gap case must reach its routine, or it covers nothing
            c['gap reached' if proof in seen else '%s not reached!' % name] += 1
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


# ------------------------------------------------------------------------------------------------ SD save / load

SD_LAY = {'A': (0xD054, 0x66, 0xDED0), 'B': (0xA816, 0x68, 0xAC25)}    # block (IX), length (DE), typed-name buffer


class _Esx:
    """esxDOS as the hooks see it (RST 8 with automap on): F_OPEN / F_READ / F_WRITE / F_CLOSE on a dict of files.
    Like the real one it may come back with interrupts on and IY, HL, DE, the alternate set scrambled. Each call
    also checks the hook's conditions: ROM in slots 0 / 1 (DivMMC overlays them), automap on, stack and buffers above
    0x4000, HL = IX, and an interrupt now would reach an EI / RETI outside 0x0000-0x3FFF."""
    def __init__(self, files, fail_write=False):
        self.files, self.fail_write, self.open, self.bad, self.calls = files, fail_write, {}, [], []

    def call(self, R, mem, st):
        def w(a):
            return mem[a] | mem[(a + 1) & 0xFFFF] << 8
        sp = R[12]
        ret = w(sp)
        fn, ix, hl = mem[ret], R[8] << 8 | R[9], R[6] << 8 | R[7]
        if st['mmu'][0:2] != [0xFF, 0xFF] or not st['nr'].get(0x0A, 0) & 0x10:
            self.bad.append(('rst 8 without the ROM / automap', st['mmu'][0:2], st['nr'].get(0x0A)))
        if sp < 0x4000 or ix < 0x4000 or hl != ix:
            self.bad.append(('rst 8 registers', hex(sp), hex(ix), hex(hl)))
        i = R[14] << 8
        tab = {mem[i + k] for k in range(257)}
        vec = mem[i] * 257 if len(tab) == 1 else 0
        if i < 0x4000 or vec < 0x4000 or [mem[vec], mem[vec + 1], mem[vec + 2]] != [0xFB, 0xED, 0x4D]:
            self.bad.append(('an interrupt in esxDOS would not reach EI / RETI', hex(i), hex(vec)))
        a, bc, err = R[0], R[2] << 8 | R[3], False
        if fn == 0x9A:
            name, p = '', ix
            while mem[p] and len(name) < 64:
                name, p = name + chr(mem[p]), p + 1
            self.calls.append(('open', name, R[2]))
            if a != ord('*'):
                self.bad.append(('drive', a))
            if R[2] == 0x01 and name in self.files:
                h = 3 + len(self.open)
                self.open[h], a = [name, 0, 'r'], h
            elif R[2] == 0x0E and not self.fail_write:
                self.files[name] = b''
                h = 3 + len(self.open)
                self.open[h], a = [name, 0, 'w'], h
            else:
                a, err = 5, True
        elif fn in (0x9D, 0x9E):
            f = self.open.get(a)
            self.calls.append(('read' if fn == 0x9D else 'write', bc))
            if f is None or f[2] != ('r' if fn == 0x9D else 'w'):
                self.bad.append(('read / write on handle', a))
                err = True
            elif fn == 0x9D:
                d = self.files[f[0]][f[1]:f[1] + bc]
                for k, x in enumerate(d):
                    mem[ix + k] = x
                f[1] += len(d)
                bc = len(d)
            else:
                self.files[f[0]] += bytes(mem[ix + k] for k in range(bc))
        elif fn == 0x9B:
            self.calls.append(('close',))
            err = self.open.pop(a, None) is None
        else:
            self.bad.append(('function', hex(fn)))
            err = True
        R[0], R[2], R[3] = a, bc >> 8, bc & 255
        R[1] = (R[1] & 0xFE) | (1 if err else 0)
        for k in (4, 5, 6, 7, 10, 11, 16, 17, 18, 19, 20, 21, 22, 23):
            R[k] = (R[k] * 7 + 0x5A) & 255             # scrambled
        R[26] = 1                                       # back with interrupts on
        R[12], R[24] = sp + 2, (ret + 1) & 0xFFFF


def _sd_machine(nex):
    """A Next as the build leaves it in the game (48K mapping, alt ROM image 1 in slots 0 / 1, automap off), from the
    built .nex's banks: (memory, state, simulator class, nextreg handlers)."""
    from . import nextboot
    from .dizzy6 import _rw_simulator
    banks, _, _ = nextboot.load_nex(str(nex))
    pages = {}
    for b, data in banks.items():
        pages[2 * b], pages[2 * b + 1] = bytearray(data[0:8192]), bytearray(data[8192:16384])
    alt = bytes(banks[12][8192:16384] + banks[12][0:8192])
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 0, 1], 'nr': {0x0A: 0x05, 0x8C: 0x80}, 'sel': 0}

    class Mem(list):
        def __getitem__(s, a):
            m = st['mmu'][a >> 13]
            return alt[a] if m == 0xFF else pages.setdefault(m, bytearray(8192))[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = st['mmu'][a >> 13]
            if m != 0xFF:
                pages.setdefault(m, bytearray(8192))[a & 0x1FFF] = v
    return Mem([0] * 65536), st, _rw_simulator(), pages


def _sd_call(nex, entry, ret, regs, files, fail_write=False, limit=200000):
    """Run one hook call (entry = the CALL's target) on _sd_machine with the fake esxDOS until it returns to ret.
    -> (registers, memory, state, esx, problems)."""
    from skoolkit.simulator import R2
    mem, st, Sim, pages = _sd_machine(nex)
    for a, v in regs.pop('ram', {}).items():
        mem[a] = v
    sp = 0xF000
    mem[sp - 2], mem[sp - 1] = ret & 255, ret >> 8
    sim = Sim(mem, dict(regs, PC=entry, SP=sp - 2, **{'^BC': 0x1357, '^DE': 0x2468, '^HL': 0x9ABC, '^A': 0x11, '^F': 0x22}))
    R, ed = sim.registers, sim.after_ED
    R[14], R[27], R[26] = 0x39, 2, 1

    def nn():
        p = R[24]
        reg, val = sim.memory[p + 2], sim.memory[p + 3]
        st['nr'][reg] = val
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = val
        R[15] = R2[R[15]]
        R[24] = p + 4

    def na():
        p = R[24]
        reg = sim.memory[p + 2]
        st['nr'][reg] = R[0]
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = R[0]
        R[15] = R2[R[15]]
        R[24] = p + 3
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            if port == 0x253B and 0x50 <= st['sel'] <= 0x57:
                return st['mmu'][st['sel'] - 0x50]
            return st['nr'].get(st['sel'], 0) if port == 0x253B else 0xFF

        def write_port(s, regs_, port, value, *x):
            if port == 0x243B:
                st['sel'] = value
    sim.set_tracer(Tr())
    esx = _Esx(files, fail_write)
    before = {p: bytes(pages[p]) for p in (10, 11, 4, 5, 0, 1)}
    kept = [R[k] for k in (10, 11) + tuple(range(16, 24))]
    ops, n, bad = sim.opcodes, 0, []
    while not (R[24] == ret and R[12] == sp):
        if R[24] == 0x0008:
            esx.call(R, mem, st)
            continue
        if R[24] < 0x4000 and not 0x3900 <= R[24] < 0x3B00:
            bad.append(('PC in the ROM', hex(R[24])))
            break
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            bad.append(('no return', hex(R[24])))
            break
    if st['mmu'] != [0xFF, 0xFF, 10, 11, 4, 5, 0, 1] or st['nr'][0x0A] != 0x05 or R[14] != 0x39 or R[26] != 0:
        bad.append(('state after', st['mmu'], st['nr'][0x0A], hex(R[14]), 'IFF', R[26]))
    if [R[k] for k in (10, 11) + tuple(range(16, 24))] != kept:
        bad.append(('IY / alternate set not kept',))
    at = {10: 0x4000, 11: 0x6000, 4: 0x8000, 5: 0xA000, 0: 0xC000, 1: 0xE000}
    changed = sorted(at[p] + k for p, b in before.items() for k in range(8192) if pages[p][k] != b[k])
    changed = [a for a in changed if not sp - 16 <= a < sp]             # the game's stack below the return
    return R, mem, st, esx, bad + esx.bad, changed


def sd_check(patch, nex, neg=True):
    """The SD save / load hooks of a built .nex (asm "SD save / load"; games/elite_std.md "## SD save"), run on a Next
    memory model with a fake esxDOS (_Esx), every call checked for its conditions and for what it leaves (slots,
    NextReg 0x0A, I, interrupts off, the stack, RAM changed only where it should): save a short and a long name,
    load each back over a cleared block, an empty name (the last save), a missing name, another name in the same file,
    and a card that refuses writes. neg: two broken hooks (the extension's letter, the DI after RST 8) must fail.
    -> Counter (failures end in '!'), examples."""
    import shutil
    c, ex = collections.Counter(), []
    if not patch.sdsites:
        return c, ex
    lay = E.VERSIONS[patch.version]['layout']
    blk, n, typed = SD_LAY[lay]
    ld_site, sv_site = patch.sdsites[0], patch.sdsites[1]
    ld_e, sv_e = int.from_bytes(ld_site[2][1:3], 'little'), int.from_bytes(sv_site[2][1:3], 'little')
    ext = '.EL' + lay

    def run(nexf, tag, files, keep=None):
        k = collections.Counter()
        exs = []

        def ok(cond, key, detail=None):
            if cond:
                k[key] += 1
            else:
                k[key + '!'] += 1
                exs.append((tag, key, detail))

        def cmdr(name, seed):
            d = bytearray((seed * 37 + i * 11) & 255 for i in range(n))
            d[0:11] = name.encode().ljust(11, b'\0')[:11]
            return bytes(d)

        def do_save(name, seed, fail=False):
            d = cmdr(name, seed)
            R, mem, st, esx, bad, ch = _sd_call(nexf, sv_e, sv_site[0] + 3, dict(A=0xFF, IX=blk, DE=n, IY=0x5C3A,
                                                ram={blk + i: x for i, x in enumerate(d)}), files, fail)
            ok(not bad, 'sd call ok', bad[:3])
            ok(not ch, 'sd save leaves RAM', [hex(x) for x in ch[:4]])
            return d, R

        def do_load(typed_name, seed):
            pre = cmdr('PREVIOUS', seed)
            ram = {blk + i: x for i, x in enumerate(pre)}
            ram.update({typed + i: x for i, x in enumerate(typed_name.encode() + b'\0')})
            R, mem, st, esx, bad, ch = _sd_call(nexf, ld_e, ld_site[0] + 3, dict(A=0xFF, IX=blk, DE=n, IY=0x5C3A,
                                                ram=ram), files)
            ok(not bad, 'sd call ok', bad[:3])
            ok(not [a for a in ch if not blk <= a < blk + n], 'sd load leaves RAM', [hex(x) for x in ch[:4]])
            return bytes(mem[blk + i] for i in range(n)), R[1] & 1, pre

        a, R = do_save('JOE', 1)
        ok(R[1] & 1 and files.get('JOE' + ext) == a and files.get('_LAST' + ext) == a, 'save short name')
        b, R = do_save('MILICEVIC', 2)
        ok(R[1] & 1 and files.get('MILICEVI' + ext) == b and files.get('_LAST' + ext) == b, 'save long name',
           sorted(files))
        got, cy, pre = do_load('JOE', 3)
        ok(cy and got == a, 'load by name')
        got, cy, pre = do_load('MILICEVIC', 4)
        ok(cy and got == b, 'load long name')
        got, cy, pre = do_load('', 5)
        ok(cy and got == b, 'load empty name = last save')
        got, cy, pre = do_load('BOB', 6)
        ok(not cy and got == pre, 'load missing name fails, block kept')
        got, cy, pre = do_load('MILICEVIX', 7)
        ok(not cy and got == pre, 'load other name in the file fails')
        ro = dict(files)
        d, R = do_save('ZED', 8, fail=True)
        ok(not R[1] & 1 and files == ro, 'save on a refusing card fails')
        return k, exs

    k, e = run(nex, 'build', {})
    c.update(k)
    ex += e
    if neg:
        d = bytearray(open(nex, 'rb').read())
        import tempfile
        tmp = tempfile.mkdtemp(prefix='elite_sd_')
        try:
            for name, old, new in (('extension', b'.ELA\0', b'.FLA\0'),
                                   ('di', bytes([0xCF, 0x00, 0xF3]), bytes([0xCF, 0x00, 0x00]))):
                at = d.find(old)
                if at < 0 or d.find(old, at + 1) >= 0:
                    c['neg sd %s not found!' % name] += 1
                    continue
                bd = bytearray(d)
                bd[at:at + len(new)] = new
                p = os.path.join(tmp, name + '.nex')
                open(p, 'wb').write(bd)
                kk, _ = run(p, name, {})
                c['neg sd %s caught' % name if any(x.endswith('!') for x in kk) else 'neg sd %s missed!' % name] += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return c, ex


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
