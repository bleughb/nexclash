"""Recolour: a painted colour sheet -> <build>_painted.nex in about a second, for every engine that
supports it (Dean, 2026-10-14: "ALL games have this easy ability").

    python nexclash.py recolour BUILD_sprites.nex PAINTED.png [--layout L] [--game NAME] [-o OUT]

The shared half lives here: reading the painted sheet (nexclash/coloursheet.py), the .nex bank
layout, splicing the rewritten banks, the output names, and the refusals (never overwrite a built
.nex; a .nex no engine recognises is refused with every engine's reason). The engine supplies the
rest, as two module-level names:

  RECOLOUR = {
    'game':      record name (docs/records/<game>.json), e.g. 'dizzy1',
    'output':    the record output it rewrites, e.g. 'sprites',
    'colours':   path of the build's colour map (docs/profiles/<game>_colours.json),
    'clear':     True if the sheet's grey means transparent (coloursheet.read(..., clear=True)),
    'note':      the note saved in the colours json,
  }
  def recolour(nex_bytes, cmap) -> (new_nex_bytes, info)
      Rewrites ONLY banks the game never reads (display data: sprite patterns, Layer 2, palettes),
      so the build's logic verification still holds. Raises ValueError (the reason) for any .nex that
      is not this engine's build of the expected game version. info: {'banks changed': [...], ...}.
      Build it on banks() / splice() below.

Selftest guard (selftest.py, every rebuild of a game whose engine has RECOLOUR): the game is built a
second time with an empty colour map (NEXCLASH_COLOURS=<empty map json>, which the engine's colour
loader must honour: build_colours_path()); recolouring the real build with {} must give that build
byte for byte, and recolouring it with the build's map must give the real build back. A recolour that
forgets a bank, or a builder that puts colour somewhere recolour does not rewrite, fails it.

Adding recolour to another engine: PLAYBOOK 3b ("Recolour"); the engine must first keep its colours
in banks the game never reads.
"""
import hashlib
import importlib
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def nex_offsets(d):
    """.nex bytes -> {bank: file offset} (nexclash/z80tonex.write_nex layout). ValueError if not."""
    from . import z80tonex as zt
    if bytes(d[0:4]) != b'Next':
        raise ValueError('not a .nex file')
    off, res = 512, {}
    for b in zt.BANK_FILE_ORDER:
        if d[18 + b]:
            res[b] = off
            off += 16384
    if off != len(d):
        raise ValueError('.nex size %d, banks say %d' % (len(d), off))
    return res


def banks(nex):
    """.nex bytes -> {bank: 16384 bytes}."""
    return {b: bytes(nex[o:o + 16384]) for b, o in nex_offsets(nex).items()}


def splice(nex, new_banks):
    """.nex bytes + {bank: 16384 bytes} -> (new .nex bytes, sorted list of banks that changed).
    Only banks the file already has; anything else is a ValueError."""
    d = bytearray(nex)
    off = nex_offsets(d)
    changed = []
    for b, data in sorted(new_banks.items()):
        if b not in off:
            raise ValueError('bank %d is not in this .nex' % b)
        if len(data) != 16384:
            raise ValueError('bank %d: %d bytes' % (b, len(data)))
        if bytes(d[off[b]:off[b] + 16384]) != bytes(data):
            changed.append(b)
        d[off[b]:off[b] + 16384] = data
    return bytes(d), changed


def engines():
    """{record name: engine module} for every record whose own module defines RECOLOUR."""
    from . import records as R
    res = {}
    for rec in R.all_records():
        for m in rec.get('own_modules', []):
            try:
                mod = importlib.import_module('nexclash.' + m)
            except Exception:                   # noqa: BLE001 - an engine that cannot import cannot recolour
                continue
            if getattr(mod, 'RECOLOUR', None) and mod.RECOLOUR.get('game') == rec['name']:
                res[rec['name']] = mod
    return res


def build_colours_path(default):
    """The colour map a build loads: $NEXCLASH_COLOURS when set (the selftest guard's empty-map build),
    else the engine's default. Every engine with RECOLOUR loads its map through this."""
    return os.environ.get('NEXCLASH_COLOURS') or default


def colours_path(mod):
    p = mod.RECOLOUR['colours']
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def build_map(mod):
    """The colour map the build uses ({} when the engine has none yet)."""
    from . import coloursheet as cs
    p = colours_path(mod)
    return cs.load(p) if os.path.exists(p) else {}


def pick(nex, game=None):
    """-> (name, module) for the engine that accepts this .nex; ValueError with every reason if none."""
    eng = engines()
    if game:
        if game not in eng:
            raise ValueError('%s has no recolour (engines with recolour: %s)' % (game, ', '.join(sorted(eng)) or 'none'))
        eng = {game: eng[game]}
    why = []
    for name, mod in sorted(eng.items()):
        try:
            mod.recolour(nex, build_map(mod))   # its checks; the result is thrown away
            return name, mod
        except ValueError as e:
            why.append('%s: %s' % (name, e))
    raise ValueError('no engine recognises this .nex - ' + '; '.join(why or ['no engine has recolour']))


def find_layout(png):
    """The painting layout next to a painted PNG: X_layout.json, or for X_painted.png / X (2).png
    the sheet's own X_layout.json. ValueError if none."""
    import re
    stem = os.path.splitext(png)[0]
    for s in (stem, re.sub(r'(_painted| ?\(\d+\))+$', '', stem, flags=re.I)):
        if os.path.exists(s + '_layout.json'):
            return s + '_layout.json'
    raise ValueError('no painting layout next to %s (pass --layout <game>_PAINTING_SPRITES_layout.json)' % png)


def run(nex_path, colours, layout=None, game=None, output=None, say=print):
    """The command. `colours` = the painted PNG (layout json next to it, or `layout`) or a colours
    .json. Writes <nex>_painted.nex + <nex>_painted_colours.json; returns the output path."""
    from . import coloursheet as cs
    nex = open(nex_path, 'rb').read()
    name, mod = pick(nex, game)
    output = output or os.path.splitext(nex_path)[0] + '_painted.nex'
    base = os.path.basename(output).lower()
    if os.path.abspath(output) == os.path.abspath(nex_path) or not base.endswith('_painted.nex'):
        raise ValueError('the output must be a new <name>_painted.nex (built .nex files are never overwritten)')
    cj = os.path.splitext(output)[0] + '_colours.json'
    if colours.lower().endswith('.png'):
        lay = layout or find_layout(colours)
        ent, rep = cs.read(colours, lay, clear=mod.RECOLOUR.get('clear', False))
        for k, v in sorted(rep.items()):
            say('%s: %d' % (k, v))
    else:
        ent = cs.load(colours)
    cs.save(ent, cj, mod.RECOLOUR.get('note', ''))
    out, info = mod.recolour(nex, cs.load(cj))
    open(output, 'wb').write(out)
    say('%s: %s' % (name, ', '.join('%s %s' % (k, v if v != [] else 'none') for k, v in info.items())))
    say('-> %s  %s' % (output, hashlib.md5(out).hexdigest()))
    say('-> %s (copy it to %s to make it the build default; then rebuild + verify)'
        % (cj, mod.RECOLOUR['colours']))
    return output


def guard(nex, blank, mod):
    """Selftest guard. nex = the build with its colour map, blank = the same build with an empty map.
    -> (ok, info)."""
    cmap = build_map(mod)
    try:
        down, _ = mod.recolour(nex, {})
        up, _ = mod.recolour(blank, cmap)
    except ValueError as e:
        return False, 'refused its own build: %s' % e
    nb = banks(nex)
    for label, got, want in (('recolour(build, {}) != empty-map build', down, blank),
                             ('recolour(empty-map build, map) != build', up, nex)):
        if got != want:
            gb, wb = banks(got), banks(want)
            return False, '%s: banks %s' % (label, [b for b in wb if wb[b] != gb.get(b)])
    return True, '%d map entries; recolour = full build both ways (colour banks %s)' % (
        len(cmap), [b for b in nb if nb[b] != banks(blank)[b]] or 'none: no colours painted')


def selfcheck():
    """Shared half on a synthetic .nex (no game data): offsets, splice, refusals. -> list of failures."""
    from . import z80tonex as zt
    bad = []
    order = list(zt.BANK_FILE_ORDER)[:3]
    hdr = bytearray(512)
    hdr[0:4] = b'Next'
    for b in order:
        hdr[18 + b] = 1
    nex = bytes(hdr) + b''.join(bytes([i]) * 16384 for i in range(len(order)))
    if nex_offsets(nex) != {b: 512 + 16384 * i for i, b in enumerate(order)}:
        bad.append('offsets')
    new, ch = splice(nex, {order[1]: b'\x07' * 16384, order[2]: b'\x02' * 16384})
    if ch != [order[1]] or banks(new)[order[1]] != b'\x07' * 16384 or banks(new)[order[0]] != banks(nex)[order[0]]:
        bad.append('splice')
    for args in ((nex[:-1],), (b'Nope' + nex[4:],)):
        try:
            nex_offsets(*args)
            bad.append('accepted a bad .nex')
        except ValueError:
            pass
    missing = next(b for b in range(112) if b not in order)
    try:
        splice(nex, {missing: bytes(16384)})
        bad.append('spliced a bank the .nex lacks')
    except ValueError:
        pass
    return bad


def _main(argv=None):
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog='nexclash.py recolour', description=__doc__.split('\n\n')[0])
    ap.add_argument('nex', help='the built <game>_sprites.nex')
    ap.add_argument('colours', help='the painted <game>_PAINTING_SPRITES.png, or a colours .json')
    ap.add_argument('--layout', help='the painting layout json (default: next to the PNG)')
    ap.add_argument('--game', help='record name (default: the engine that recognises the .nex)')
    ap.add_argument('-o', '--output', help='default: <nex>_painted.nex next to the input')
    a = ap.parse_args(argv)
    try:
        run(a.nex, a.colours, a.layout, a.game, a.output)
    except ValueError as e:
        sys.exit('recolour refused: %s' % e)


if __name__ == '__main__':
    _main()
