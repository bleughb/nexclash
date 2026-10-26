#!/usr/bin/env python3
"""Technique cards (docs/techniques/STANDARD.md): generate the index and check cards, predicates
and game recipes.

    python tools/techindex.py            write docs/techniques/index.json
    python tools/techindex.py --check    exit 1 if the index is stale or a check fails (doccheck runs check())

Checks STRUCTURE, never technical truth: card metadata and mandatory sections, predicate names,
the fixed Display-proof wording (patch), Measurements (optimise), lifecycle, the `owns` shape,
the card size budget; predicates.json fields; records' `techniques` / `results`; overlaps between
a game's applications (each needs an `overlap_ok` reason); the `Techniques:` line in games/<game>.md.
Not a game dependency (docs/records): changing it re-verifies nothing.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, 'docs', 'techniques')
INDEX = os.path.join(TDIR, 'index.json')
NOT_CARDS = {'STANDARD.md', 'CHANGELOG.md'}
KINDS = {'detect', 'patch', 'optimise', 'verify'}
LIFECYCLE = {'candidate', 'active', 'deprecated'}
PHASES = {'setup', 'entry', 'exit', 'commit', 'isr', 'clear', 'menu'}
EVALUATION = {'auto', 'manual', 'proposed'}
STATUS = {'not_run', 'pass', 'fail', 'partial'}
META = ('schema', 'id', 'revision', 'kind', 'title', 'question', 'tags', 'lifecycle', 'superseded_by',
        'requires', 'rejects', 'conflicts', 'phases', 'order', 'owns', 'examples', 'sources')
SECTIONS = ('Use / do not use', 'Recognise', 'Probe and stop', 'Contract', 'Resources owned',
            'Failure lookup', 'Verification', 'Evidence')
OWNS = {'mmu_slots', 'next_pages', 'memory', 'sprite_ids', 'pattern_slots', 'registers_clobbered',
        'vectors', 'speed', 'hook_state'}
SPACES = {'next_page': 'page', 'game_ram': 'bank', 'alt_rom': 'image'}
DISPLAY = re.compile(r'Display: software = (return/boundary only|entry-to-exit coverage \([^)]+\)); '
                     r'hardware = checklist item "[^"]+"')
WORDS_MAX = 600              # card body after the metadata block (STANDARD 3: 300-600 words)
APP_KEYS = ('application', 'id', 'revision', 'target', 'phases')


def _cards():
    out = {}
    for p in sorted(glob.glob(os.path.join(TDIR, '*.md'))):
        if os.path.basename(p) not in NOT_CARDS:
            out[os.path.basename(p)] = open(p).read()
    return out


def _meta(text):
    m = re.search(r'```json\n(.*?)```', text, re.S)
    return (json.loads(m.group(1)), text[m.end():]) if m else (None, text)


def build():
    """-> the index entries (STANDARD 12), sorted by id."""
    out = []
    for name, text in _cards().items():
        meta, body = _meta(text)
        if not meta:
            continue
        use = re.search(r'^## Use / do not use\n(.*?)(?=\n## |\Z)', body, re.S | re.M)
        first = re.split(r'(?<=[.!?])\s', ' '.join(use.group(1).split()), maxsplit=1)[0] if use else ''
        out.append({k: meta.get(k) for k in ('id', 'kind', 'lifecycle', 'superseded_by', 'question')}
                   | {'summary': first}
                   | {k: meta.get(k, []) for k in ('requires', 'rejects', 'conflicts', 'tags', 'examples')}
                   | {'path': 'docs/techniques/' + name})
    return sorted(out, key=lambda e: e['id'])


def _ranges_overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def _num(x):
    return int(x, 16) if isinstance(x, str) else int(x)


def _owns_shape(owns, where, concrete, fail):
    for k, v in owns.items():
        if k not in OWNS:
            fail.append('%s: owns key %r not in the schema' % (where, k))
        elif v == 'param':
            if concrete:
                fail.append('%s: owns %s is "param" in a recipe (give the values)' % (where, k))
        elif k == 'memory':
            for r in v:
                key = SPACES.get(r.get('space'))
                if not key or key not in r or 'offset' not in r:
                    fail.append('%s: memory range needs space (%s) + its id + offset: %r' % (where, '/'.join(SPACES), r))


def _resources(owns):
    """-> {(kind, identity): [(lo, hi), ...]} for overlap checks (physical identity for memory)."""
    out = {}
    for k in ('mmu_slots', 'next_pages', 'vectors', 'registers_clobbered'):
        for v in owns.get(k, []) if isinstance(owns.get(k), list) else []:
            out.setdefault((k, str(v)), []).append((0, 0))
    for k in ('sprite_ids', 'pattern_slots'):
        for r in owns.get(k, []) if isinstance(owns.get(k), list) else []:
            out.setdefault((k, ''), []).append((r[0], r[1]))
    for r in owns.get('memory', []) if isinstance(owns.get('memory'), list) else []:
        key = SPACES.get(r.get('space'))
        if key and key in r and 'offset' in r:
            out.setdefault(('memory', '%s %s' % (r['space'], r[key])), []).append(
                (_num(r['offset'][0]), _num(r['offset'][1])))
    return out


def check():
    """-> list of FAIL strings (empty = PASS)."""
    fail = []
    try:
        preds = json.load(open(os.path.join(TDIR, 'predicates.json')))
    except (OSError, ValueError) as e:
        return ['docs/techniques/predicates.json: %s' % e]
    for name, p in preds.items():
        if name.startswith('_'):
            continue
        miss = [k for k in ('means', 'true_when', 'false_when', 'evaluation', 'survey_field', 'probe') if k not in p]
        if miss:
            fail.append('predicate %s: missing %s' % (name, ', '.join(miss)))
        if p.get('evaluation') not in EVALUATION:
            fail.append('predicate %s: evaluation must be one of %s' % (name, sorted(EVALUATION)))
        if p.get('evaluation') == 'auto' and not p.get('survey_field'):
            fail.append('predicate %s: auto needs an existing survey_field' % name)
    ids = {}
    for name, text in _cards().items():
        where = 'docs/techniques/' + name
        meta, body = _meta(text)
        if meta is None:
            fail.append('%s: no ```json metadata block' % where)
            continue
        miss = [k for k in META if k not in meta]
        if miss:
            fail.append('%s: metadata missing %s' % (where, ', '.join(miss)))
            continue
        ids[meta['id']] = meta
        if name != meta['id'] + '.md':
            fail.append('%s: file name must be <id>.md (%s)' % (where, meta['id']))
        if meta['kind'] not in KINDS or not meta['id'].startswith(meta['kind'] + '.'):
            fail.append('%s: kind %r (one of %s; id starts with it)' % (where, meta['kind'], sorted(KINDS)))
        if meta['lifecycle'] not in LIFECYCLE:
            fail.append('%s: lifecycle %r' % (where, meta['lifecycle']))
        if meta['lifecycle'] == 'deprecated' and not meta['superseded_by']:
            fail.append('%s: deprecated needs superseded_by' % where)
        for k in ('requires', 'rejects'):
            for p in meta[k]:
                if p not in preds:
                    fail.append('%s: %s predicate %r not in predicates.json' % (where, k, p))
        bad = set(meta['phases']) - PHASES
        if bad:
            fail.append('%s: phases %s not in %s' % (where, sorted(bad), sorted(PHASES)))
        if meta['kind'] in ('patch', 'optimise') and not meta['phases']:
            fail.append('%s: a %s card needs phases' % (where, meta['kind']))
        for ph in meta['order']:
            if ph != 'cross' and ph not in PHASES:
                fail.append('%s: order key %r is not a phase or "cross"' % (where, ph))
        _owns_shape(meta['owns'], where, False, fail)
        heads = re.findall(r'^## (.+)$', body, re.M)
        for s in SECTIONS:
            if s not in heads:
                fail.append('%s: section "## %s" missing' % (where, s))
        if meta['kind'] == 'patch' and not DISPLAY.search(body):
            fail.append('%s: no Display-proof line in the fixed form (STANDARD 2)' % where)
        if meta['kind'] == 'optimise' and not re.search(r'^### Measurements$', body, re.M):
            fail.append('%s: optimise card needs "### Measurements"' % where)
        if len(body.split()) > WORDS_MAX:
            fail.append('%s: %d words > %d (size budget)' % (where, len(body.split()), WORDS_MAX))
    for meta in ids.values():
        for k in ('conflicts', 'superseded_by'):
            for ref in ([meta[k]] if isinstance(meta[k], str) else meta[k] or []):
                if ref not in ids:
                    fail.append('card %s: %s %r is not a card' % (meta['id'], k, ref))
    for r in sorted(glob.glob(os.path.join(ROOT, 'docs', 'records', '*.json'))):
        rec = json.load(open(r))
        where = 'docs/records/' + os.path.basename(r)
        apps = rec.get('techniques')
        if apps is None:
            continue
        names = set()
        for a in apps:
            miss = [k for k in APP_KEYS if k not in a]
            if miss:
                fail.append('%s: application missing %s: %r' % (where, ', '.join(miss), a.get('application')))
                continue
            if a['application'] in names:
                fail.append('%s: application %s twice' % (where, a['application']))
            names.add(a['application'])
            card = ids.get(a['id'])
            if not card:
                fail.append('%s: %s uses unknown card %s' % (where, a['application'], a['id']))
                continue
            if a['revision'] > card['revision']:
                fail.append('%s: %s revision %s > card %s' % (where, a['application'], a['revision'], card['revision']))
            if set(a['phases']) - PHASES:
                fail.append('%s: %s phases %s' % (where, a['application'], a['phases']))
            _owns_shape(a.get('owns', {}), '%s %s' % (where, a['application']), True, fail)
        for x in rec.get('results', []):
            if x.get('status') not in STATUS:
                fail.append('%s: result status %r (one of %s)' % (where, x.get('status'), sorted(STATUS)))
            if x.get('application') not in names:
                fail.append('%s: result for unknown application %r' % (where, x.get('application')))
            for k in ('check', 'scope', 'evidence'):
                if not x.get(k):
                    fail.append('%s: result %s needs %s' % (where, x.get('application'), k))
        res = [(a['application'], _resources(a.get('owns', {}))) for a in apps if 'application' in a]
        for i, (na, ra) in enumerate(res):
            for nb, rb in res[i + 1:]:
                for key in set(ra) & set(rb):
                    if any(_ranges_overlap(x, y) for x in ra[key] for y in rb[key]):
                        ok = [o for a in apps if a.get('application') in (na, nb)
                              for o in a.get('overlap_ok', []) if o.get('with') in (na, nb) and o.get('why')]
                        if not ok:
                            fail.append('%s: %s and %s both own %s %s (add overlap_ok with a reason)' % (
                                where, na, nb, key[0], key[1]))
        doc = os.path.join(ROOT, 'games', rec.get('doc') or rec['name'] + '.md')
        if os.path.exists(doc):
            line = re.search(r'^Techniques: (.+)$', open(doc).read(), re.M)
            used = {a.get('id') for a in apps}
            listed = set(re.findall(r'`((?:detect|patch|optimise|verify)\.[a-z0-9.-]+)`', line.group(1))) if line else set()
            if not line:
                fail.append('%s: no "Techniques:" line (record %s has techniques)' % (os.path.relpath(doc, ROOT), rec['name']))
            elif listed - used:
                fail.append('%s: Techniques line lists %s not in the record' % (os.path.relpath(doc, ROOT), sorted(listed - used)))
    try:
        if json.load(open(INDEX)) != build():
            fail.append('docs/techniques/index.json is stale: python tools/techindex.py')
    except (OSError, ValueError):
        fail.append('docs/techniques/index.json missing: python tools/techindex.py')
    return fail


def main():
    if '--check' not in sys.argv:
        # one entry per line: an agent greps or reads it whole for a few hundred tokens
        open(INDEX, 'w').write('[\n' + ',\n'.join(json.dumps(e) for e in build()) + '\n]\n')
    f = check()
    for x in f:
        print('FAIL ' + x)
    print('techindex: %s (%d cards)' % ('FAIL' if f else 'PASS', len(build())))
    return 1 if f else 0


if __name__ == '__main__':
    sys.exit(main())
