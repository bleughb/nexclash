"""Recolour: a painted colour sheet -> <build>_painted.nex in about a second, for every engine that
supports it (Dean, 2026-10-14: "ALL games have this easy ability").

    python nexclash.py recolour BUILD_sprites.nex PAINTED.png [--layout L] [--game NAME] [-o OUT]
                                                              [--onto CURRENT_colours.json | --replace]

A painting is merged onto the map the build holds now (found by reproducing the build, or --onto):
only the pixels changed on the sheet change, so an older sheet cannot wipe newer paint; a pixel
painted two ways, or changed both on the sheet and since it was drawn, is refused. The output is a
bundle, written all or nothing: the painted .nex, its colours json, both sheets redrawn from their
own layouts with the new map (+ layouts) and a report (GPT6 review, 2026-10-27).

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


def reference_layout(painting_layout):
    """The reference sheet's layout beside a painting layout (X_PAINTING_SPRITES_layout.json ->
    X_REFERENCE_ALL_SPRITES_layout.json), or None when the name has no PAINTING_SPRITES part."""
    d, n = os.path.split(painting_layout)
    if '_PAINTING_SPRITES' not in n:
        return None
    return os.path.join(d, n.replace('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES', 1))


def current_map(nex, mod, nex_path, onto=None):
    """The map the build holds now -> (map, where it came from). A candidate counts only when
    recolouring the build with it gives the build back byte for byte: the .nex's own sidecar
    (<nex>_colours.json, written by recolour), the build's default map, the empty map. --onto names
    it explicitly. None when nothing reproduces the build (the caller refuses)."""
    from . import coloursheet as cs
    if onto:
        m = cs.load(onto)
        same = mod.recolour(nex, m)[0] == nex
        return m, '--onto %s%s' % (onto, '' if same else ' (NOTE: it does not reproduce this build\'s colours)')
    side = os.path.splitext(nex_path)[0] + '_colours.json'
    for where, m in (('sidecar %s' % os.path.basename(side), cs.load(side) if os.path.exists(side) else None),
                     ('the build default %s' % mod.RECOLOUR['colours'], build_map(mod)),
                     ('the empty map (unpainted build)', {})):
        if m is not None and mod.recolour(nex, m)[0] == nex:
            return m, where
    return None, None


def run(nex_path, colours, layout=None, game=None, output=None, say=print, onto=None, replace=False):
    """The command. `colours` = the painted PNG (layout json next to it, or `layout`) or a colours
    .json (used as the whole map). A painting is MERGED onto the map the build holds now
    (current_map; --onto names it; --replace starts from the sheet's own map instead): only the
    pixels the user changed on the sheet change. Refuses, writing nothing, on a pixel painted two
    different ways on the sheet, on a change that conflicts with the current map, or on a build no
    known map reproduces. Writes, all or nothing, next to the output: <nex>_painted.nex, its
    _colours.json, both sheets redrawn with the new map from their own layouts (+ layouts), and a
    _report.json. Returns the output path."""
    import json
    import shutil
    import tempfile
    from . import coloursheet as cs
    nex = open(nex_path, 'rb').read()
    name, mod = pick(nex, game)
    output = output or os.path.splitext(nex_path)[0] + '_painted.nex'
    base_ = os.path.basename(output).lower()
    if os.path.abspath(output) == os.path.abspath(nex_path) or not base_.endswith('_painted.nex'):
        raise ValueError('the output must be a new <name>_painted.nex (built .nex files are never overwritten)')
    ostem = os.path.splitext(output)[0]
    report = {'engine': name, 'input': os.path.basename(nex_path)}
    clear = mod.RECOLOUR.get('clear', False)
    lay = layout
    if colours.lower().endswith('.png'):
        lay = layout or find_layout(colours)
        base, chg, meta, sconf, rep = cs.changes(colours, lay, clear=clear)
        for k, v in sorted(rep.items()):
            say('%s: %d' % (k, v))
        warn_ignored(rep, say)
        if sconf:
            lines = ['%s bit %d: %s' % (k, b, '; '.join('%s -> %s' % (f, _st(st)) for f, st in lst))
                     for (k, b), lst in sconf[:20]]
            raise ValueError('%d pixel(s) painted two different ways on the sheet (one graphic shown in several '
                             'figures); paint each the same, or leave all but one copy unpainted:\n  %s'
                             % (len(sconf), '\n  '.join(lines)))
        if replace:
            cur, where = base, '--replace: the sheet\'s own map (%s)' % os.path.basename(lay)
        else:
            cur, where = current_map(nex, mod, nex_path, onto)
            if cur is None:
                raise ValueError('no known colour map reproduces %s (not its sidecar %s_colours.json, not the build '
                                 'default, not empty): give the map it was made with (--onto MAP.json), or --replace '
                                 'to start from this sheet alone' % (os.path.basename(nex_path), os.path.splitext(
                                     os.path.basename(nex_path))[0]))
        say('current map: %s (%d entries)' % (where, len(cur)))
        merged, mconf = cs.merge(base, chg, meta, cur)
        if mconf:
            lines = ['%s bit %d: sheet showed %s, painted %s, the build now has %s' % (k, b, _st(bs), _st(u), _st(c))
                     for (k, b), bs, u, c in mconf[:20]]
            raise ValueError('%d painted pixel(s) conflict with the current map (changed since this sheet was drawn); '
                             'repaint them on the refreshed sheet:\n  %s' % (len(mconf), '\n  '.join(lines)))
        if not replace and cur is not base and base != cur:
            say('merged onto the current map: the sheet was drawn with another map (%d entries); %d changed pixels '
                'applied, everything else kept' % (len(base), len(chg)))
        report.update({'current map': where, 'changed pixels': len(chg),
                       'report': {k: v for k, v in rep.items()}})
    else:
        merged = cs.load(colours)
        report.update({'current map': 'replaced by %s' % os.path.basename(colours)})
    work = tempfile.mkdtemp(prefix='.recolour_', dir=os.path.dirname(os.path.abspath(output)))
    try:
        files = {}
        cj = ostem + '_colours.json'
        tj = os.path.join(work, 'colours.json')
        cs.save(merged, tj, mod.RECOLOUR.get('note', ''))
        merged = cs.load(tj)
        out, info = mod.recolour(nex, merged)
        files[cj] = tj
        tn = os.path.join(work, 'build.nex')
        open(tn, 'wb').write(out)
        files[output] = tn
        missing = []
        if lay:
            sheets = [('painting', lay), ('reference', reference_layout(lay))]
            for kind, lp in sheets:
                if not lp or not os.path.exists(lp):
                    missing.append('%s sheet: no layout %s - not in this bundle' % (kind, lp or '(name has no _PAINTING_SPRITES)'))
                    continue
                sn = os.path.basename(lp)[:-len('_layout.json')] if lp.endswith('_layout.json') else os.path.splitext(os.path.basename(lp))[0]
                dst = '%s_%s' % (ostem, sn)
                tp, tl = os.path.join(work, kind + '.png'), os.path.join(work, kind + '.json')
                cs.redraw(lp, merged, tp, tl)
                files[dst + '.png'], files[dst + '_layout.json'] = tp, tl
        else:
            missing.append('sheets: no layout (a colours .json without --layout) - none in this bundle')
        inputs = {os.path.abspath(x) for x in (nex_path, colours, lay or '', onto or '') if x}
        clash = [f for f in files if os.path.abspath(f) in inputs]
        if clash:
            raise ValueError('an output would overwrite an input: %s' % clash)
        report.update({'map entries': len(merged), 'engine info': {k: v for k, v in info.items()},
                       'md5': hashlib.md5(out).hexdigest(), 'files': sorted(os.path.basename(f) for f in files),
                       'missing': missing})
        tr = os.path.join(work, 'report.json')
        json.dump(report, open(tr, 'w'), indent=1)
        files[ostem + '_report.json'] = tr
        for dst, src in files.items():                 # publish only now: every output was built
            os.replace(src, dst)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    say('%s: %s' % (name, ', '.join('%s %s' % (k, v if v != [] else 'none') for k, v in info.items())))
    say('-> %s  %s' % (output, report['md5']))
    for f in sorted(files):
        if f != output:
            say('-> %s' % f)
    for m in missing:
        say('NOTE: %s' % m)
    say('(copy %s to %s to make it the build default; then rebuild + verify)' % (os.path.basename(cj), mod.RECOLOUR['colours']))
    return output


def _st(st):
    return 'default' if st == 'D' else 'transparent' if st == 'T' else 'colour %d' % st[1]


def warn_ignored(rep, say=print):
    """Paint the colour map cannot hold (a coloursheet.read report): say so loudly (Dean's outlines
    were silently dropped once, Dizzy 1 2026-10-14)."""
    n = sum(v for k, v in rep.items() if '(ignored)' in k or 'kept default' in k)
    if n:
        say('WARNING: %d painted pixels were NOT used (lines above): paint only the grey and coloured '
            'pixels of a figure, on the sheet that goes with this _layout.json' % n)


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
    ap.add_argument('--onto', help='the colour map the build holds now (default: found by reproducing the build)')
    ap.add_argument('--replace', action='store_true', help='start from the sheet\'s own map, not the build\'s')
    a = ap.parse_args(argv)
    try:
        run(a.nex, a.colours, a.layout, a.game, a.output, onto=a.onto, replace=a.replace)
    except ValueError as e:
        sys.exit('recolour refused: %s' % e)


if __name__ == '__main__':
    _main()
