#!/usr/bin/env python3
"""The learning loop's checkable part (docs/LEARNING.md): every lesson has a disposition that
resolves, technique use is recorded, kept probes are complete, new cards carry their evidence.

    python tools/learncheck.py            exit 0 = PASS, 1 = FAIL (doccheck runs check() too)
    python tools/learncheck.py --usage    per card / probe: how often games used it, it helped,
                                          it did not help, it was corrected

Checks STRUCTURE, never technical truth. Scope (docs/LEARNING.md 6): games/<game>.md files with a
"## Lessons" section; a game file changed against origin/main that still has the old
"## Lesson candidates" section fails (migrate when revisited); untouched old files are left alone.
Not a game dependency (docs/records): changing it re-verifies nothing.
"""
import collections
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, 'docs', 'techniques')
PDIR = os.path.join(ROOT, 'tools', 'probes')
NOT_CARDS = {'STANDARD.md', 'CHANGELOG.md'}
USE = ('used', 'helped', 'no help', 'corrected')
PROBE_FIELDS = ('Invocation:', 'Limits:', 'Origin:', 'Smoke test:')
TAG = re.compile(r'\[(card|doc|tool|backlog|probe|local|deferred)\b([^\]]*)\]')


def cards():
    """-> {id: (meta dict, [headings], text)}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(TDIR, '*.md'))):
        if os.path.basename(p) in NOT_CARDS:
            continue
        t = open(p).read()
        m = re.search(r'```json\s*(\{.*?\})\s*```', t, re.S)
        meta = json.loads(m.group(1)) if m else {}
        heads = [h.strip('# ').strip() for h in re.findall(r'^#{1,4} .+$', t, re.M)]
        out[os.path.splitext(os.path.basename(p))[0]] = (meta, heads, t)
    return out


def probes():
    """-> {file name: (docstring fields present, listed in README)}"""
    readme = open(os.path.join(PDIR, 'README.md')).read() if os.path.exists(os.path.join(PDIR, 'README.md')) else ''
    out = {}
    for p in sorted(glob.glob(os.path.join(PDIR, '*.py'))):
        n = os.path.basename(p)
        t = open(p).read()
        out[n] = ([f for f in PROBE_FIELDS if f not in t], ('| %s |' % n) in readme)
    return out


def _ctx():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import doccheck
    os.chdir(ROOT)
    heads, c2 = doccheck.headings()
    return {'heads': heads, 'c2': c2, 'mods': doccheck.module_names(), 'cli': doccheck.cli_flags(),
            'has_section': doccheck.has_section}


def _section(text, title):
    """Lines of the '## title' section (bullets with their continuation lines joined)."""
    m = re.search(r'^## %s\s*$(.*?)(?=^## |\Z)' % re.escape(title), text, re.M | re.S)
    if not m:
        return None
    items, cur = [], None
    for line in m.group(1).splitlines():
        if line.startswith('- '):
            cur = [line[2:].strip()]
            items.append(cur)
        elif cur is not None and line.startswith('  ') and line.strip():
            cur.append(line.strip())
        elif not line.strip():
            cur = None
    return [' '.join(x) for x in items]


def _tool_ok(ref, ctx):
    ref = ref.strip().strip('`')
    m = re.match(r'(?:python3? )?nexclash\.py ([a-z]+)', ref)
    if m:
        return m.group(1) in ctx['cli']
    m = re.match(r'(?:python3? -m )?nexclash\.([a-z_0-9]+)$', ref)
    if m:
        return m.group(1) in ctx['mods']
    m = re.match(r'([a-z_0-9]+)\.([A-Za-z_][A-Za-z_0-9]*)(\(\))?$', ref)
    if m and m.group(1) in ctx['mods']:
        return m.group(2) in ctx['mods'][m.group(1)]
    return os.path.exists(os.path.join(ROOT, ref))


def _check_tag(kind, arg, game_text, cs, ps, ctx):
    """-> problem text or None"""
    arg = arg.strip()
    if kind == 'card':
        m = re.match(r'([\w.-]+)\s+§\s*(.+)$', arg)
        if not m:
            return 'card tag needs "[card <id> §<section>]"'
        cid, sec = m.groups()
        if cid not in cs:
            return 'no card %s' % cid
        if not any(h.lower().startswith(sec.strip().lower()) for h in cs[cid][1]):
            return 'card %s has no section "%s"' % (cid, sec)
    elif kind == 'doc':
        m = re.match(r'(PLAYBOOK|LEARNINGS|BRIEFING|TECHNIQUES)\s+(.+)$', arg)
        if m:
            doc, sec = m.groups()
            n = re.match(r'C2 #(\d+)', sec)
            if n:
                return None if int(n.group(1)) in ctx['c2'] else 'no BRIEFING C2 #%s' % n.group(1)
            return None if ctx['has_section'](ctx['heads'], doc, sec.split()[0]) else 'no %s %s' % (doc, sec)
        m = re.match(r'((?:docs|tools)/[\w./-]+\.md)\s+§\s*(.+)$', arg)
        if not m:
            return 'doc tag needs "[doc BRIEFING A1]" or "[doc docs/X.md §Heading]"'
        p, sec = m.groups()
        if not os.path.exists(os.path.join(ROOT, p)):
            return 'no file %s' % p
        hs = [h.strip('# ').strip().lower() for h in open(os.path.join(ROOT, p)) if h.startswith('#')]
        if not any(h.startswith(sec.strip().lower()) for h in hs):
            return '%s has no section "%s"' % (p, sec)
    elif kind == 'tool':
        if not arg or not _tool_ok(arg, ctx):
            return 'tool "%s" does not resolve (a request not built yet is [backlog C2 #N])' % arg
    elif kind == 'backlog':
        m = re.match(r'C2 #(\d+)$', arg)
        if not m or int(m.group(1)) not in ctx['c2']:
            return 'backlog tag needs an existing "[backlog C2 #N]"'
    elif kind == 'probe':
        n = os.path.basename(arg)
        if not arg.startswith('tools/probes/') or n not in ps:
            return 'no probe %s' % arg
        missing, listed = ps[n]
        if missing or not listed:
            return 'probe %s: %s' % (n, ', '.join(missing + ([] if listed else ['not in tools/probes/README.md'])))
    elif kind == 'local':
        if not re.match(r':\s*\S.{6,}', arg):
            return 'local tag needs a reason "[local: <reason>]"'
    elif kind == 'deferred':
        m = re.match(r'(C2 #(\d+)|Open)\s*:\s*reconsider when\s+\S.{4,}$', arg)
        if not m:
            return 'deferred tag needs "[deferred C2 #N|Open: reconsider when <condition>]"'
        if m.group(2) and int(m.group(2)) not in ctx['c2']:
            return 'no BRIEFING C2 #%s' % m.group(2)
        if m.group(1) == 'Open' and not re.search(r'^## Open', game_text, re.M):
            return 'no "## Open" section to defer to'
    return None


def changed_games():
    """Game files changed against origin/main (merge base, incl. the working tree); None: no git."""
    try:
        base = subprocess.run(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        out = subprocess.run(['git', 'diff', '--name-only', base], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {f for f in out if f.startswith('games/') and f.endswith('.md')}


def check(ctx=None):
    """-> list of problems (strings)."""
    ctx = ctx or _ctx()
    cs, ps = cards(), probes()
    bad = []
    for n, (missing, listed) in ps.items():
        if missing:
            bad.append('tools/probes/%s: docstring lacks %s' % (n, ', '.join(missing)))
        if not listed:
            bad.append('tools/probes/%s: not listed in tools/probes/README.md' % n)
    changed = changed_games()
    for g in sorted(glob.glob(os.path.join(ROOT, 'games', '*.md'))):
        rel = os.path.relpath(g, ROOT)
        t = open(g).read()
        lessons = _section(t, 'Lessons')
        if lessons is None:
            if changed is not None and rel in changed and re.search(r'^## Lesson candidates', t, re.M):
                bad.append('%s: changed but still "## Lesson candidates": migrate to "## Lessons" with '
                           'dispositions (docs/LEARNING.md)' % rel)
            continue
        if re.search(r'^## Lesson candidates', t, re.M):
            bad.append('%s: both "## Lessons" and "## Lesson candidates"' % rel)
        for i, item in enumerate(lessons, 1):
            tags = TAG.findall(item[:400])
            if not tags or not item.startswith('['):
                bad.append('%s: lesson %d has no disposition tag at its start: %s' % (rel, i, item[:70]))
                continue
            for kind, arg in tags:
                p = _check_tag(kind, arg, t, cs, ps, ctx)
                if p:
                    bad.append('%s: lesson %d: %s' % (rel, i, p))
        use = _section(t, 'Technique use')
        if use is None:
            bad.append('%s: "## Lessons" needs "## Technique use" (docs/LEARNING.md 5)' % rel)
        else:
            for item in use:
                m = re.match(r'([\w./-]+):\s*(used|helped|no help|corrected)\b', item)
                if not m:
                    bad.append('%s: technique use line "%s" (want "<card id | probe>: used | helped | '
                               'no help: why | corrected: what")' % (rel, item[:60]))
                elif m.group(1) not in cs and os.path.basename(m.group(1)) not in ps:
                    bad.append('%s: technique use names no card or probe: %s' % (rel, m.group(1)))
    for cid, (meta, heads, text) in cs.items():
        if meta.get('schema', 3) < 4:
            continue                          # migrated when next revised (docs/LEARNING.md 4)
        if meta.get('lifecycle') == 'candidate':
            for k in ('**Assumptions.**', '**Validation gap.**'):
                if k not in text:
                    bad.append('card %s (schema 4 candidate): no %s line' % (cid, k))
            if not meta.get('examples') and not meta.get('sources'):
                bad.append('card %s (schema 4 candidate): no source (examples or sources)' % cid)
        elif meta.get('lifecycle') == 'active' and not _active_evidence(cid):
            bad.append('card %s (active): no record with a "pass" result for an application of it' % cid)
    return bad


def _active_evidence(cid):
    for p in glob.glob(os.path.join(ROOT, 'docs', 'records', '*.json')):
        r = json.load(open(p))
        apps = {t.get('application') for t in r.get('techniques', []) if t.get('id') == cid}
        if any(x.get('application') in apps and x.get('status') == 'pass' for x in r.get('results', [])):
            return True
    return False


def usage():
    cnt = collections.defaultdict(collections.Counter)
    for g in glob.glob(os.path.join(ROOT, 'games', '*.md')):
        for item in _section(open(g).read(), 'Technique use') or []:
            m = re.match(r'([\w./-]+):\s*(used|helped|no help|corrected)\b', item)
            if m:
                cnt[m.group(1)][m.group(2)] += 1
                cnt[m.group(1)]['games'] += 1
    for k in sorted(cnt):
        print('%-40s %s' % (k, ', '.join('%s %d' % (u, cnt[k][u]) for u in ('games',) + USE if cnt[k][u])))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--usage' in argv:
        usage()
        return 0
    bad = check()
    for b in bad:
        print('FAIL ' + b)
    print('learncheck: %s' % ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
