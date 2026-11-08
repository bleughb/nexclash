#!/usr/bin/env python3
"""Report the palettes whose colours are outside the master palette (docs/COLOURS.md "PALETTE STANDARD").

    python tools/palette_check.py          one WARN line per palette with colours outside the master
    python tools/palette_check.py -v       also every palette found, on the standard or not

Report only: exit 0 whatever it finds (games published before the standard keep their colours until
their next update). It fails only if it cannot run. What it reads, without importing any engine:
  - nexclash/*.py: module-level literal constants with PAL in the name (PALETTE, L2PAL, FLOOR_PAL,
    WORLD_PAL, ...) and SPECCY: ints are RRRGGGBB bytes (0x41 writes; always master), triples RGB
    (a channel above 7: RGB888, else RGB333), 'RRGGBB' strings RGB888; FORMS below overrides;
  - docs/profiles/*.json, nexclash/*.json: values under a "palette" / "pal" key (lists of bytes or RGB
    triples, or a hex string of bytes);
  - asm/*.asm, asm/*.inc: DB / DEFB tables under a label with "pal" in its name, and .inc files whose
    header says they hold NextReg 0x44 byte pairs. A table whose every second byte is 0 or 1 is read
    as 0x44 pairs (RRRGGGBB, blue's low bit), any other as RRRGGGBB bytes.
Not seen: palettes computed at build time (they show as the constants they are computed from),
binary assets, and the Enhanced colour sets kept beside the user's snapshot (not in the repository).
"""
import argparse
import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nexclash import master_palette as MP     # noqa: E402

# (file, constant) -> colour form, where the values alone do not say it
FORMS = {('nexclash/herbert_colours.py', 'PALETTE'): 'rgb332'}
# (file, constant) -> why it is not a Next palette
IGNORE = {('nexclash/preview.py', 'PAL'): 'preview image of the original Spectrum picture, not a Next palette',
          ('nexclash/rainbow_objects.py', 'SPECCY'): 'object catalogue image for the maintainer, not a Next palette'}
# colour tables whose names do not say PAL
EXTRA = {('nexclash/new_zealand_story_paint.py', 'FIG_RULES'), ('nexclash/new_zealand_story_paint.py', 'BOSS_RULES')}
PY_NAME = re.compile(r'PAL|^SPECCY$')
PY_SKIP = re.compile(r'_(NAME|MD5|FREE|OFF|ON)$')
HEX6 = re.compile(r'^[0-9A-Fa-f]{6}$')
NUM = re.compile(r'^(0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]+|[0-9][0-9A-Fa-f]*[hH]|\d+)$')


def colours_of(v, form=None):
    """A literal value -> [(colour, form)]: RGB triples, ints and 'RRGGBB' strings, nested anywhere."""
    out = []
    if isinstance(v, dict):
        v = list(v.values())
    if isinstance(v, (list, tuple)):
        if len(v) == 3 and all(isinstance(x, int) and not isinstance(x, bool) for x in v) and form != 'ints':
            out.append((tuple(v), form or ('rgb888' if max(v) > 7 else 'rgb333')))
            return out
        ints = [x for x in v if isinstance(x, int) and not isinstance(x, bool)]
        if ints and len(ints) == len(v):
            f = 'next9' if max(ints) > 255 else 'next8'
            return [(x, f) for x in ints if 0 <= x <= 511]
        for x in v:
            out += colours_of(x, form)
    elif isinstance(v, str) and HEX6.match(v):
        out.append((tuple(int(v[i:i + 2], 16) for i in (0, 2, 4)), 'rgb888'))
    return out


def _one_rgb_form(cols, form=None):
    """One table, one RGB form: a triple with a channel above 7 makes every triple in it RGB888."""
    if not form and any(f == 'rgb888' for _, f in cols):
        form = 'rgb888'
    return [(c, form) if form and isinstance(c, tuple) else (c, f) for c, f in cols]


def scan_python():
    for path in sorted(glob.glob(os.path.join(ROOT, 'nexclash', '*.py'))):
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        tree = ast.parse(open(path, encoding='utf-8').read(), rel)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if not isinstance(t, ast.Name) or (rel, t.id) not in EXTRA and not (
                        PY_NAME.search(t.id) and not PY_SKIP.search(t.id)):
                    continue
                if (rel, t.id) in IGNORE:
                    continue
                try:
                    v = ast.literal_eval(node.value)
                except ValueError:
                    continue                     # computed: its inputs are checked where they are literals
                form = FORMS.get((rel, t.id))
                cols = _one_rgb_form(colours_of(v, form), form)
                if cols:
                    yield '%s:%d %s' % (rel, node.lineno, t.id), cols


def _json_pal(v):
    if isinstance(v, str) and re.fullmatch(r'(?:[0-9A-Fa-f]{2})+', v):
        return [(b, 'next8') for b in bytes.fromhex(v)]
    return _one_rgb_form(colours_of(v))


def scan_json():
    files = sorted(glob.glob(os.path.join(ROOT, 'docs', 'profiles', '*.json')) +
                   glob.glob(os.path.join(ROOT, 'nexclash', '*.json')))
    for path in files:
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        try:
            d = json.load(open(path, encoding='utf-8'))
        except (ValueError, UnicodeDecodeError):
            continue
        stack = [('', d)]
        while stack:
            where, o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == 'syms':
                        continue                 # hook symbol addresses, not colours
                    if k.lower() in ('palette', 'pal') and not isinstance(v, (dict, int)):
                        cols = _json_pal(v)
                        if cols:
                            yield '%s %s/%s' % (rel, where, k), cols
                    else:
                        stack.append(('%s/%s' % (where, k), v))
            elif isinstance(o, list) and o and isinstance(o[0], (dict, list)):
                stack += [('%s[%d]' % (where, i), x) for i, x in enumerate(o)]


def _num(tok):
    tok = tok.strip()
    if not NUM.match(tok):
        return None
    if tok.startswith('$'):
        return int(tok[1:], 16)
    if tok[-1] in 'hH':
        return int(tok[:-1], 16)
    return int(tok, 0) if tok.startswith('0x') else int(tok)


def _db_values(line):
    m = re.match(r'^\s*(?:[\w.]+:?\s+)?(?:DB|DEFB|db|defb)\s+(.*)$', line)
    if not m:
        return None
    vals = [_num(t) for t in m.group(1).split(';')[0].split(',')]
    return None if None in vals or not vals else vals


def _table(vals, pairs=None):
    if pairs is None:
        pairs = len(vals) >= 4 and len(vals) % 2 == 0 and all(v in (0, 1) for v in vals[1::2])
    if pairs:
        return [((vals[i], vals[i + 1]), 'pair') for i in range(0, len(vals) - 1, 2)]
    return [(v, 'next8') for v in vals if 0 <= v <= 255]


def scan_asm():
    for path in sorted(glob.glob(os.path.join(ROOT, 'asm', '*.asm')) + glob.glob(os.path.join(ROOT, 'asm', '*.inc'))):
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
        head = ' '.join(lines[:3])
        if path.endswith('.inc') and '0x44' in head and 'pair' in head:
            vals = [v for ln in lines for v in (_db_values(ln) or [])]
            if vals:
                yield rel, _table(vals, pairs=True)
            continue
        i = 0
        while i < len(lines):
            m = re.match(r'^([\w.]*pal[\w.]*):?(\s|$)', lines[i], re.I)
            if not m:
                i += 1
                continue
            start, vals = i, _db_values(lines[i]) or []
            i += 1
            while i < len(lines):
                more = None if re.match(r'^[\w.]+:?(\s|$)', lines[i]) and lines[i].strip() else _db_values(lines[i])
                if more is None:
                    break
                vals += more
                i += 1
            if len(vals) >= 4:                   # shorter: a variable (vpal: db 0), not a table
                yield '%s:%d %s' % (rel, start + 1, m.group(1)), _table(vals)


def report(verbose=False, out=sys.stdout):
    """-> (palettes checked, [(where, off entries, entries)]); prints the report."""
    gha = os.environ.get('GITHUB_ACTIONS') == 'true'
    seen, off_list = 0, []
    print('palette standard (docs/COLOURS.md "PALETTE STANDARD"): report only; '
          'games published before it keep their colours until their next update', file=out)
    for where, cols in list(scan_python()) + list(scan_json()) + list(scan_asm()):
        seen += 1
        off = []
        for c, f in cols:
            if not MP.is_master(c, f) and (c, f) not in off:
                off.append((c, f))
        forms = '/'.join(sorted({f for _, f in cols}))
        if off:
            off_list.append((where, off, cols))
            shown = ', '.join('%s->%s' % (_fmt(c, f), MP.describe(MP.nearest(c, f))) for c, f in off[:6])
            more = ' ...' if len(off) > 6 else ''
            n_off = sum(1 for c, f in cols if not MP.is_master(c, f))
            print('WARN %s (%s): %d of %d entries outside the master palette; nearest master: %s%s' % (
                where, forms, n_off, len(cols), shown, more), file=out)
            if gha:
                f_, _, rest = where.partition(' ')
                f_, _, line = f_.partition(':')
                print('::warning file=%s%s::palette standard: %d of %d entries outside the master palette' % (
                    f_, ',line=%s' % line if line else '', n_off, len(cols)), file=out)
        elif verbose:
            print('ok   %s (%s): %d entries, all master colours' % (where, forms, len(cols)), file=out)
    print('palette standard: %d palettes checked, %d with colours outside the master palette (warnings, '
          'not failures)' % (seen, len(off_list)), file=out)
    return seen, off_list


def _fmt(c, f):
    if f == 'pair':
        return '0x%02X,%d' % c
    if f == 'next9':
        return '0x%03X' % c
    return '(%d,%d,%d)' % c if isinstance(c, tuple) else '0x%02X' % c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-v', '--verbose', action='store_true', help='list every palette found, not only the warnings')
    a = ap.parse_args(argv)
    report(a.verbose)
    return 0


if __name__ == '__main__':
    sys.exit(main())
