#!/usr/bin/env python3
"""The repository's knowledge as data: one deterministic export, and lookups over it.

  python tools/knowledge.py export [-o FILE]     JSON lines (stdout by default)
  python tools/knowledge.py coverage             what is recorded as data, and what is not yet
  python tools/knowledge.py eligible GAME        cards eligible / excluded / deferred (STANDARD 5)
  python tools/knowledge.py precedent GAME [-n N]  games whose predicate values agree most
  python tools/knowledge.py risks GAME           hardware-risk items that apply (docs/risks.json)
  python tools/knowledge.py lessons WORD ...     shared lessons (docs/kb/lessons.json) and every game's own
                                                 lessons holding every word; -n N of the games' (default 12)
  python tools/knowledge.py lessons --game GAME  shared lessons that apply to the game (their `when`)
  python tools/knowledge.py recurring [-n N]     maintainers: terms the [local] lessons of N+ games share
                                                 (default 3) and no shared lesson names - sweep candidates
  python tools/knowledge.py eval                 leave-one-out: do precedents predict the cards used?
  python tools/knowledge.py check                structure only (also run by tools/doccheck.py)

GAME is a record name (docs/records/<name>.json) or `--values FILE`, a JSON object
{predicate: "true" | "false" | "unknown"} for a game that has no record yet.

The export reads only files in this repository and writes no dates, so the same commit gives the
same bytes. Every row has `type`, `id` and `src` (path + first 16 hex digits of its SHA-256, as
nexclash.records hashes dependencies); the first row carries the commit. Any index built from it
can be rebuilt from any commit: the files stay the source, nothing here is edited by hand.

Row types: export, game, card, predicate, application, result, predicate_value, predicate_implied,
lesson, shared_lesson, technique_use, friction, learning, backlog, risk.

Predicate values. A record may state them (STANDARD 5, tools/templates/predicates.json):
  "predicates": [{"predicate": id, "value": true|false|unknown|conflicted, "scope": ..., "basis": ...,
                  "source": survey|scan|disassembly|verify|hardware|design, "evidence": optional}]
`predicate_implied` rows are NOT statements: an applied card implies someone judged its `requires`
true and its `rejects` false. They help retrieval and are never used by `eval` (the cards would
predict themselves). Lookups name which kind each value is.

Checks STRUCTURE, never truth (as techindex / learncheck).
"""
import collections
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = 1
VALUES = ('true', 'false', 'unknown', 'conflicted')
SOURCES = ('survey', 'scan', 'disassembly', 'verify', 'hardware', 'design')
LEVELS = ('observed', 'inferred', 'demonstrated')
TAG = re.compile(r'\[(card|doc|tool|backlog|probe|kb|local|deferred|none)\b:?\s*([^\]]*)\]')
USE = re.compile(r'([\w./-]+):\s*(used|helped|no help|corrected)\b:?\s*(.*)')
RISKS = 'docs/risks.json'
LESSONS = 'docs/kb/lessons.json'
TERM = re.compile(r'\b(?:0x[0-9A-Fa-f]{4}|(?=[0-9]*[A-F])[0-9A-F]{4}|[A-Za-z]+_[A-Za-z_]+|[A-Z][A-Z0-9]{3,}|[A-Z][a-z]+[A-Z]\w*)\b')


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8', newline='') as f:
        return f.read().replace('\r\n', '\n')           # as committed (LF), whatever the checkout


def _sha(rel):
    return hashlib.sha256(_read(rel).encode('utf-8')).hexdigest()[:16]


def _rels(pattern):
    return sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(ROOT, pattern)))


def _hid(text):
    return hashlib.sha256(' '.join(text.split()).encode('utf-8')).hexdigest()[:10]


def _bullets(text, title):
    """'## title' section -> its "- " bullets, continuation lines joined (learncheck._section)."""
    m = re.search(r'^## %s\s*$(.*?)(?=^## |\Z)' % re.escape(title), text, re.M | re.S)
    items, cur = [], None
    for line in (m.group(1).splitlines() if m else []):
        if line.startswith('- '):
            cur = [line[2:].strip()]
            items.append(cur)
        elif cur is not None and line.startswith('  ') and line.strip():
            cur.append(line.strip())
        elif not line.strip():
            cur = None
    return [' '.join(x) for x in items]


def _commit():
    try:
        out = lambda *a: subprocess.run(('git', '-C', ROOT) + a, capture_output=True, text=True, check=True).stdout
        return out('rev-parse', 'HEAD').strip(), bool(out('status', '--porcelain').strip())
    except (OSError, subprocess.CalledProcessError):
        return None, None                                   # a package without Git


def _value(v):
    return {True: 'true', False: 'false'}.get(v, v) if isinstance(v, (bool, str)) else None


def records():
    return [(rel, json.loads(_read(rel))) for rel in _rels('docs/records/*.json')]


def cards():
    out = {}
    for rel in _rels('docs/techniques/*.md'):
        m = re.search(r'```json\n(.*?)\n```', _read(rel), re.S)
        if m and os.path.basename(rel) not in ('STANDARD.md', 'CHANGELOG.md'):
            meta = json.loads(m.group(1))
            out[meta['id']] = (rel, meta)
    return out


def predicates():
    return {k: v for k, v in json.loads(_read('docs/techniques/predicates.json')).items() if not k.startswith('_')}


def risks():
    return json.loads(_read(RISKS))['risks'] if os.path.exists(os.path.join(ROOT, RISKS)) else []


def shared():
    return json.loads(_read(LESSONS))['lessons'] if os.path.exists(os.path.join(ROOT, LESSONS)) else []


def _hay(x):
    return ' '.join([x.get('id', ''), x.get('title', ''), x.get('text', ''), x.get('card') or ''] + x.get('words', [])).lower()


def find(words, shared_rows, game_rows):
    """-> (shared lessons, games' lesson rows) that hold every word (case ignored)."""
    ws = [w.lower() for w in words]
    return ([x for x in shared_rows if all(w in _hay(x) for w in ws)],
            [r for r in game_rows if all(w in r['text'].lower() for w in ws)])


def recurring(game_rows, shared_rows, floor=3):
    """Terms (addresses, identifiers, names) in the [local] lessons of `floor`+ game files that no shared lesson
    holds -> [(term, [docs])], most games first. A sweep list for a reader: a term is a lead, not a finding."""
    known = ' '.join(_hay(x) for x in shared_rows)
    where = collections.defaultdict(set)
    for r in game_rows:
        if any(t['kind'] == 'local' for t in r['tags']):
            for term in set(TERM.findall(re.sub(r'^\[[^\]]*\]', '', r['text']))):
                where[term].add(r['doc'])
    return sorted(((t, sorted(d)) for t, d in where.items() if len(d) >= floor and t.lower() not in known),
                  key=lambda x: (-len(x[1]), x[0]))


def stated(rec):
    """-> {predicate: value over its scopes}: one value, 'conflicted' when scopes disagree."""
    seen = collections.defaultdict(set)
    for p in rec.get('predicates', []):
        seen[p.get('predicate')].add(_value(p.get('value')))
    out = {}
    for k, vs in seen.items():
        known = vs & {'true', 'false'}
        out[k] = 'conflicted' if len(known) == 2 or 'conflicted' in vs else (known.pop() if known else 'unknown')
    return out


def implied(rec, cs):
    """-> {predicate: (value, [card ids])} from the cards the record applies."""
    why = collections.defaultdict(lambda: collections.defaultdict(list))
    for a in rec.get('techniques', []):
        if a.get('id') in cs:
            meta = cs[a['id']][1]
            for k, v in (('requires', 'true'), ('rejects', 'false')):
                for p in meta.get(k, []):
                    why[p][v].append(a['id'])
    return {p: ('conflicted' if len(v) == 2 else list(v)[0], sorted({c for x in v.values() for c in x}))
            for p, v in why.items()}


def values(rec, cs, with_implied=True):
    """-> {predicate: (value, 'stated' | 'implied')}; a stated value always wins."""
    out = {p: (v, 'implied') for p, (v, _) in implied(rec, cs).items()} if with_implied else {}
    out.update({p: (v, 'stated') for p, v in stated(rec).items()})
    return out


def rows():
    commit, dirty = _commit()
    cs, preds = cards(), predicates()
    yield dict(type='export', id='export', schema=SCHEMA, commit=commit, dirty=dirty,
               version=_read('VERSION').strip())
    docs = {}
    for rel, r in records():
        src = dict(path=rel, sha=_sha(rel))
        name = r['name']
        doc = 'games/' + (r.get('doc') or name + '.md')
        docs.setdefault(doc, []).append(name)
        snap = (r.get('inputs') or {}).get('snapshot') or {}
        yield dict(type='game', id=name, title=r.get('game'), engine=r.get('engine'), doc=doc,
                   reference=r.get('reference'), snapshot_md5=snap.get('md5'),
                   strategy=((r.get('rebuild') or {}).get('decisions') or {}).get('strategy'),
                   status={k: (r.get('status') or {}).get(k) for k in ('software', 'hardware', 'next')}, src=src)
        for a in r.get('techniques', []):
            yield dict(type='application', id='%s/%s' % (name, a.get('application')), game=name, card=a.get('id'),
                       revision=a.get('revision'), target=a.get('target'), src=src)
        for i, x in enumerate(r.get('results', [])):
            yield dict(type='result', id='%s/%s/%d' % (name, x.get('application'), i), game=name,
                       application=x.get('application'), check=x.get('check'), status=x.get('status'),
                       scope=x.get('scope'), evidence=x.get('evidence'), src=src)
        for i, p in enumerate(r.get('predicates', [])):
            yield dict(type='predicate_value', id='%s/%s/%d' % (name, p.get('predicate'), i), game=name,
                       predicate=p.get('predicate'), value=_value(p.get('value')), scope=p.get('scope'),
                       basis=p.get('basis'), source=p.get('source'), evidence=p.get('evidence'), src=src)
        for p, (v, why) in sorted(implied(r, cs).items()):
            if p not in stated(r):
                yield dict(type='predicate_implied', id='%s/%s' % (name, p), game=name, predicate=p, value=v,
                           cards=why, src=src)
    for cid, (rel, m) in sorted(cs.items()):
        yield dict(type='card', id=cid, kind=m.get('kind'), title=m.get('title'), question=m.get('question'),
                   lifecycle=m.get('lifecycle'), revision=m.get('revision'), requires=m.get('requires', []),
                   rejects=m.get('rejects', []), conflicts=m.get('conflicts', []), tags=m.get('tags', []),
                   src=dict(path=rel, sha=_sha(rel)))
    psrc = dict(path='docs/techniques/predicates.json', sha=_sha('docs/techniques/predicates.json'))
    for pid, p in sorted(preds.items()):
        yield dict(type='predicate', id=pid, means=p.get('means'), evaluation=p.get('evaluation'),
                   survey_field=p.get('survey_field'), probe=p.get('probe'), src=psrc)
    for rel in _rels('games/*.md'):
        text, src, stem = _read(rel), dict(path=rel, sha=_sha(rel)), os.path.basename(rel)[:-3]
        recs = docs.get(rel, [])
        for item in _bullets(text, 'Lessons'):
            yield dict(type='lesson', id='%s#%s' % (stem, _hid(item)), doc=rel, games=recs,
                       tags=[dict(kind=k, ref=a.strip()) for k, a in TAG.findall(item)],
                       evidence=[w for w in LEVELS if re.search(r'\b%s\b' % w, item)], text=item, src=src)
        for item in _bullets(text, 'Technique use'):
            m = USE.match(item)
            if m:
                yield dict(type='technique_use', id='%s#%s' % (stem, _hid(item)), doc=rel, games=recs,
                           ref=m.group(1), outcome=m.group(2), note=m.group(3), src=src)
        for item in _bullets(text, 'Friction'):
            key, _, rest = item.partition(':')
            yield dict(type='friction', id='%s#%s' % (stem, _hid(item)), doc=rel, games=recs, key=key.strip(),
                       text=rest.strip(), src=src)
    rel = 'docs/LEARNINGS.md'
    src, sec = dict(path=rel, sha=_sha(rel)), None
    for block in re.split(r'\n(?=#{1,3} |- )', _read(rel)):
        h = re.match(r'#{1,3} (\S+)\s*(.*)', block)
        if h:
            sec = h.group(1) if re.match(r'\d', h.group(1)) else None
        elif block.startswith('- ') and sec:
            text = ' '.join(block[2:].split())
            yield dict(type='learning', id='L%s#%s' % (sec, _hid(text)), section=sec, text=text, src=src)
    rel = 'docs/BRIEFING.md'
    m = re.search(r'^### C2\..*?$(.*?)(?=^### )', _read(rel), re.M | re.S)
    src = dict(path=rel, sha=_sha(rel))
    seen = collections.Counter()
    for n, text in re.findall(r'^(\d+)\. (.*?)(?=^\d+\. |^\S|\Z)', m.group(1) if m else '', re.M | re.S):
        seen[n] += 1                                        # a number given twice: the later item is C2#N~2
        yield dict(type='backlog', id='C2#' + n + ('~%d' % seen[n] if seen[n] > 1 else ''), number=int(n),
                   text=' '.join(text.split()), src=src)
    if risks():
        src = dict(path=RISKS, sha=_sha(RISKS))
        for x in risks():
            yield dict(type='risk', src=src, **x)
    if shared():
        src = dict(path=LESSONS, sha=_sha(LESSONS))
        for x in shared():
            yield dict(type='shared_lesson', src=src, **x)


def export():
    return ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in rows())


def eligible(vals, cs, preds):
    """vals {predicate: value} -> [(card id, 'eligible' | 'excluded' | 'deferred', reason)] (STANDARD 5)."""
    out = []
    for cid, (_, m) in sorted(cs.items()):
        if not (m.get('requires') or m.get('rejects')):
            continue
        need = [(p, 'true') for p in m.get('requires', [])] + [(p, 'false') for p in m.get('rejects', [])]
        got = [(p, want, vals.get(p, 'unknown')) for p, want in need]
        wrong = [p for p, want, v in got if v in ('true', 'false') and v != want]
        open_ = [p for p, want, v in got if v not in ('true', 'false')]
        if wrong:
            out.append((cid, 'excluded', ', '.join('%s is %s' % (p, vals[p]) for p in wrong)))
        elif open_:
            out.append((cid, 'deferred', '; '.join('%s: %s' % (p, preds.get(p, {}).get('probe', '?')) for p in open_)))
        else:
            out.append((cid, 'eligible', 'every requires true, every rejects false'))
    return out


def precedent(vals, pool, top=5):
    """vals {predicate: value}; pool {game: {predicate: value}} -> [(score, agree, differ, game)], best first.
    Only predicates known (true / false) on both sides count; unknown is never a match."""
    out = []
    for g, other in pool.items():
        both = [p for p in vals if vals[p] in ('true', 'false') and other.get(p) in ('true', 'false')]
        agree = sum(vals[p] == other[p] for p in both)
        if both:
            out.append((agree - (len(both) - agree), agree, len(both) - agree, g))
    return sorted(out, key=lambda x: (-x[0], -x[1], x[3]))[:top]


def applies(risk, vals):
    """A risk applies unless one of its `when` predicates is known false (not seen is not absent)."""
    return not any(vals.get(p) == 'false' for p in risk.get('when', []))


def evaluate(recs, cs, top=3):
    """Leave one out over records with STATED values and applied cards: are the game's patch cards among
    those its `top` precedents applied? -> (games scored, cards hit, cards wanted)."""
    data = {r['name']: (stated(r), {a['id'] for a in r.get('techniques', []) if a.get('id', '').startswith('patch.')})
            for _, r in recs if r.get('predicates') and r.get('techniques')}
    n = hit = want = 0
    for g, (vals, used) in data.items():
        near = precedent(vals, {k: v[0] for k, v in data.items() if k != g}, top)
        if not near or not used:
            continue
        guess = set().union(*(data[x[3]][1] for x in near))
        n, hit, want = n + 1, hit + len(used & guess), want + len(used)
    return n, hit, want


def check():
    """-> list of FAIL strings (empty = PASS)."""
    fail, cs, preds = [], cards(), predicates()
    for rel, r in records():
        ps = r.get('predicates', [])
        if not isinstance(ps, list):
            fail.append('%s: predicates must be a list (tools/templates/predicates.json)' % rel)
            continue
        seen = set()
        for p in ps:
            where = '%s: predicate %s' % (rel, p.get('predicate'))
            if p.get('predicate') not in preds:
                fail.append('%s not in docs/techniques/predicates.json' % where)
            if _value(p.get('value')) not in VALUES:
                fail.append('%s: value %r (one of %s)' % (where, p.get('value'), ', '.join(VALUES)))
            if p.get('source') not in SOURCES:
                fail.append('%s: source %r (one of %s)' % (where, p.get('source'), ', '.join(SOURCES)))
            for k in ('scope', 'basis'):
                if not p.get(k):
                    fail.append('%s needs %s' % (where, k))
            if (p.get('predicate'), p.get('scope')) in seen:
                fail.append('%s: scope %r given twice' % (where, p.get('scope')))
            seen.add((p.get('predicate'), p.get('scope')))
            ev = (p.get('evidence') or '').split('#')[0]
            if ev and not ev.startswith('http') and not os.path.exists(os.path.join(ROOT, ev)):
                fail.append('%s: evidence file %s not found' % (where, ev))
    ids = set()
    for x in risks():
        where = '%s: risk %s' % (RISKS, x.get('id'))
        if not re.fullmatch(r'risk\.[a-z0-9-]+', x.get('id') or '') or x['id'] in ids:
            fail.append('%s: id must be unique risk.<name>' % where)
        ids.add(x.get('id'))
        for k in ('title', 'source', 'cover'):
            if not x.get(k):
                fail.append('%s needs %s' % (where, k))
        for p in x.get('when', []):
            if p not in preds:
                fail.append('%s: when %r not in predicates.json' % (where, p))
        doc, _, phrase = (x.get('source') or '').partition('#')
        if doc and not os.path.exists(os.path.join(ROOT, doc)):
            fail.append('%s: source file %s not found' % (where, doc))
        elif phrase and phrase not in _read(doc):
            fail.append('%s: source text %r not in %s' % (where, phrase, doc))
    ids = set()
    for x in shared():
        where = '%s: %s' % (LESSONS, x.get('id'))
        if not re.fullmatch(r'lesson\.[a-z0-9-]+', x.get('id') or '') or x['id'] in ids:
            fail.append('%s: id must be unique lesson.<name>' % where)
        ids.add(x.get('id'))
        for k in ('title', 'text', 'sources', 'words'):
            if not x.get(k):
                fail.append('%s needs %s' % (where, k))
        if x.get('level') not in LEVELS:
            fail.append('%s: level %r (one of %s)' % (where, x.get('level'), ', '.join(LEVELS)))
        for p in x.get('when', []):
            if p not in preds:
                fail.append('%s: when %r not in predicates.json' % (where, p))
        if x.get('card') and x['card'] not in cs:
            fail.append('%s: no card %s' % (where, x['card']))
        for s in x.get('sources') or []:
            if not re.fullmatch(r'games/[\w.-]+\.md', s) or not os.path.exists(os.path.join(ROOT, s)):
                fail.append('%s: source %s is not a games/<game>.md file' % (where, s))
    try:
        text = export()
        seen = collections.Counter((json.loads(l)['type'], json.loads(l)['id']) for l in text.splitlines())
        fail.extend('export: id %s/%s given %d times' % (t, i, n) for (t, i), n in sorted(seen.items()) if n > 1)
        if text != export():
            fail.append('export: two runs differ')
    except Exception as e:                                  # a malformed source file: say which stage
        fail.append('export failed: %s: %s' % (type(e).__name__, e))
    fail.extend(selfcheck())
    return fail


def selfcheck():
    """The lookups on made-up values (no repository data)."""
    bad = []
    cs = {'patch.a': ('', dict(requires=['p.x'], rejects=['p.y'])), 'patch.b': ('', dict(requires=['p.z'], rejects=[]))}
    got = {c: s for c, s, _ in eligible({'p.x': 'true', 'p.y': 'false'}, cs, {})}
    if got != {'patch.a': 'eligible', 'patch.b': 'deferred'}:
        bad.append('selfcheck eligible: %s' % got)
    if {c: s for c, s, _ in eligible({'p.x': 'true', 'p.y': 'true', 'p.z': 'false'}, cs, {})} != {
            'patch.a': 'excluded', 'patch.b': 'excluded'}:
        bad.append('selfcheck excluded')
    near = precedent({'p.x': 'true', 'p.y': 'false', 'p.z': 'unknown'},
                     {'g1': {'p.x': 'true', 'p.y': 'false'}, 'g2': {'p.x': 'false', 'p.y': 'false'}, 'g3': {'p.z': 'true'}})
    if [x[3] for x in near] != ['g1', 'g2'] or near[0][:3] != (2, 2, 0):
        bad.append('selfcheck precedent: %s' % near)
    if stated({'predicates': [dict(predicate='p', value=True), dict(predicate='p', value='false')]}) != {'p': 'conflicted'}:
        bad.append('selfcheck stated')
    if applies({'when': ['p.x']}, {'p.x': 'false'}) or not applies({'when': ['p.x']}, {}):
        bad.append('selfcheck applies')
    sh = [dict(id='lesson.a', title='Loader', text='NEXLOAD overwrites 5B00', words=['boot'], when=['p.x'])]
    gl = [dict(doc='games/g%d.md' % i, text='[local: here] NEXLOAD and frame_serial at 0xBD40', tags=[dict(kind='local')])
          for i in range(3)] + [dict(doc='games/g9.md', text='[card c] NEXLOAD frame_serial', tags=[dict(kind='card')])]
    a, b = find(['nexload', 'BOOT'], sh, gl)
    if [x['id'] for x in a] != ['lesson.a'] or b or len(find(['nexload'], sh, gl)[1]) != 4:
        bad.append('selfcheck find')
    if [t for t, _ in recurring(gl, sh)] != ['0xBD40', 'frame_serial'] or recurring(gl, sh, 4):
        bad.append('selfcheck recurring: %s' % recurring(gl, sh))
    recs = [('', dict(name=n, predicates=[dict(predicate='p.x', value=v)], techniques=[dict(id=c)]))
            for n, v, c in (('a', True, 'patch.a'), ('b', True, 'patch.a'), ('c', False, 'patch.b'))]
    if evaluate(recs, cs, 1) != (3, 2, 3):
        bad.append('selfcheck evaluate: %s' % (evaluate(recs, cs, 1),))
    return bad


def _vals(argv, cs):
    """-> (label, {predicate: value}, {predicate: 'stated' | 'implied'})"""
    if argv[:1] == ['--values']:
        raw = json.load(open(argv[1], encoding='utf-8'))
        return argv[1], {k: _value(v) for k, v in raw.items()}, {k: 'stated' for k in raw}
    rec = dict((r['name'], r) for _, r in records()).get(argv[0] if argv else '')
    if rec is None:
        sys.exit('no record %r in docs/records (or use --values FILE)' % (argv[0] if argv else ''))
    v = values(rec, cs)
    return rec['name'], {k: x[0] for k, x in v.items()}, {k: x[1] for k, x in v.items()}


def main(argv):
    cmd, rest = (argv[0] if argv else ''), argv[1:]
    cs, preds = cards(), predicates()
    if cmd == 'export':
        text = export()
        if rest[:1] == ['-o']:
            with open(rest[1], 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            print('%s: %d rows' % (rest[1], text.count('\n')))
        else:
            sys.stdout.reconfigure(encoding='utf-8', newline='\n')
            sys.stdout.write(text)
        return 0
    if cmd == 'check':
        bad = check()
        print('\n'.join(bad) or 'knowledge check OK')
        return 1 if bad else 0
    if cmd == 'coverage':
        recs = [r for _, r in records()]
        kinds = collections.Counter(r['type'] for r in rows())
        print('records %d: with techniques %d, with stated predicates %d, with feasibility %d' % (
            len(recs), sum(bool(r.get('techniques')) for r in recs), sum(bool(r.get('predicates')) for r in recs),
            sum(bool(r.get('feasibility')) for r in recs)))
        print('cards %d: %s' % (len(cs), ', '.join('%s %d' % kv for kv in sorted(
            collections.Counter(m['lifecycle'] for _, m in cs.values()).items()))))
        print('predicates %d: %s' % (len(preds), ', '.join('%s %d' % kv for kv in sorted(
            collections.Counter(p['evaluation'] for p in preds.values()).items()))))
        print('rows: ' + ', '.join('%s %d' % kv for kv in sorted(kinds.items())))
        twice = sorted(r['number'] for r in rows() if r['type'] == 'backlog' and '~' in r['id'])
        if twice:
            print('WARN BRIEFING C2 numbers given twice (a [backlog C2 #N] tag cannot tell them apart): %s' % twice)
        return 0
    if cmd == 'eval':
        n, hit, want = evaluate(records(), cs)
        if n < 2:
            print('eval: %d games with stated predicates and applied cards - nothing to score yet' % n)
        else:
            print('eval: %d games, %d of %d patch cards found among the 3 nearest precedents (%.0f%%)' % (
                n, hit, want, 100.0 * hit / want))
        return 0
    if cmd == 'lessons' and rest[:1] not in (['--game'], ['--values']):
        top = int(rest[rest.index('-n') + 1]) if '-n' in rest else 12
        words = [w for i, w in enumerate(rest) if w != '-n' and (i == 0 or rest[i - 1] != '-n')]
        if not words:
            sys.exit('lessons WORD ... | lessons --game GAME | lessons --values FILE')
        sys.stdout.reconfigure(encoding='utf-8')
        sh, own = find(words, shared(), [r for r in rows() if r['type'] == 'lesson'])
        for x in sh:
            print('%s  %s (%s; %s)%s\n    %s' % (x['id'], x['title'], x['level'], ', '.join(
                os.path.basename(s)[:-3] for s in x['sources']), '  card ' + x['card'] if x.get('card') else '', x['text']))
        for r in own[:top]:
            print('%s  %s' % (r['doc'], r['text'][:300]))
        more = ' (first %d: -n N for more)' % top if len(own) > top else ''
        print("%d shared, %d in the games' notes%s" % (len(sh), len(own), more))
        return 0
    if cmd == 'recurring':
        floor = int(rest[rest.index('-n') + 1]) if '-n' in rest else 3
        for term, docs in recurring([r for r in rows() if r['type'] == 'lesson'], shared(), floor):
            print('%-24s %2d  %s' % (term, len(docs), ' '.join(os.path.basename(d)[:-3] for d in docs)))
        return 0
    if cmd == 'lessons':
        rest = rest[1:] if rest[0] == '--game' else rest
        cmd = 'lessons-for'
    if cmd in ('eligible', 'precedent', 'risks', 'lessons-for'):
        top = int(rest[rest.index('-n') + 1]) if '-n' in rest else 5
        name, vals, kind = _vals(rest, cs)
        print('%s: %d predicates known (%d stated, %d implied by applied cards)' % (
            name, sum(v in ('true', 'false') for v in vals.values()),
            sum(k == 'stated' for k in kind.values()), sum(k == 'implied' for k in kind.values())))
        if cmd == 'eligible':
            for cid, state, why in eligible(vals, cs, preds):
                print('%-9s %-34s %s' % (state, cid, why))
        elif cmd == 'precedent':
            pool = {r['name']: {k: x[0] for k, x in values(r, cs).items()} for _, r in records() if r['name'] != name}
            used = {r['name']: sorted({a['id'] for a in r.get('techniques', []) if a.get('id')}) for _, r in records()}
            for score, agree, differ, g in precedent(vals, pool, top):
                print('%+3d  agree %d differ %d  %-28s %s' % (score, agree, differ, g, ', '.join(used[g])))
        elif cmd == 'lessons-for':
            sys.stdout.reconfigure(encoding='utf-8')
            for x in shared():
                if applies(x, vals):
                    unknown = [p for p in x.get('when', []) if vals.get(p) != 'true']
                    print('%-36s %s%s' % (x['id'], x['title'], ' (not ruled out: %s)' % ', '.join(unknown) if unknown else ''))
        else:
            for x in risks():
                if applies(x, vals):
                    unknown = [p for p in x.get('when', []) if vals.get(p) != 'true']
                    print('%-28s %s%s\n    cover: %s' % (x['id'], x['title'],
                                                         ' (not ruled out: %s)' % ', '.join(unknown) if unknown else '', x['cover']))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
