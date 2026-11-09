"""Jilly's Farm Volume 1 - SokoBAArn! (Bob's Stuff, 2017, 48K): the original game on the Next, no figures moved.

Every level's play area is one colour on black (bright white), so the game has no colour clash there. The default is the
original picture. The build owns the ROM (Sinclair's 48K ROM as the whole alt ROM) so the game runs the same on any
NextZXOS. No hook, no site, not one game byte changes. See games/jillys_farm.md.
"""
from pathlib import Path
import json
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/jillys_farm.json'
SOURCE_MD5 = '86a5e1dc43e4cfe45582e91eb7cd1cf3'
REGBLOCK = 0x3C00
REGS_LEN = 20
PAGE = 25
SIGNATURE = {0x8200: '31C0FEF33E80ED47ED5EFB', 0x8181: 'F5E5218FA134', 0x83A8: 'C34C83'}
DECISIONS = {'figures': 'unchanged: monochrome play area', 'scenery': 'unchanged', 'pace': 'original: no hook', 'outline': 'none',
             'enhanced': "the Spec256 set's values on Layer 2, off by default (jillys_farm_enh)"}
CMP = ()


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_jillys(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = "Jilly's Farm: the original game, Sinclair ROM as the whole alt ROM"
    uses_printer_buffer = False
    keep_printer_buffer = True
    hook_page_data = b''
    stub_extra = b''
    setup_call = None
    sites = ()

    def __init__(self, source=None):
        self.source = str(source) if source else None
        rom = zt.rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        self.slot1 = (PAGE, REGBLOCK)
        self.altrom = (REGBLOCK, REGBLOCK + REGS_LEN)
        self.extra_banks = {PAGE // 2: bytes(8192) + bytes(self.page)}

    def apply(self, snap):
        if not is_jillys(snap):
            raise ValueError("Not the supported Jilly's Farm release (MD5 %s)" % SOURCE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """No hook: what can differ is the ROM and the tail; nextboot.rom_paths replays the original against the .nex."""
    from collections import Counter
    c = Counter(hooks=0)
    if patch.sites:
        c['a site in a no-hook build!'] += 1
    return (c, {}, []) if collect else (c, {})


def unit_tests(patch, states, neg=True):
    from collections import Counter
    return Counter()


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the Enhanced replay proof -------------------
LOAD_SCREEN, LOAD_MD5 = 'jillys_farm_loading.scr', '8a2b35914b9d038f27443578bb999475'   # the tape's screen: game data
# Enhanced, beside the start state, both or neither; never in this repo:
SET_NAME, SET_MD5 = 'jillys_farm.256', '34a22ecc05c805464303e7e0f49db611'                    # the Spec256 set (Ynicky, V1.00)
PALETTE_NAME, PALETTE_MD5 = 'jillys_farm_palette.json', 'cc822d044ec89ffcffbfb3a122f4d088'  # the set's 256 colours as RGB
NEG_RECORDING, NEG_STOP = 'a1.rzx', 400   # the broken builds and the ABI states, as in the review run
# a broken build that shows only at a level change: its own recording and length, as in the review run
LONG_NEG = {'wipe not done': ('levels.rzx', 2500)}


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def _beside(z80, file, md5, what):
    """A private input beside the start state -> its path, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def enhanced_inputs(z80):
    """-> (set, palette) paths beside the start state, or None when either is missing."""
    got = (_beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with'),
           _beside(z80, PALETTE_NAME, PALETTE_MD5, "the set's palette this engine was proved with"))
    return tuple(str(p) for p in got) if all(got) else None


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched start
    state, bar the start-up tail (and, unless the build restores it, the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    slot1 = getattr(patch, 'slot1', None)
    altrom = getattr(patch, 'altrom', None) is not None
    size = len(zt.build_tail(s, 0x8000, slot1, altrom)[0])
    tail = zt.choose_tail_addr(s, size, getattr(patch, 'tail_addr', None), bool(patch.uses_printer_buffer))[0]
    keep = getattr(patch, 'keep_printer_buffer', False)
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size or (nexload and not keep and 0x5B00 <= a < 0x5C00):
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _replay(z80, inputs, rzx, stop, collect):
    """One recording's Enhanced replay (a process of its own) -> (name, counts, failures, states)."""
    from . import jillys_farm_enh as E
    r = E.verify(E.Patch(z80, *inputs), rzx, stop=stop, collect=collect)
    c, ex, states = r[0], r[1], (r[2] if len(r) > 2 else [])
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}, states


def _negative(z80, inputs, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own) -> (name, its failure keys)."""
    from . import jillys_farm_enh as E
    try:
        return name, sorted(E.run_negative(E.negative_patches(E.Patch(z80, *inputs))[name], rzx, stop))
    except Exception as e:          # noqa: BLE001 - a broken hook that runs off into data is caught too
        return name, ['exception ' + type(e).__name__]


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no hook, no game byte changed) and, with the set and its palette beside the
    start state, the Enhanced build; each with the tape's loading screen when it is beside the start state, as published;
    every build boot-checked. With --rzx the Enhanced replay of each recording, the ABI cases and the broken builds (the
    default runs no hook). Pace, soak, flicker and the real loader are the review runs' (games/jillys_farm.md "Evidence")."""
    import concurrent.futures, hashlib, os
    from . import jillys_farm_enh as E
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = "Bob's Stuff, 2017"
    say("Game      : Jilly's Farm Volume 1 - SokoBAArn! (Bob's Stuff, 2017, V1.01)")
    say("Engine    : jillys_farm; default: the original, no hook (no clash to remove); Enhanced: the Spec256 set's values "
        "on Layer 2 over the unchanged ULA")
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, "the tape's loading screen")
    inputs = enhanced_inputs(z80)
    if screen is None:
        say('Loading   : no %s beside the start state: builds without the loading screen' % LOAD_SCREEN)
    builds = [('Default', name, lambda: Patch(z80))]
    if inputs is None:
        say('Enhanced  : not both of %s, %s beside the start state: default build only' % (SET_NAME, PALETTE_NAME))
    else:
        builds.append(('Enhanced', name + '_enhanced', lambda: E.Patch(z80, *inputs)))
    for label, stem, make in builds:
        nex = out / (stem + '.nex')
        zt.convert(str(z80), str(nex), patch=make(), quiet=True)
        nexes = [(label, nex)]
        if screen is not None:
            loading = out / (stem + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
            nexes.append((label[:3] + '+scr', loading))
        for lab, path in nexes:
            bad = boot_check(path, z80, make())
            ok = ok and not bad
            say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)' if not bad
                                    else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    quick = getattr(a, 'quick', None)
    if rzxs and inputs is None:
        say('Verify    : FAILED: recordings given but no Enhanced inputs beside the start state (the default runs no hook; '
            'the replay proves Enhanced)')
        ok = False
    elif rzxs:
        byname = {Path(r).name: r for r in rzxs}
        neg = byname.get(NEG_RECORDING, rzxs[0])
        nstop = NEG_STOP if quick is None else min(quick, NEG_STOP)
        with concurrent.futures.ProcessPoolExecutor(os.cpu_count() or 1) as pool:
            first = pool.submit(_replay, z80, inputs, neg, nstop, 1)
            reps = [pool.submit(_replay, z80, inputs, r, quick, 0) for r in rzxs]
            negs = []
            if quick is None:
                for k in E.negative_patches(E.Patch(z80, *inputs)):
                    rec, stop = LONG_NEG.get(k, (NEG_RECORDING, NEG_STOP))
                    negs.append(pool.submit(_negative, z80, inputs, k, byname.get(rec, neg), stop))
            for f in reps:
                rname, c, fail, _ = f.result()
                ok = ok and not fail
                say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d value pictures, %d Layer 2 pictures, '
                    '%d screens: %s' % (rname, c.get('frames', 0), c.get('hooks', 0), c.get('R comparisons', 0),
                                        c.get('value pictures compared', 0), c.get('Layer 2 pictures compared', 0),
                                        c.get('screens compared', 0), 'IDENTICAL' if not fail else str(fail)[:400]))
            u = E.unit_tests(E.Patch(z80, *inputs), first.result()[3])
            ok = ok and not [k for k in u if k.endswith('!')] and u.get('ABI cases', 0) > 0
            say('Unit      : %s (%d sites)' % (dict(u), len(first.result()[3])))
            if negs:
                res = dict(f.result() for f in negs)
                missed = [k for k, v in res.items() if not v]
                ok = ok and not missed
                say('Negatives : %d of %d broken builds caught (%s, %d frames each; %s)%s' % (
                    len(res) - len(missed), len(res), Path(neg).name, nstop,
                    ', '.join('%s on %s to %d' % (k, r, n) for k, (r, n) in LONG_NEG.items()),
                    '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only (the default runs no hook)')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
