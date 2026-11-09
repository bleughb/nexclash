"""Atom Ant (Hi-Tec, 1990): the 128K form of the tape, unchanged.

The play area is white on black: no colour clash to remove, so there are no hooks and the game's code runs as it is.
The tape's last block, the AY music, loads only on a 128K machine, so the .z80 in the archive (a 48K dump) has none: the start
state is the tape loaded on a 128K machine, stopped at 9FF4, the game's own start after the music has loaded.
"""
from pathlib import Path
import hashlib
from . import z80tonex as zt

TAPE_MD5 = '404e992b4edceb10ef8fae9dfaac364b'
START_MD5 = '2ae624d49075367226a59766c860ea21'   # the derived start state (the review run's): never in this repo
START_PC = 0x9FF4
SIGNATURE = {0x9FF4: '31BF5D', 0x9E4A: 'CD71A7', 0xAB76: '3A5C5B', 0xA184: 'ED73F7A1'}
PUBLISHER = 'Hi-Tec, 1990'
DECISIONS = {'figures': 'none: white on black, as the original', 'scenery': 'as the original', 'pace': 'original; no hooks',
             'outline': 'none: figures have their own black masks',
             'enhanced': "the Spec256 set's colours on a full Layer 2, off by default (atom_ant_enh)"}

CMP = ()                           # the default runs no hook; Enhanced compares atom_ant_enh.CMP (hooklib.CMP_R)


def _profile_path():
    return Path(__file__).resolve().parents[1] / 'docs/profiles/atom_ant.json'


def load_profile():
    """The Enhanced hooks' profile: the default has none of its own."""
    import json
    return json.loads(_profile_path().read_text())


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """The default has no site, so nothing runs instead of the game's code: the boot check is its proof. An Enhanced
    patch is replayed by atom_ant_enh.verify."""
    from collections import Counter
    if not isinstance(patch, Patch):
        from . import atom_ant_enh as E
        return E.verify(patch, rzx_path, stop=stop, collect=collect)
    c = Counter(hooks=0)
    return (c, {}, []) if collect else (c, {})


def unit_tests(patch, states, neg=True):
    """Default: no hook, no case. Enhanced: atom_ant_enh.unit_tests."""
    from collections import Counter
    if not isinstance(patch, Patch):
        from . import atom_ant_enh as E
        return E.unit_tests(patch, states)
    return Counter()


def is_atom_ant(snap):
    """The tape's 128K start state: bank 2 holds the code, bank 3 the music. zt.Z80Snapshot (banks) or skoolkit's Snapshot
    (memory.banks, nexclash.py auto)."""
    if getattr(snap, 'banks', None) is None:
        banks = getattr(getattr(snap, 'memory', None), 'banks', None)
        if getattr(snap, 'machine', '48K') == '48K' or banks is None:
            return False
        try:
            return (bytes(banks[3][0xE75E - 0xC000:0xE75E - 0xC000 + 4]) == bytes.fromhex('21000FCD') and
                    all(bytes(banks[2][a - 0x8000:a - 0x8000 + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items()))
        except (KeyError, TypeError, IndexError):
            return False
    if not getattr(snap, 'is128', False):
        return False
    try:
        if snap.banks[3][0xE75E - 0xC000:0xE75E - 0xC000 + 4] != bytes.fromhex('21000FCD'):
            return False
        return all(bytes(snap.banks[2][a - 0x8000:a - 0x8000 + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (KeyError, TypeError, IndexError):
        return False


class Patch:
    """No hooks, no changed bytes: the start state checked, then converted."""
    name = 'Atom Ant 128K: the original, with its AY music'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = None
    stub_extra = b''
    extra_banks = {}

    def __init__(self, source=None):
        self.source = str(source) if source else None

    def apply(self, snap):
        if not is_atom_ant(snap):
            raise ValueError('Not the 128K start state of Atom Ant (tape MD5 %s)' % TAPE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2)."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the Enhanced replay proof -------------------
LOAD_SCREEN = 'atom_ant_loading.scr'      # the tape's screen, beside the start state: game data, never in this repo
LOAD_MD5 = '9f8b3417ce05f83346309e643bb58536'
# Enhanced, beside the start state, all three or none; game data derived from the Spec256 set, never in this repo:
SET_NAME, SET_MD5 = 'atom_ant.256', '057fea528187ea2d518e77fd7b146aaa'                      # the set as a .256
PANEL_NAME, PANEL_MD5 = 'atom_ant_panel.bin', 'b8fc47099bb732034ec47e346ad29371'          # the set's panel at moments of play
PALETTE_NAME, PALETTE_MD5 = 'atom_ant_palette.json', 'cc822d044ec89ffcffbfb3a122f4d088'   # the set's 256 colours
NEG_RECORDING, NEG_STOP = 'k1.rzx', 500   # the broken builds and the ABI states, as in the review run
# The archive's three, each tested alone (games/atom_ant.md); bank 8 = no paging.
TRAINERS = """NInfinite Lives
M 8 49384 0 0
Z 8 49444 0 0
NImmunity
M 8 49374 24 0
Z 8 49434 24 0
NInfinite Time
M 8 43749 0 0
Z 8 40674 195 0
Y
"""


def _beside(z80, file, md5, what):
    """A private input beside the start state -> its path, or None. A different file there is refused."""
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def enhanced_inputs(z80):
    """-> (set, panel, palette) paths beside the start state, or None when any is missing."""
    got = [_beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with'),
           _beside(z80, PANEL_NAME, PANEL_MD5, "the set's panel this engine was proved with"),
           _beside(z80, PALETTE_NAME, PALETTE_MD5, "the set's palette this engine was proved with")]
    return tuple(got) if all(got) else None


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all RAM 4000-FFFF (bank 0 at C000)
    against the patched start state, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites);
    the music bank 3 against the .nex's own. -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    slot1 = getattr(patch, 'slot1', None)
    size = len(zt.build_tail(s, 0x8000, slot1, slot1 is not None)[0])
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
    data = Path(nex).read_bytes()
    if data[18 + 3] != 1:
        bad.append(('music bank 3 not in the .nex',))
    return bad


def _enh_patch(z80, inputs):
    from . import atom_ant_enh as E
    return E.Patch(z80, *inputs)


def _replay(z80, inputs, rzx, stop, collect):
    """One recording's Enhanced replay (a process of its own) -> (counts, examples, states)."""
    from . import atom_ant_enh as E
    got = E.verify(_enh_patch(z80, inputs), rzx, stop=stop, collect=collect)
    return got if collect else (got[0], got[1], [])


def _negative(z80, inputs, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own): -> (name, its failure keys)."""
    from . import atom_ant_enh as E
    try:
        c, ex = E.verify(E.negative_patches(_enh_patch(z80, inputs))[name], rzx, stop=stop)
    except Exception as e:                  # noqa: BLE001 - a broken hook that runs off into data is caught too
        return name, ['exception ' + type(e).__name__]
    return name, sorted(k for k in c if k.endswith('!'))


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no hook, no game byte changed) and, with the set, panel and palette beside
    the start state, the Enhanced build; each with the tape's loading screen when it is beside the start state, as
    published; every build boot-checked. With --rzx the Enhanced replay proof of each recording, the ABI cases and the
    broken builds (the default runs no hook). The pace, soak, flicker and real loader proofs are the review run's
    (games/atom_ant.md "Evidence")."""
    import concurrent.futures, os
    from . import atom_ant_enh as E
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Atom Ant (Hi-Tec, 1990, the tape\'s 128K form with its AY music)')
    say("Engine    : atom_ant; default: the original, no hook (no clash to remove); Enhanced: the Spec256 set's colours "
        'on a full Layer 2 over the unchanged ULA')
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, "the tape's loading screen")
    inputs = enhanced_inputs(z80)
    if screen is None:
        say('Loading   : no %s beside the start state: builds without the loading screen' % LOAD_SCREEN)
    if inputs is None:
        say('Enhanced  : not all of %s, %s, %s beside the start state: default build only' % (SET_NAME, PANEL_NAME, PALETTE_NAME))
    builds = [('Default', name, lambda: Patch(z80))]
    if inputs is not None:
        art = _enh_patch(z80, inputs).art
        builds.append(('Enhanced', name + '_enhanced', lambda: E.Patch(z80, *inputs, keep_art=art)))
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
            say('Boot      : %s' % ('simulated, OK (registers with R, all RAM, the music bank; converter loader and NEXLOAD)'
                                    if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs and inputs is None:
        say('Verify    : FAILED: recordings given but no Enhanced inputs beside the start state (the default runs no hook; '
            'the replay proves Enhanced)')
        ok = False
    elif rzxs:
        quick = getattr(a, 'quick', None)
        neg = next((r for r in rzxs if Path(r).name == NEG_RECORDING), rzxs[0])
        jobs = [(r, quick, 0) for r in rzxs] + [(neg, min(quick or NEG_STOP, NEG_STOP), 1)]
        with concurrent.futures.ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1)) as pool:
            done = list(pool.map(_replay, [z80] * len(jobs), [inputs] * len(jobs), *zip(*jobs)))
        for (path, stop, collect), (c, ex, got) in zip(jobs, done):
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            if collect:
                states = got
                if fail:
                    say('Verify    : ABI states (%s to %d): %s' % (Path(path).name, stop, fail))
                continue
            say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d figures, %d Layer 2 pictures: %s' % (
                Path(path).name, c['frames'], c['hooks'], c['R comparisons'], c['figures'], c['publications'],
                'IDENTICAL' if not fail else str(fail)))
            for k, v in ex.items():
                say('            %s: %s' % (k, str(v)[:300]))
        counts = E.unit_tests(_enh_patch(z80, inputs), states)
        fail = {k: v for k, v in counts.items() if k.endswith('!')}
        ok = ok and not fail
        say('Unit      : %s (%d sites)' % (dict(counts), len(states)))
        names = list(E.negative_patches(_enh_patch(z80, inputs)))
        with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
            negs = list(pool.map(_negative, [z80] * len(names), [inputs] * len(names), names, [neg] * len(names),
                                 [min(quick or NEG_STOP, NEG_STOP)] * len(names)))
        missed = [n for n, keys in negs if not keys]
        ok = ok and not missed
        say('Negatives : %d of %d broken builds caught (%s, %d frames each)%s' % (
            len(negs) - len(missed), len(negs), Path(neg).name, min(quick or NEG_STOP, NEG_STOP),
            '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only (the default runs no hook)')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
