"""El Capitan Trueno (Dinamic, 1990, 48K) engine 'trueno': the start of an engine. Additive module:
reachable only through is_trueno().

What is here: the detector (signature at the figure plotter's entry 0x82DF), the plain build with the
start-up tail that a scan of the whole recording proved safe (0xA6C9) and the boot check.
What is NOT here: the sprite build and its proof.
  - The hooks are asm/trueno_hooks.asm (profile docs/profiles/el_capitan_trueno.json, the base assembly).
    The tables they use (patterns, shape directory, Layer 2 cells, title, portraits) come from the
    contributor's build chain (games/el_capitan_trueno_build.md), which needs hand-drawn sheets and is
    not part of the toolkit.
  - verify() and unit_tests() are not written; the plan is in games/el_capitan_trueno.md,
    "Verification plan". auto() says so and returns False, so nothing stamps this game as proven.
Game facts: games/el_capitan_trueno.md (render, depth, tail) and games/el_capitan_trueno_build.md.
"""
import json
import os

TAIL_ADDR = 0xA6C9          # write-first area 0xA6C9-0xAAA2 over the whole recording (scan --rzx)
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'el_capitan_trueno.json'),
              os.path.join(_HERE, 'el_capitan_trueno.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('el_capitan_trueno.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_trueno(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    raise NotImplementedError('trueno: no differential test yet (games/el_capitan_trueno.md, Verification plan)')


def unit_tests(patch, states, neg=None):
    raise NotImplementedError('trueno: no unit tests yet (games/el_capitan_trueno.md, Verification plan)')


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : trueno (El Capitan Trueno: figure plotter 0x82DF; plain build only, see nexclash/trueno.py)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X: write-first over the whole recording; the converter default '
        'puts it below SP, above 0xC000, and the game never starts)' % (
            os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    say('Sprites   : not built here - the tables come from the contributor\'s chain '
        '(games/el_capitan_trueno_build.md)')
    say('Verify    : not done (games/el_capitan_trueno.md, Verification plan)')
    say('Result    : PLAIN ONLY, sprite build NOT VERIFIED')
    return False
